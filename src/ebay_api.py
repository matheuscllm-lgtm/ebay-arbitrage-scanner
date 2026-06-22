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
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

# Categoria 183454 = CCG Individual Cards (cartas avulsas de TCG no eBay).
CCG_CATEGORY_ID = "183454"


class EbayAuthError(RuntimeError):
    pass


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


class EbayClient:
    def __init__(self, client_id=None, client_secret=None, marketplace="EBAY_US"):
        self.client_id = _clean_secret(client_id or os.environ.get("EBAY_CLIENT_ID", ""))
        self.client_secret = _clean_secret(client_secret or os.environ.get("EBAY_CLIENT_SECRET", ""))
        self.marketplace = marketplace
        self._token = None
        self._token_expires_at = 0.0

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
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 7200))
        return self._token

    def search(self, query, min_price=10.0, max_price=None, limit=50,
               fixed_price_only=False, location_country="US"):
        """Busca anuncios ativos. Retorna lista de models.Listing.

        location_country: filtro server-side de localizacao do item. Default
        US -- a entrega e na COMC (Algona, WA), entao so vendedor americano
        interessa (frete domestico, sem importacao, elegivel ao Authenticity
        Guarantee).
        """
        from .models import Listing

        price_filter = f"price:[{min_price:g}..{'' if max_price is None else f'{max_price:g}'}]"
        filters = [price_filter, "priceCurrency:USD"]
        if location_country:
            filters.append(f"itemLocationCountry:{location_country}")
        if fixed_price_only:
            filters.append("buyingOptions:{FIXED_PRICE}")
        params = {
            "q": query,
            "category_ids": CCG_CATEGORY_ID,
            "filter": ",".join(filters),
            "limit": str(limit),
            "sort": "price",
        }
        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())

        listings = []
        for item in payload.get("itemSummaries", []):
            price = float(item.get("price", {}).get("value", 0) or 0)
            shipping = 0.0
            for opt in item.get("shippingOptions", []):
                cost = opt.get("shippingCost", {})
                if cost.get("value") is not None:
                    shipping = float(cost["value"])
                    break
            seller = item.get("seller", {})
            buying = item.get("buyingOptions", []) or []
            # qualifiedPrograms so vem no endpoint de DETALHE (1 chamada por
            # anuncio -- caro). A elegibilidade e deterministica por politica
            # do eBay: cartas de TCG >= $250 localizadas nos EUA entram
            # automaticamente no Authenticity Guarantee.
            programs = item.get("qualifiedPrograms", []) or []
            country = (item.get("itemLocation", {}) or {}).get("country", "")
            ag = ("AUTHENTICITY_GUARANTEE" in programs
                  or (country == "US" and price >= 250.0))
            listings.append(Listing(
                item_id=item.get("itemId", ""),
                title=item.get("title", ""),
                price=price,
                shipping=shipping,
                currency=item.get("price", {}).get("currency", "USD"),
                buying_option="FIXED_PRICE" if "FIXED_PRICE" in buying else "AUCTION",
                condition=item.get("condition", "") or "",
                seller_feedback_pct=float(seller.get("feedbackPercentage", 0) or 0),
                seller_feedback_score=int(seller.get("feedbackScore", 0) or 0),
                url=item.get("itemWebUrl", ""),
                image_url=(item.get("image", {}) or {}).get("imageUrl", ""),
                authenticity_guarantee=ag,
                top_rated=bool(item.get("topRatedBuyingExperience", False)),
                country=country,
            ))
        return listings
