"""Cliente da eBay Browse API (oficial e gratuita).

Por que API e nao scraping: o eBay bloqueia scraping direto (HTTP 403 testado
em 2026-06-09 com urllib e cloudscraper). A Browse API e gratuita (5.000
chamadas/dia) e devolve JSON estruturado com preco, frete, vendedor e condicao.

Setup (uma vez, ~5 minutos, gratis):
1. Criar conta em https://developer.ebay.com (pode usar a conta eBay normal).
2. Em "Application Keys", criar um keyset de PRODUCTION.
3. Definir as variaveis de ambiente do Windows (usuario):
   EBAY_CLIENT_ID     = App ID (Client ID)
   EBAY_CLIENT_SECRET = Cert ID (Client Secret)

O token OAuth e obtido automaticamente (client credentials, validade ~2h).

Orcamento: `EbayClient.calls` conta cada requisicao HTTP de busca feita pelo
cliente (inclusive tentativas que falharam e foram repetidas) -- a cota
gratis e 5.000/dia. `EbayClient.last_total` guarda o `total` que a API
reportou na ultima busca (quantos anuncios casam a query, alem da pagina).

Fixture real (offline) do payload de busca:
`tests/fixtures/ebay_search_charizard_base_psa.json` (captura 2026-09-03).
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .models import Listing

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

# Categoria 183454 = CCG Individual Cards (cartas avulsas de TCG no eBay).
CCG_CATEGORY_ID = "183454"

# Teto de itens por pagina da Browse API (item_summary/search).
MAX_LIMIT = 200

# Retry de busca: 429 (rate limit), 5xx e erro transitorio de rede (timeout
# de handshake TLS, reset) repetem ate SEARCH_ATTEMPTS vezes com backoff
# 2s/4s -- mesma calibracao do pricecharting.fetch_page. Outro 4xx nao repete.
SEARCH_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2

# Politica do eBay: carta de TCG >= US$250 localizada nos EUA entra
# automaticamente no Authenticity Guarantee (autenticacao fisica antes de
# chegar ao comprador).
AG_MIN_PRICE_USD = 250.0


class EbayAuthError(RuntimeError):
    """Credencial ausente ou recusada pelo endpoint de token (401/403)."""


class EbayApiError(RuntimeError):
    """Falha da Browse API na busca: 4xx definitivo ou 429/5xx/rede persistente.

    O chamador decide: o scanner registra o erro da carta e segue adiante.
    """


def _clean_secret(value):
    """Remove BOM/zero-width/espacos de uma credencial lida do ambiente.

    Uma chave colada com BOM (U+FEFF) ou zero-width (U+200B) -- comum ao
    copiar de alguns editores/paineis -- viraria um header Authorization
    Basic invalido (-> eBay 401, "configurado mas nao autentica"). Pior: uma
    chave que seja SO esses invisiveis passaria como "configurada" (truthy) e
    tomaria 401 em vez de cair limpo no modo pricing-only. `.strip()` NAO
    remove BOM/zero-width (nao sao whitespace), entao removemos explicito.
    Erro recorrente numero 1 da frota (cross-scanner; ver CLAUDE.md).
    """
    if not value:
        return ""
    return value.replace("\ufeff", "").replace("\u200b", "").strip()


def _is_transient_http(code):
    return code == 429 or 500 <= code < 600


def parse_search_payload(payload):
    """Converte o JSON de `item_summary/search` em lista de models.Listing.

    Funcao PURA (sem rede): recebe o payload bruto (dict) e monta um Listing
    por item de `itemSummaries`. Campos ausentes viram valor neutro (0.0 /
    "" / False) -- nunca inventa preco.

    - preco = `price.value`; frete = 1a `shippingOptions[].shippingCost.value`
      com valor (frete CALCULATED vem sem custo na busca -> 0.0 = desconhecido);
    - Authenticity Guarantee: `qualifiedPrograms` so vem no endpoint de
      DETALHE (1 chamada por anuncio -- caro), entao o flag e calculado por
      politica do eBay: >= US$250 nos EUA (ver AG_MIN_PRICE_USD). Se o campo
      vier, tambem conta;
    - `condition` e o texto do eBay ("Graded", "Ungraded", ...); a condicao
      fina da carta (Near Mint etc.) nao vem na busca -- ver spike 2026-09-03
      na fixture.
    """
    listings = []
    for item in (payload or {}).get("itemSummaries", []) or []:
        price_obj = item.get("price", {}) or {}
        price = float(price_obj.get("value", 0) or 0)
        shipping = 0.0
        for opt in item.get("shippingOptions", []) or []:
            cost = opt.get("shippingCost", {}) or {}
            if cost.get("value") is not None:
                shipping = float(cost["value"])
                break
        seller = item.get("seller", {}) or {}
        buying = item.get("buyingOptions", []) or []
        programs = item.get("qualifiedPrograms", []) or []
        country = (item.get("itemLocation", {}) or {}).get("country", "")
        ag = ("AUTHENTICITY_GUARANTEE" in programs
              or (country == "US" and price >= AG_MIN_PRICE_USD))
        listings.append(Listing(
            item_id=item.get("itemId", "") or "",
            title=item.get("title", "") or "",
            price=price,
            shipping=shipping,
            currency=price_obj.get("currency", "USD") or "USD",
            buying_option="FIXED_PRICE" if "FIXED_PRICE" in buying else "AUCTION",
            condition=item.get("condition", "") or "",
            seller_feedback_pct=float(seller.get("feedbackPercentage", 0) or 0),
            seller_feedback_score=int(seller.get("feedbackScore", 0) or 0),
            url=item.get("itemWebUrl", "") or "",
            image_url=(item.get("image", {}) or {}).get("imageUrl", "") or "",
            authenticity_guarantee=ag,
            top_rated=bool(item.get("topRatedBuyingExperience", False)),
            country=country or "",
        ))
    return listings


class EbayClient:
    def __init__(self, client_id=None, client_secret=None, marketplace="EBAY_US"):
        self.client_id = _clean_secret(client_id or os.environ.get("EBAY_CLIENT_ID", ""))
        self.client_secret = _clean_secret(client_secret or os.environ.get("EBAY_CLIENT_SECRET", ""))
        self.marketplace = marketplace
        self._token = None
        self._token_expires_at = 0.0
        # Orcamento: requisicoes HTTP de BUSCA feitas por esta instancia
        # (token nao conta). Tentativa repetida por 429/5xx tambem conta --
        # ela gastou cota do mesmo jeito.
        self.calls = 0
        # `total` reportado pela API na ultima busca (None antes da 1a).
        self.last_total = None

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    def _get_token(self):
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        if not self.configured:
            raise EbayAuthError(
                "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET nao definidos. "
                "Veja o setup no topo de src/ebay_api.py (gratis, ~5 min)."
            )
        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": SCOPE}
        ).encode()
        req = urllib.request.Request(
            TOKEN_URL,
            data=body,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise EbayAuthError(
                    f"eBay recusou as credenciais (HTTP {e.code} no token). "
                    "Confira EBAY_CLIENT_ID/SECRET (keyset de PRODUCTION) e se "
                    "a chave nao veio com BOM/zero-width."
                ) from e
            raise EbayApiError(
                f"eBay token endpoint HTTP {e.code} {e.reason}") from e
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 7200))
        return self._token

    def _request_search_json(self, url):
        """Uma pagina de busca, com retry em 429/5xx/rede. Conta em `calls`."""
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
        )
        last_error = None
        for attempt in range(SEARCH_ATTEMPTS):
            if attempt:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)   # 2s, 4s
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                if not _is_transient_http(e.code):
                    raise EbayApiError(
                        f"eBay Browse API HTTP {e.code} {e.reason} "
                        f"(nao repetivel) em {url}") from e
                last_error = e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # Timeout de handshake TLS / reset / DNS: transitorio.
                last_error = e
        raise EbayApiError(
            f"eBay Browse API falhou {SEARCH_ATTEMPTS}x em {url}: "
            f"{last_error}") from last_error

    def search(self, query, min_price=10.0, max_price=None, limit=MAX_LIMIT,
               fixed_price_only=True, location_country="US", max_pages=3):
        """Busca anuncios ativos. Retorna lista de models.Listing.

        - fixed_price_only: DEFAULT True (decisao do operador 2026-09-03: so
          preco fixo; leilao nao entra no funil).
        - limit: itens por pagina (teto da Browse API = 200 -> ValueError
          acima disso).
        - max_pages: pede paginas sucessivas por `offset` ate max_pages; para
          antes se a pagina vier curta (< limit) ou se offset >= `total`
          reportado. Itens repetidos entre paginas (a ordenacao por preco
          pode deslocar anuncios) sao deduplicados por itemId.
        - location_country: filtro server-side de localizacao do item.
          Default US -- a entrega e na COMC (Algona, WA), entao so vendedor
          americano interessa (frete domestico, sem importacao, elegivel ao
          Authenticity Guarantee). Vazio/None = sem filtro.

        Compatibilidade: `search(query, min_price=...)` (como o scanner chama)
        segue valendo.
        """
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            raise ValueError(
                f"limit={limit!r} invalido: a Browse API aceita 1..{MAX_LIMIT}")
        if max_pages < 1:
            raise ValueError(f"max_pages={max_pages!r} invalido: minimo 1")

        price_filter = f"price:[{min_price:g}..{'' if max_price is None else f'{max_price:g}'}]"
        filters = [price_filter, "priceCurrency:USD"]
        if location_country:
            filters.append(f"itemLocationCountry:{location_country}")
        if fixed_price_only:
            filters.append("buyingOptions:{FIXED_PRICE}")

        listings = []
        seen_ids = set()
        offset = 0
        for _page in range(max_pages):
            params = {
                "q": query,
                "category_ids": CCG_CATEGORY_ID,
                "filter": ",".join(filters),
                "limit": str(limit),
                "offset": str(offset),
                "sort": "price",
            }
            url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
            payload = self._request_search_json(url)

            total = payload.get("total")
            self.last_total = int(total) if total is not None else None
            items = payload.get("itemSummaries", []) or []
            for listing in parse_search_payload(payload):
                # item_id vazio nao identifica nada -> nao entra no set.
                if listing.item_id:
                    if listing.item_id in seen_ids:
                        continue
                    seen_ids.add(listing.item_id)
                listings.append(listing)

            if len(items) < limit:
                break
            offset += limit
            if self.last_total is not None and offset >= self.last_total:
                break
        return listings
