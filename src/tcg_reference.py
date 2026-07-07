"""Referencia TCGplayer via tcgcsv.com (dump diario gratuito).

O tcgcsv.com espelha os precos do TCGplayer em JSON estatico (categoria 3 =
Pokemon). E a MESMA fonte de preco real usada pelo MYP scanner (v5.15+):

  GET /tcgplayer/3/groups              -> {"results": [{groupId, name, ...}]}
  GET /tcgplayer/3/{groupId}/products  -> {"results": [{productId, name, url,
                                            extendedData: [{name: "Number",
                                                            value: "NNN/MMM"}]}]}
  GET /tcgplayer/3/{groupId}/prices    -> {"results": [{productId, marketPrice,
                                            midPrice, lowPrice, subTypeName}]}

Papel neste scanner: preco de referencia PRINCIPAL para cartas RAW NM
(TCGplayer market e a referencia canonica da frota para singles raw); para
graded o TCGplayer nao tem preco, entao la a referencia segue PriceCharting.

Honestidade (invariante da frota): este modulo NUNCA inventa preco nem URL.
Sem match confiavel de set/carta, ou sem `marketPrice` -> retorna None e o
caller usa o fallback rotulado. Nunca degrada para mid/low silenciosamente.

Implementacao stdlib-only (urllib), mesmo padrao do pricecharting.py:
cache 24h em disco + throttle entre requests + tolerancia total a falha.
"""
import gzip
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer/3"  # categoria 3 = Pokemon
CACHE_TTL_SECONDS = 24 * 3600
REQUEST_GAP_SECONDS = 0.15  # throttle leve (arquivos estaticos, mas educacao)
DEFAULT_CACHE_DIR = os.path.join("data", "cache", "tcgcsv")

# User-Agent e OBRIGATORIO: sem ele o tcgcsv responde 401 (comprovado no MYP).
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
}

# Ordem de preferencia do subtype ao escolher o preco. So `marketPrice` conta;
# um subtype presente mas sem marketPrice e pulado (nunca cai pra mid/low).
SUBTYPE_ORDER = ("Normal", "Holofoil", "Reverse Holofoil")

_last_request_at = [0.0]


@dataclass
class TcgReference:
    """Preco de mercado TCGplayer de UMA carta, com proveniencia."""
    market_usd: float   # marketPrice do TCGplayer (USD)
    product_url: str    # URL do produto no TCGplayer (campo `url` do tcgcsv)
    group_name: str     # nome do set no tcgcsv (auditoria do match)
    sub_type: str       # subtype usado (Normal / Holofoil / Reverse Holofoil)


def _fetch_json(url, cache_dir=DEFAULT_CACHE_DIR):
    """Baixa um endpoint JSON do tcgcsv com cache em disco (24h).

    Tolerante a falha: qualquer erro (rede, HTTP, JSON invalido) -> None.
    O scan NUNCA quebra por causa da referencia TCG.
    """
    os.makedirs(cache_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", url.lower())[-120:]
    cache_path = os.path.join(cache_dir, slug + ".json")
    if os.path.exists(cache_path):
        if time.time() - os.path.getmtime(cache_path) < CACHE_TTL_SECONDS:
            try:
                with open(cache_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                pass  # cache corrompido -> refaz o fetch

    try:
        wait = REQUEST_GAP_SECONDS - (time.time() - _last_request_at[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
        _last_request_at[0] = time.time()
        payload = json.loads(data.decode("utf-8", errors="replace"))
    except Exception:
        return None
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass  # cache e otimizacao, nao requisito
    return payload


def _results(payload):
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    return results if isinstance(results, list) else []


def _norm(text):
    """Normaliza nome pra comparacao: minusculo, so alfanumerico+espaco."""
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()


def resolve_group(card, groups):
    """Resolve o set da carta -> group do tcgcsv.

    Match EXATO case-insensitive do nome do set (`card.tcg_set` quando
    preenchido na watchlist, senao `card.set_name`) contra `groups[].name`.
    Sem match exato -> None (nunca chuta parcial: injetar preco de outro set
    como 'real' e a classe de bug que a frota ja pagou caro pra corrigir).
    """
    wanted = (card.tcg_set or card.set_name or "").strip().lower()
    if not wanted:
        return None
    for g in groups:
        if str(g.get("name") or "").strip().lower() == wanted:
            return g
    return None


def _product_number(product):
    """Numero do colecionador do produto: extendedData 'Number' quando
    presente; senao tenta extrair 'NNN/MMM' ou '- NNN' do nome."""
    for ed in product.get("extendedData") or []:
        if ed.get("name") == "Number" and ed.get("value"):
            return str(ed["value"])
    name = str(product.get("name") or "")
    m = re.search(r"\b(\d+)\s*/\s*\d+\b", name)
    if m:
        return m.group(1)
    m = re.search(r"-\s*(\d+)\s*$", name)
    if m:
        return m.group(1)
    return ""


def _numerator(number_text):
    """'004/102' -> '4'; 'TG12/TG30' -> '' (nao-numerico: sem normalizacao)."""
    numerator = str(number_text or "").split("/")[0].strip()
    if not numerator.isdigit():
        return ""
    return numerator.lstrip("0") or "0"


def _number_matches(want_raw, product_number):
    """True se o numero da watchlist casa o numero do produto.

    - Numerador NUMERICO: compara numeradores normalizados (zero-padding
      tolerado: '4' casa '004/102').
    - Numerador NAO-numerico (TG04, GG12, SV107...): match EXATO
      case-insensitive do texto cru contra o numero do produto OU contra a
      parte antes do '/' ('TG04' casa 'TG04' e 'TG04/TG30'; NAO casa
      '4/102'). A restricao de numero NUNCA e dropada: degradar pra match
      so-por-nome ja devolveu a carta ERRADA como referencia (review PR #18
      -- watchlist 'Charizard TG04' casava o Charizard base 4/102).
    """
    want_raw = str(want_raw or "").strip()
    want_num = _numerator(want_raw)
    if want_num:
        return _numerator(product_number) == want_num
    have_raw = str(product_number or "").strip().lower()
    have_prefix = have_raw.split("/")[0].strip()
    return bool(have_raw) and want_raw.lower() in (have_raw, have_prefix)


def find_product(card, products):
    """Acha o produto da carta no dump do set.

    Match primario: numero do colecionador (extNumber do extendedData quando
    presente; senao numero embutido no nome) + CONFIRMACAO pelo nome
    normalizado (todas as palavras do nome da carta presentes no nome do
    produto). Numero sozinho nao basta (sets com variantes repetem numeros);
    nome sozinho tambem nao (Charizard aparece N vezes). Se mais de UM
    candidato sobrevive a numero+nome, e ambiguo -> None (conservador:
    perder deal > inventar deal). Sem match confiavel -> None.
    """
    want_words = _norm(card.name)
    if not want_words:
        return None

    def name_matches(product):
        have = _norm(product.get("name"))
        return all(w in have for w in want_words)

    number = str(card.number or "").strip()
    if number:
        by_number = [p for p in products
                     if _number_matches(number, _product_number(p))]
        confirmed = [p for p in by_number if name_matches(p)]
        return confirmed[0] if len(confirmed) == 1 else None

    # Watchlist sem numero: so aceita se o match por nome for UNICO.
    by_name = [p for p in products if name_matches(p)]
    return by_name[0] if len(by_name) == 1 else None


def pick_market_price(price_rows):
    """Escolhe o marketPrice do produto na ordem Normal -> Holofoil ->
    Reverse Holofoil. SO `marketPrice` conta; sem marketPrice em nenhum
    subtype -> (None, "") — nunca degrada pra mid/low silenciosamente."""
    by_sub = {}
    for row in price_rows:
        sub = str(row.get("subTypeName") or "")
        market = row.get("marketPrice")
        if isinstance(market, (int, float)) and market > 0:
            by_sub.setdefault(sub, float(market))
    for sub in SUBTYPE_ORDER:
        if sub in by_sub:
            return by_sub[sub], sub
    return None, ""


def get_tcg_reference(card, cache_dir=DEFAULT_CACHE_DIR):
    """WatchCard -> TcgReference (market USD + URL do produto) ou None.

    None = sem referencia TCGplayer confiavel (carta nao-EN, set nao resolvido,
    carta nao achada, ou produto sem marketPrice). O caller decide o fallback
    rotulado.
    """
    # A categoria 3 do tcgcsv e o catalogo INGLES do TCGplayer: uma carta JP
    # casaria com o produto EN homonimo e a margem sairia de um produto que
    # nao e o anunciado, rotulada como "TCG real". Carta nao-EN fica sem TCG
    # ref e cai no fallback PriceCharting ROTULADO (a pagina JP la e a certa).
    if str(getattr(card, "language", "EN") or "EN").strip().upper() != "EN":
        return None

    groups = _results(_fetch_json(f"{TCGCSV_BASE}/groups", cache_dir))
    group = resolve_group(card, groups)
    if not group or group.get("groupId") is None:
        return None
    gid = group["groupId"]

    products = _results(_fetch_json(f"{TCGCSV_BASE}/{gid}/products", cache_dir))
    product = find_product(card, products)
    if not product or product.get("productId") is None:
        return None
    pid = product["productId"]

    prices = _results(_fetch_json(f"{TCGCSV_BASE}/{gid}/prices", cache_dir))
    rows = [r for r in prices if r.get("productId") == pid]
    market, sub = pick_market_price(rows)
    if market is None:
        return None

    return TcgReference(
        market_usd=market,
        product_url=str(product.get("url") or ""),
        group_name=str(group.get("name") or ""),
        sub_type=sub,
    )
