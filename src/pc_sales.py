"""PriceCharting — vendas concluídas (eBay) como referência de preço.

Portado de scanner-comc/comc_scanner/pricecharting_client.py @ dd952ba (2026-09-03).

Complementa ``src/pricecharting.py`` (que lê só as COLUNAS de preço por grade): aqui a
referência vem das **vendas concluídas** da página pública de cada carta, para SLABS
(cartas gradadas: o TCGplayer/tcgcsv só precifica carta solta) e para carta solta em
condição LP (que NUNCA pode ser comparada com o market NM do TCGplayer).

A página pública de cada carta traz (a) a tabela "Full Price Guide" com colunas por
nota (``PSA 10``, ``BGS 10``, ``BGS 10 Black``, ``CGC 10 Pristine``, ``Grade 9``…) e
(b) várias tabelas ``completed-auctions-*`` com as vendas concluídas: data, título do
anúncio e preço. Política do operador (2026-09-02):

- Referência = **mediana de vendas concluídas** da MESMA carta, variante, idioma
  (inglês), certificadora, nota e subcategoria (``comparable_sales``) — ou, para carta
  solta LP, de vendas cujo título diga explicitamente LP (``lp_sales``). O título tem
  que citar UMA só nota e o MESMO conjunto de tokens de variante que a listagem
  (``variant_tokens``: reverse, 1st, shadowless, staff, prerelease, cosmos, error,
  signed, promo). Nota vizinha ou variante diferente NUNCA é proxy.
- Janelas (``sales_reference``): ≥3 vendas em 180 dias → ``liquidity="ok"``; ≥3 só em
  365 dias → ``"low"`` (referência válida, marcada baixa-liquidez); 1–2 vendas em 365
  dias → ``"thin"`` (só com ``allow_thin``: slabs, que viram REVISAR; LP exige ≥3);
  0 → None. A mediana usa as ``SALES_WINDOW`` vendas mais recentes da janela.
- As colunas do PriceCharting (mesmo "PSA 10" exata) e os buckets genéricos ("Grade 9")
  NUNCA geram referência. A coluna exata da nota, quando existe, viaja em
  ``SalesRef.column_price`` só como informação (sanidade coluna÷vendas na entrega).

Diferença em relação ao original: este repo não tem módulo ``grading``. Em
``graded_reference`` a nota é qualquer objeto com ``grader``/``value``/``qualifier``/
``label`` (duck typing) e a coluna EXATA do PriceCharting vem pelo parâmetro
``column_key`` ("PSA 10", "BGS 10 BLACK", "CGC 10"…); ``None`` → ``column_price`` None.

Scrape leve com urllib (padrão deste repo em ``src/pricecharting.py``: mesmos headers,
gzip, retry 3x em 429/5xx/erro de rede — caso real 2026-09-01: um handshake pendurado
derrubou uma carta do run). Cache em disco **do dia** (``data/cache/pc/<AAAA-MM-DD>/``):
o operador exige dados só de hoje — o cache existe para não repetir a mesma carta dentro
de um run, nunca para reaproveitar ontem.

Invariantes: NUNCA inventa preço (busca que não casa nome+número+set → None; 0 vendas
comparáveis → None mesmo que a coluna exista); rede, bloqueio ou página sem tabela
nenhuma → ``PcError`` (o pipeline conta como ERRO da fonte, distinto de "sem venda");
guarda de set bidirecional (o console do PC tem que ser exatamente o set — nada de
tiragem japonesa/coreana).
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import gzip
import html as html_mod
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://www.pricecharting.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}
REQUEST_GAP_SECONDS = 2.0  # educação com o site
# Erro transitório de rede (handshake TLS pendurado, conexão resetada, 429/5xx) não
# pode derrubar a carta do run: tenta de novo com backoff curto; só depois de esgotar
# as tentativas o erro sobe como PcError.
FETCH_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0
DEFAULT_CACHE_DIR = os.path.join("data", "cache", "pc")

# Tabela "Full Price Guide" (#full-prices): rótulo → chave normalizada.
FULL_TABLE_GRADE_BY_LABEL = {
    "Ungraded": "RAW",
    "Grade 7": "GRADE 7",
    "Grade 8": "GRADE 8",
    "Grade 9": "GRADE 9",      # bucket genérico (todas as certificadoras) — nunca referência
    "Grade 9.5": "GRADE 9.5",  # idem
    "PSA 10": "PSA 10",
    "BGS 10": "BGS 10",
    "CGC 10": "CGC 10",
    "SGC 10": "SGC 10",
    "TAG 10": "TAG 10",
    "ACE 10": "ACE 10",
    "BGS 10 Black": "BGS 10 BLACK",
    "CGC 10 Pristine": "CGC 10 PRISTINE",
}
# Tabela principal (#price_data) usa ids herdados de videogame:
MAIN_TABLE_GRADE_BY_ID = {
    "used_price": "RAW",
    "complete_price": "GRADE 7",
    "new_price": "GRADE 8",
    "graded_price": "GRADE 9",
    "box_only_price": "GRADE 9.5",
    "manual_only_price": "PSA 10",
}

MIN_COMPARABLE_SALES = 3               # referência válida só com ≥3 vendas comparáveis
SALES_WINDOW = 10                      # mediana das 10 mais recentes (anti-outlier)
SALES_MAX_AGE_DAYS = 180               # janela "ok"
SALES_LOW_LIQUIDITY_MAX_AGE_DAYS = 365  # janela "low" (≥3) / "thin" (1–2)
MIN_PAGE_BYTES = 2000      # corpo menor = página de bloqueio/erro, não cachear
_BLOCK_TITLE_RE = re.compile(
    r"<title>[^<]*(Just a moment|Attention Required|Access denied|Rate limit)", re.I)

log = logging.getLogger(__name__)


class PcError(RuntimeError):
    """Fonte PriceCharting FALHOU (rede, bloqueio, layout) — distinto de 'sem venda'."""


_last_request_at = [0.0]
_CODE_PREFIX = re.compile(r"^[A-Za-z0-9]{2,6}:\s*")
# Palavras de variante toleradas no SLUG da busca (não confundir com ``variant_tokens``).
_VARIANT_TOKENS = {"holo", "reverse", "1st", "edition", "shadowless", "unlimited", "promo"}


@dataclass(frozen=True, slots=True)
class SalesRef:
    """Referência = mediana de vendas concluídas comparáveis (slab por nota exata, ou LP)."""
    price: float          # mediana (US$) das SALES_WINDOW vendas mais recentes da janela
    n_sales: int          # vendas comparáveis dentro da janela usada (não só as da mediana)
    window_days: int      # 180 | 365
    liquidity: str        # "ok" (≥3 em 180 d) | "low" (≥3 só em 365 d) | "thin" (1–2 em 365 d)
    url: str              # página da carta no PriceCharting (link de referência)
    label: str            # "vendas PSA 9 (n=5, 2026-03..2026-08)" · "vendas LP (n=4, 2026-05..2026-08)"
    column_price: float | None = None  # coluna EXATA da nota — só informação (slabs)


# --- rede + cache do dia ------------------------------------------------------

def today_stamp() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def today_cache_dir(base: Path | str) -> Path:
    return Path(base) / today_stamp()


def fetch_page(url: str, cache_dir: str | None = None) -> str:
    """Baixa uma página com cache em disco (só válido dentro do mesmo dia UTC).

    Cache em ``<cache_dir ou data/cache/pc>/<AAAA-MM-DD>/``. Erro transitório (429, 5xx,
    URLError/timeout/reset) tenta de novo até ``FETCH_ATTEMPTS`` vezes com backoff;
    4xx definitivo (URL errada) falha já. Toda falha sobe como ``PcError``. Página de
    bloqueio/erro/vazia NUNCA é cacheada: seria re-servida o dia inteiro."""
    cdir = today_cache_dir(cache_dir or DEFAULT_CACHE_DIR)
    cdir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", url.lower())[-120:]
    cache_path = cdir / f"{slug}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    last_err: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        if attempt:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        wait = REQUEST_GAP_SECONDS - (time.time() - _last_request_at[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
            break
        except urllib.error.HTTPError as exc:
            _last_request_at[0] = time.time()  # também em falha: não martelar no retry
            if exc.code == 429 or exc.code >= 500:
                last_err = exc
                continue
            raise PcError(f"PriceCharting HTTP {exc.code} em {url}") from exc  # 4xx: não transitório
        except OSError as exc:  # URLError, TimeoutError, reset, BadGzipFile — transitórios
            _last_request_at[0] = time.time()
            last_err = exc
    else:
        raise PcError(f"PriceCharting indisponível ({last_err}) em {url}") from last_err
    _last_request_at[0] = time.time()
    body = data.decode("utf-8", errors="replace")
    # Nunca cachear página de bloqueio/erro/vazia: seria re-servida o dia inteiro.
    if len(body) < MIN_PAGE_BYTES or _BLOCK_TITLE_RE.search(body):
        raise PcError(f"PriceCharting devolveu página de bloqueio/vazia ({len(body)} B) em {url}")
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, cache_path)
    return body


# --- parsers puros -------------------------------------------------------------

def _money(text: str) -> float | None:
    text = text.replace(",", "").replace("$", "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_grade_prices(body: str) -> dict[str, float]:
    """Preço por coluna da página de uma carta ({"PSA 10": 125.65, ...}) — só informação."""
    prices: dict[str, float] = {}
    m = re.search(r'id="full-prices">.*?<table>(.*?)</table>', body, re.S)
    if m:
        rows = re.findall(
            r"<tr>\s*<td>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*(?:<span[^>]*>)?\s*"
            r"\$?([\d,]+\.\d{2}|N/A)", m.group(1))
        for label, price_text in rows:
            grade = FULL_TABLE_GRADE_BY_LABEL.get(label.strip())
            price = _money(price_text)
            if grade and price is not None:
                prices[grade] = price
    m = re.search(r'<table[^>]*id="price_data".*?</table>', body, re.S)
    if m:
        table = m.group(0)
        for cell_id, grade in MAIN_TABLE_GRADE_BY_ID.items():
            cm = re.search(r'id="%s".{0,300}?\$([\d,]+\.\d{2})' % cell_id, table, re.S)
            if cm:
                price = _money(cm.group(1))
                if price is not None:
                    prices.setdefault(grade, price)
    return prices


_SALES_DIV_RE = re.compile(r'<div class="(completed-auctions-[^"]+)"')
_SALE_ROW_RE = re.compile(r'<tr id="([a-z]+)-(\d+)">(.*?)</tr>', re.S)
_SALE_DATE_RE = re.compile(r'<td class="date">(\d{4}-\d{2}-\d{2})</td>')
_SALE_PRICE_RE = re.compile(r'class="js-price"[^>]*>\s*\$([\d,]+\.\d{2})')
_SALE_TITLE_CELL_RE = re.compile(r'<td class="title">(.*?)</td>', re.S)
# Boilerplate do "Time Warp" (foto da venda, paga) que a célula de imagem injeta na
# linha, e o marcador da fonte ("[eBay]") que já vai em ``source``.
_TITLE_NOISE_RE = re.compile(
    r"Time Warp shows photos of completed sales\..*?to see photos\.\s*(?:OK\b)?"
    r"|\[(?:eBay|TCGPlayer)\]", re.I | re.S)


def _sale_title(row: str) -> str:
    """Título do anúncio: célula ``title`` (ou a linha inteira, em páginas sem ela), sem
    tags, sem o boilerplate "Time Warp … to see photos. OK" e sem o marcador [eBay]."""
    m = _SALE_TITLE_CELL_RE.search(row)
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", m.group(1) if m else row))
    text = _TITLE_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_sales(body: str) -> list[dict]:
    """Vendas concluídas de TODAS as tabelas ``completed-auctions-*`` da página (used,
    cib, new, graded, box-only, manual-only, grade-*, e as combinadas), como
    ``{date, price, title, bucket, source, sale_id}``, deduplicadas por (source, sale_id):
    o ``<tr id="ebay-12345">`` traz o id e as tabelas combinadas repetem linhas. O título
    do anúncio é o que identifica condição/certificadora/nota ("LP", "PSA 9 MINT")."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    starts = list(_SALES_DIV_RE.finditer(body))
    for i, div in enumerate(starts):
        # Janela = até o fim da PRÓPRIA tabela (ou o próximo bloco de vendas, o que vier
        # antes): linhas <tr id="ebay-N"> de outros widgets da página nunca entram.
        nxt = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        close = body.find("</table>", div.end())
        end = min(nxt, close if close != -1 else nxt)
        for source, sale_id, row in _SALE_ROW_RE.findall(body, div.end(), end):
            key = (source, sale_id)
            if key in seen:
                continue
            d = _SALE_DATE_RE.search(row)
            p = _SALE_PRICE_RE.search(row)
            if not d or not p:
                continue
            price = _money(p.group(1))
            if price is None:
                continue
            seen.add(key)
            out.append({"date": d.group(1), "price": price, "title": _sale_title(row),
                        "bucket": div.group(1), "source": source, "sale_id": sale_id})
    return out


# --- filtros de comparabilidade ------------------------------------------------

_VARIANT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("reverse", re.compile(r"\breverse\b", re.I)),
    ("1st", re.compile(r"\b1st\b|\bfirst[\s-]+ed(?:ition)?\b", re.I)),
    ("shadowless", re.compile(r"(?<!non-)(?<!non )\bshadowless\b", re.I)),
    ("staff", re.compile(r"\bstaff\b", re.I)),
    ("prerelease", re.compile(r"\bpre[\s-]?release\b", re.I)),
    ("cosmos", re.compile(r"\bcosmos\b", re.I)),
    ("error", re.compile(r"\b(?:error|err|misprint(?:ed)?)\b", re.I)),
    ("signed", re.compile(r"\b(?:signed|autographed?)\b", re.I)),
    ("promo", re.compile(r"\bpromos?\b", re.I)),  # "Black Star Promos" (set) = "Promo" (título)
    # Produtos NÃO comparáveis com a carta normal (ruído real: "2021 Celebrations Metal
    # UPC PSA 8" na página do Charizard 4/102): reimpressão Classic Collection/Celebrations,
    # cartas de metal, jumbo/oversized e custom/replica/proxy/reprint/fake.
    ("metal", re.compile(r"\bmetal\b", re.I)),
    ("classic", re.compile(r"\b(?:classic\s+collection|celebrations|classic)\b", re.I)),
    ("jumbo", re.compile(r"\b(?:jumbo|oversized?)\b", re.I)),
    ("custom", re.compile(r"\b(?:custom|replica|proxy|reprints?|fake)\b", re.I)),
)


def variant_tokens(text: str) -> frozenset[str]:
    """Tokens de variante presentes no texto (palavras inteiras, sem diferenciar
    maiúsculas): "reverse" (reverse holo/foil), "1st" (1st/first edition), "shadowless"
    ("non-shadowless" = unlimited, não conta), "staff", "prerelease" (pre-release),
    "cosmos", "error" (error/err/misprint), "signed" (signed/autograph), "promo",
    e os NÃO comparáveis "metal", "classic" (Classic Collection/Celebrations), "jumbo",
    "custom" (custom/replica/proxy/reprint/fake).
    Uma venda só é comparável quando o conjunto do seu título é IGUAL ao da listagem:
    venda sem token só casa listagem sem token, e vice-versa."""
    text = text or ""
    return frozenset(tok for tok, rx in _VARIANT_PATTERNS if rx.search(text))


_LANG_NOISE = re.compile(r"\b(japanese|korean|chinese|german|french|italian|spanish)\b", re.I)
# Venda que NAO e uma carta unica (lote, playset, booster/pack, selado, "escolha") nunca
# e comparavel -- review Codex 2026-09-03 ("Expansion Pack", trio LP). "pack fresh" e
# condicao, nao produto.
_NOISE_SALE_RE = re.compile(
    r"\b(lots?|bundle|playset|booster|sealed|collection|choose|pick|set\s+of|x\s*\d{2,}|\d{2,}\s*x)\b"
    r"|\bpacks?\b(?![\s-]*fresh)", re.I)
# Qualquer menção "<certificadora> <nota>" no título — usada para exigir que o
# anúncio cite UMA só nota (título "PSA 9 … comps PSA 10" não entra em nenhuma cesta).
_ANY_GRADE_RE = re.compile(
    r"\b(PSA|BGS|BECKETT|CGC|SGC|TAG|ACE|MNT|GMA|HGA|AGS|KSA|RCG|CSG)\s*-?\s*(10|[1-9](?:\.5)?)(?![\d.])", re.I)
_GRADER_CANON = {"BECKETT": "BGS"}
_CGC_PRISTINE_RE = re.compile(r"\bCGC\s*-?\s*10\s*(?:Pristine)\b", re.I)


# Etiqueta preta da BGS num TÍTULO de venda: só "Black Label" ou "black" colado em
# "BGS 10" (antes ou depois). "Black Kyurem BGS 10" tem "black" no NOME da carta —
# não é Black Label.
# "BGS 10 Black" só conta quando "black" ENCERRA a menção (fim do título ou
# pontuação): "BGS 10 Black Kyurem EX" (nota antes do nome) não é Black Label
# (review PR A eBay, 2026-09-03 — a regex original só protegia a ordem inversa).
_BLACK_LABEL_SALE_RE = re.compile(
    r"\bblack[\s-]*label\b"
    r"|\bBGS\s*-?\s*10\s+black\b(?!\s+[A-Za-z0-9])"
    r"|\bblack\s+BGS\s*-?\s*10\b", re.I)


# "BGS 10 Black <mais texto>" é AMBÍGUO: o texto seguinte tanto pode ser o NOME da
# carta ("BGS 10 Black Kyurem EX") quanto o resto do título de uma Black Label de
# verdade escrita sem a palavra "Label" ("BGS 10 Black Base Set 4/102"). Aqui não dá
# para desempatar (a função não recebe o nome da carta), então o ambíguo não entra em
# cesta NENHUMA -- mesma política do título que cita duas notas. Achado do review da
# COMC (2026-09-04): antes essa venda caía na cesta do BGS 10 COMUM e envenenava a
# mediana (uma venda de US$ 90 mil entre duas de US$ 1,5 mil).
_AMBIGUOUS_BLACK_SALE_RE = re.compile(r"\bBGS\s*-?\s*10\s+black\s+[A-Za-z0-9]", re.I)


def _is_black_label_sale(title: str) -> bool:
    return _BLACK_LABEL_SALE_RE.search(title or "") is not None


def _is_ambiguous_black_sale(title: str) -> bool:
    """True quando não dá para dizer se "black" é etiqueta preta ou nome da carta."""
    t = title or ""
    return (_AMBIGUOUS_BLACK_SALE_RE.search(t) is not None
            and _BLACK_LABEL_SALE_RE.search(t) is None)


def _grade_mentions(title: str) -> set[tuple[str, float]]:
    return {(_GRADER_CANON.get(g.upper(), g.upper()), float(v))
            for g, v in _ANY_GRADE_RE.findall(title)}


def comparable_sales(sales: list[dict], grader: str, value: float, qualifier: str = "",
                     variants: frozenset[str] = frozenset()) -> list[dict]:
    """Só vendas cujo título nomeia a MESMA certificadora e nota — e SÓ ela —, em inglês,
    com preço > 0, na MESMA subcategoria e com o MESMO conjunto de tokens de variante.
    'PSA 9' não casa 'PSA 9.5' nem 'BGS 9'; CGC 10 exige 'Pristine' logo após a nota
    quando qualifier=PRISTINE (e a ausência dele para GEM); BGS 10 exige "black" no
    título quando qualifier=BLACK (e a ausência dele para o BGS 10 comum/dourado);
    "1st Edition" no título não casa listagem sem token, e vice-versa."""
    grader = grader.upper()
    wanted = {(grader, float(value))}
    variants = frozenset(variants)
    out = []
    for s in sales:
        t = s["title"]
        if s.get("price", 0) <= 0 or _LANG_NOISE.search(t) or _NOISE_SALE_RE.search(t):
            continue
        if _grade_mentions(t) != wanted:
            continue  # nenhuma menção, outra nota, ou mais de uma nota citada
        if grader == "CGC" and value == 10.0:
            pristine = _CGC_PRISTINE_RE.search(t) is not None
            if qualifier == "PRISTINE" and not pristine:
                continue
            if qualifier == "GEM" and pristine:
                continue
        if grader == "BGS" and value == 10.0:
            if _is_ambiguous_black_sale(t):
                continue  # não dá para dizer se é etiqueta preta: não serve a cesta nenhuma
            if (qualifier == "BLACK") != _is_black_label_sale(t):
                continue
        if variant_tokens(t) != variants:
            continue
        out.append(s)
    return out


_LP_RE = re.compile(r"\bLP\b|\blightly[\s-]+played\b", re.I)
_LIGHTLY_PLAYED_RE = re.compile(r"\blightly[\s-]+played\b", re.I)
_OTHER_CONDITION_RE = re.compile(
    r"\bnear[\s-]*mint\b|\bNM\b|\bmoderately\b|\bMP\b|\bheavily\b|\bHP\b"
    r"|\bdamaged\b|\bDMG\b|\bplayed\b", re.I)
_BARE_GRADER_RE = re.compile(r"\b(?:PSA|BGS|Beckett|CGC|SGC)\b", re.I)


def lp_sales(sales: list[dict], variants: frozenset[str] = frozenset()) -> list[dict]:
    """Vendas de carta SOLTA em LP: o título diz ``LP`` (palavra inteira) ou "Lightly
    Played" e NÃO cita nota nem certificadora, nem outra condição (NM, Near Mint, MP,
    Moderately, HP, Heavily, Damaged, DMG, "Played" fora de "Lightly Played"), nem idioma
    estrangeiro; preço > 0; mesmo conjunto de tokens de variante da listagem. Venda sem
    condição explícita não serve — nunca se compara LP com NM."""
    variants = frozenset(variants)
    out = []
    for s in sales:
        t = s["title"]
        if s.get("price", 0) <= 0 or _LANG_NOISE.search(t) or _NOISE_SALE_RE.search(t) \
                or not _LP_RE.search(t):
            continue
        if _ANY_GRADE_RE.search(t) or _BARE_GRADER_RE.search(t):
            continue
        if _OTHER_CONDITION_RE.search(_LIGHTLY_PLAYED_RE.sub(" ", t)):
            continue
        if variant_tokens(t) != variants:
            continue
        out.append(s)
    return out


# --- janelas de recência e mediana --------------------------------------------

def _today() -> _dt.date:
    return _dt.datetime.now(_dt.timezone.utc).date()


def recent_only(sales: list[dict], max_age_days: int = SALES_MAX_AGE_DAYS) -> list[dict]:
    """Descarta vendas mais velhas que `max_age_days` (data 'AAAA-MM-DD')."""
    cutoff = _today() - _dt.timedelta(days=max_age_days)
    out = []
    for s in sales:
        try:
            d = _dt.date.fromisoformat(str(s["date"])[:10])
        except ValueError:
            continue
        if d >= cutoff:
            out.append(s)
    return out


def median_recent(sales: list[dict], n_min: int = MIN_COMPARABLE_SALES,
                  window: int = SALES_WINDOW) -> tuple[float | None, int]:
    """Mediana das `window` vendas mais recentes; menos de `n_min` → (None, n)."""
    if len(sales) < n_min:
        return None, len(sales)
    recent = sorted(sales, key=lambda s: s["date"], reverse=True)[:window]
    prices = sorted(s["price"] for s in recent)
    mid = len(prices) // 2
    med = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2.0
    return round(med, 2), len(prices)


def _date_span(sales: list[dict]) -> str:
    """'2026-03..2026-08' (mês da venda mais antiga..mês da mais recente)."""
    months = sorted(str(s["date"])[:7] for s in sales)
    return f"{months[0]}..{months[-1]}" if months else ""


def _build_ref(sales: list[dict], window_days: int, liquidity: str, url: str, what: str) -> SalesRef:
    median, _ = median_recent(sales, n_min=1)
    return SalesRef(price=median, n_sales=len(sales), window_days=window_days, liquidity=liquidity,
                    url=url, label=f"vendas {what} (n={len(sales)}, {_date_span(sales)})")


def sales_reference(comps: list[dict], url: str, what: str, allow_thin: bool = True) -> SalesRef | None:
    """Janelas do operador → SalesRef ou None (função pura, sem rede).

    Vendas comparáveis de até 180 dias: ≥3 → mediana (das 10 mais recentes),
    ``liquidity="ok"``. Senão, de até 365 dias: ≥3 → ``"low"`` (referência válida,
    marcada baixa-liquidez); 1–2 e ``allow_thin`` → mediana dessas, ``"thin"`` (slab →
    REVISAR; LP passa ``allow_thin=False`` porque exige ≥3); senão None.
    ``what`` é o texto da label ("PSA 9", "CGC 10 Pristine", "LP")."""
    for window, liquidity in ((SALES_MAX_AGE_DAYS, "ok"), (SALES_LOW_LIQUIDITY_MAX_AGE_DAYS, "low")):
        inside = recent_only(comps, window)
        if len(inside) >= MIN_COMPARABLE_SALES:
            return _build_ref(inside, window, liquidity, url, what)
    inside = recent_only(comps, SALES_LOW_LIQUIDITY_MAX_AGE_DAYS)
    if inside and allow_thin:
        return _build_ref(inside, SALES_LOW_LIQUIDITY_MAX_AGE_DAYS, "thin", url, what)
    return None


# --- busca e página da carta ----------------------------------------------------

def search_card_paths(body: str) -> list[str]:
    """Paths ``/game/...`` da página de busca (hrefs vêm ABSOLUTOS desde 2026-08).
    Percent-encoding do slug é desfeito (``team-rocket%27s-mewtwo-ex-231`` →
    ``team-rocket's-mewtwo-ex-231``): sem isso o apóstrofo do nome nunca casa
    (caso real 2026-09-03, Destined Rivals)."""
    paths = re.findall(
        r'href="(?:https?://www\.pricecharting\.com)?(/game/[^"#?]+)"', body)
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        p = urllib.parse.unquote(html_mod.unescape(p))
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# --- guardas de match (adaptadas do CardTrader pricecharting_ref.py) -----------

def norm_number(number) -> str:
    """'006/165' → '6'; '4/102' → '4'; '95b' → '95'; 'SV49' → 'sv49'; 'TG05/TG30' → 'tg5';
    'H09' → 'h9'. O prefixo de letras FAZ PARTE do número (PC: charizard-gx-sv49,
    umbreon-h29, arceus-ar1 — sondagem 2026-09-03); zeros à esquerda caem. Sem dígito → ''."""
    if number is None:
        return ""
    head = re.sub(r"[^a-z0-9]", "", str(number).strip().split("/", 1)[0].lower())
    m = re.match(r"^([a-z]*)0*(\d+)", head)
    return (m.group(1) + m.group(2)) if m else ""


def _norm_token(t: str) -> str:
    t = t.lower().strip()
    if t.endswith("'s"):
        t = t[:-2]
    return t.replace("'", "").replace(".", "")


def clean_card_name(card_name) -> str:
    """Nome TCGCSV → nome comparável: tira ' - 006/165', parênteses e 'Lv.NN'."""
    # " - 006/165" e tambem "-160/091" colado (tcgcsv real: "Mimikyu -160/091").
    s = re.split(r"\s+-\s*", str(card_name or ""), 1)[0]
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\(.*$", "", s)  # parentese sem fechar ("Primal Kyogre EX (Alpha")
    s = re.sub(r"(?i)\blv\.?\s*\d+\b", " ", s)
    return s.strip()


# Grafias do PriceCharting (sondagem real 2026-09-03): "rayquaza-gold-star-107" para
# "Rayquaza Star", "typhlosion-prime-110" para "Typhlosion", "infernape-lvx-108" para
# "Infernape E4 Lv.X" -- tokens opcionais dos DOIS lados; "mega-blastoise-ex" == "M Blastoise EX";
# "lv-x" / "lvx" / "Lv.X" == lvx.
_OPTIONAL_TOKENS = {"gold", "prime", "e4"}
_TOKEN_ALIASES = {"mega": "m"}


def _canon_tokens(tokens) -> list[str]:
    out: list[str] = []
    for t in tokens:
        t = _TOKEN_ALIASES.get(t, t)
        if t == "x" and out and out[-1] == "lv":
            out[-1] = "lvx"
            continue
        out.append(t)
    return [t for t in out if t and t not in _OPTIONAL_TOKENS]


def _name_tokens(card_name) -> list[str]:
    # "." vira separador: "Gengar Lv.X" -> [gengar, lv, x] -> [gengar, lvx].
    name = clean_card_name(card_name).replace(".", " ")
    return _canon_tokens(t for t in (_norm_token(x) for x in re.findall(r"[a-z0-9']+", name.lower())) if t)


# Sets cujo nome TCGCSV nao bate com o console do PriceCharting nem por tokens.
PC_CONSOLE_ALIASES = {
    "SM Base Set": "Sun & Moon",
    "XY Base Set": "XY",
    "SWSH01: Sword & Shield Base Set": "Sword & Shield",
    "SV01: Scarlet & Violet Base Set": "Scarlet & Violet",
}
# Prefixo de serie com hifen ("SM - Unbroken Bonds", "XY - Evolutions") -- sem ':'.
_SERIES_PREFIX = re.compile(r"^(?:SM|XY|SWSH|SV|BW|DP|HGSS)\s+-\s+", re.I)
# Subconjuntos que o PC arquiva no console do set-PAI (sondagem 2026-09-03):
# "Hidden Fates: Shiny Vault" -> pokemon-hidden-fates, "... Trainer Gallery" ->
# pokemon-brilliant-stars, "Celebrations: Classic Collection" -> pokemon-celebrations,
# "Crown Zenith: Galarian Gallery" -> pokemon-crown-zenith, "Radiant Collection" -> pai.
_SUBSET_SUFFIX = re.compile(
    r"(?::\s*(?:Shiny Vault|Galarian Gallery|Classic Collection|Radiant Collection)"
    r"|\s+Trainer Gallery)\s*$", re.I)


def pc_console_label(set_label) -> str:
    """Nome de set TCGCSV → nome do CONSOLE do PriceCharting: aliases dos Base Set de
    série, prefixos/códigos fora, subconjunto → set-pai."""
    raw = str(set_label or "").strip()
    return _SUBSET_SUFFIX.sub("", clean_set_name(PC_CONSOLE_ALIASES.get(raw, raw))).strip()


def clean_set_name(set_label) -> str:
    """'SV: Scarlet & Violet 151' → 'Scarlet & Violet 151'; 'EX Emerald (em)' → 'EX Emerald';
    'SM - Unbroken Bonds' → 'Unbroken Bonds'."""
    s = _SERIES_PREFIX.sub("", _CODE_PREFIX.sub("", str(set_label or "").strip()))
    return s.rsplit(" (", 1)[0].strip() if " (" in s else s


def slug_matches(path: str, card_name, number) -> bool:
    """Slug termina no MESMO número; 1º token = 1º token do nome ('dark-charizard'
    não casa 'Charizard'); tokens do nome == tokens do slug (fora número e
    palavras de variante) — 'charizard-ex-6' não casa 'Charizard' nem vice-versa."""
    parts = path.strip("/").split("/")
    if len(parts) < 3:
        return False
    slug = parts[-1].lower()
    num = norm_number(number)
    raw_tokens = slug.split("-")
    # ultimo token do slug e o numero, comparado canonizado (tg04 == TG4, sv49 != 49)
    if not num or len(raw_tokens) < 2 or norm_number(raw_tokens[-1]) != num:
        return False
    # "&" do PC ("mewtwo-&-mew-gx-242") nao e token de nome
    slug_tokens = _canon_tokens(t for t in (_norm_token(t) for t in raw_tokens[:-1])
                                if re.search(r"[a-z0-9]", t))
    tokens = _name_tokens(card_name)
    if not tokens or not slug_tokens:
        return False
    # 1o token igual ("shadowless-charizard" != "Charizard"), exceto Tag Team, em que o PC
    # inverte a ordem ("psyduck-&-slowpoke-gx-217" para "Slowpoke & Psyduck GX")
    if slug_tokens[0] != tokens[0] and "&" not in str(card_name):
        return False
    core = {t for t in slug_tokens if t and t not in _VARIANT_TOKENS}
    return core == set(tokens)


def console_matches(path: str, set_label) -> bool:
    """Console do path (/game/{console}/{carta}) == tokens do set (sem 'pokemon',
    sem o prefixo 'EX'); bidirecional — 'pokemon-japanese-base-set' NÃO casa 'Base Set'."""
    parts = path.strip("/").split("/")
    if len(parts) < 3:
        return False
    noise = {"pokemon", "ex", "vs", "and", "the"}
    console_list = [t for t in (re.sub(r"[^a-z0-9]", "", x)
                                for x in parts[1].lower().split("-")) if t and t not in noise]
    # aliases dos Base Set de serie + subconjunto -> console do set-pai
    set_list = [t for t in re.findall(r"[a-z0-9]+", pc_console_label(set_label).lower())
                if t not in noise]
    if not set_list:
        return False
    if set(console_list) == set(set_list):
        return True
    # Tolerancia real (build_watchlist 2026-09-03): PC escreve "fire-red-&-leaf-green"
    # e "team-magma-&-team-aqua" para "EX FireRed & LeafGreen" / "EX Team Magma vs
    # Team Aqua" -- comparar o texto colado (sem separadores) resolve os dois sem
    # afrouxar idioma/edicao ("japanese-base-set" e "base-set-2" seguem fora).
    return "".join(console_list) == "".join(set_list)


def choose_path(paths: list[str], card_name, number, set_label) -> str | None:
    matches = [p for p in paths if slug_matches(p, card_name, number)
               and console_matches(p, set_label)]
    matches = [p for p in matches if "reverse" not in p.rsplit("/", 1)[-1].lower()]
    if not matches:
        return None
    return min(matches, key=lambda p: len(p.rsplit("/", 1)[-1]))


# dono com uma OU duas palavras: "Team Aqua's Kyogre", "Lt. Surge's Electabuzz"
_OWNER_PREFIX = re.compile(r"^(?:\w[\w.]*\s+)?[\w.]+'s\s+", re.I)


def _product_path(card_name, number, set_label, cache_dir: str | None = None) -> str | None:
    """Busca (nome+número+set) → ``choose_path`` (match exato) → path ``/game/...`` ou
    None. Rede/bloqueio → ``PcError``."""
    set_name = pc_console_label(set_label)
    base_name = clean_card_name(card_name)
    num = norm_number(number)
    head = str(number or "").strip().split("/", 1)[0].strip()
    # numero com letras vai cru na busca ("SV49", "TG04", "H29": 1 resultado exato);
    # so digitos continua canonizado ("006/165" -> "6", cache do dia intacto)
    qnum = head if re.match(r"^[A-Za-z]", head) else num
    query = " ".join(p for p in ("pokemon", set_name, base_name, qnum) if p)
    body = fetch_page(f"{BASE_URL}/search-products?q={urllib.parse.quote(query)}&type=prices",
                      cache_dir=cache_dir)
    paths = search_card_paths(body)
    path = choose_path(paths, card_name, number, set_label)
    if not path:
        # PC omite o dono em sets so de cartas "de alguem" ("kyogre-3" para "Team Aqua's
        # Kyogre", EX Team Magma vs Team Aqua). So como 2a tentativa, mesmo console+numero.
        stripped = _OWNER_PREFIX.sub("", base_name)
        if stripped != base_name:
            path = choose_path(paths, stripped, number, set_label)
    if not path:
        log.info("PC: sem página que case '%s' #%s (%s).", base_name, num, set_name)
    return path


def _product_page(card_name, number, set_label, cache_dir: str | None = None) -> tuple[str, str] | None:
    """Busca (nome+número+set) → ``choose_path`` (match exato, como sempre) → (url, html
    da página da carta), ou None quando nenhum resultado casa. Rede/bloqueio, ou página
    que carregou sem NENHUMA tabela de preço/vendas (layout mudou, bloqueio disfarçado)
    → ``PcError``: é erro de fonte, não "carta sem vendas"."""
    path = _product_path(card_name, number, set_label, cache_dir=cache_dir)
    if not path:
        return None
    url = BASE_URL + path
    page = fetch_page(url, cache_dir=cache_dir)
    if not parse_grade_prices(page) and not parse_sales(page):
        raise PcError(f"PriceCharting sem tabelas de preço/vendas em {url} (layout mudou?)")
    return url, page


# --- API usada pelo pipeline ---------------------------------------------------

def product_page_url(card_name, number, set_label, cache_dir: str | None = None) -> str | None:
    """URL da página EXATA da carta no PriceCharting (mesmo match nome+número+set dos
    slabs) — usada como link `[referência]` das cartas soltas (operador 2026-09-02: a
    página do PC é mais informativa: vendas eBay, gráfico, PSA 10/9). O PREÇO raw continua
    sendo o TCGplayer market. Sem match → None (o link cai no TCGplayer); PcError propaga."""
    # Só o path: uma página casada SEM tabelas (lançamento recente) ainda é link válido —
    # o check de tabelas de `_product_page` é para quem precisa de VENDAS (slab/LP).
    path = _product_path(card_name, number, set_label, cache_dir=cache_dir)
    return BASE_URL + path if path else None


def graded_reference(card_name, number, set_label, grade, cache_dir: str | None = None,
                     variants: frozenset[str] = frozenset(),
                     column_key: str | None = None) -> SalesRef | None:
    """Nome+número+set+nota → SalesRef (mediana de vendas da MESMA certificadora + nota +
    subcategoria + variante) ou None — nunca inventa. ``grade`` é qualquer objeto com
    ``grader`` (str), ``value`` (float), ``qualifier`` (str: "" / "PRISTINE" / "GEM" /
    "BLACK") e ``label`` (str, texto da entrega). ``variants`` = ``variant_tokens`` da
    listagem. ``column_key`` é a chave da coluna EXATA da nota no PriceCharting ("PSA 10",
    "BGS 10 BLACK", "CGC 10"…): quando a página a tem, vai em ``column_price`` SÓ como
    informação; None (nota sem coluna própria) → ``column_price`` None. Com 0 vendas
    comparáveis devolve None mesmo que a coluna exista (caso Luxray). 1–2 vendas →
    ``liquidity="thin"`` (REVISAR)."""
    found = _product_page(card_name, number, set_label, cache_dir)
    if found is None:
        return None
    url, page = found
    comps = comparable_sales(parse_sales(page), grade.grader, grade.value, grade.qualifier, variants)
    ref = sales_reference(comps, url, grade.label, allow_thin=True)
    if ref is None:
        log.info("PC: %s #%s sem vendas comparáveis de %s%s em %d dias (%d fora da janela).",
                 clean_card_name(card_name), norm_number(number), grade.label,
                 f" {sorted(variants)}" if variants else "", SALES_LOW_LIQUIDITY_MAX_AGE_DAYS, len(comps))
        return None
    column = parse_grade_prices(page).get(column_key) if column_key else None
    if column is not None and column > 0:
        ref = dataclasses.replace(ref, column_price=float(column))
    return ref


def raw_condition_reference(card_name, number, set_label, condition: str = "LP",
                            cache_dir: str | None = None,
                            variants: frozenset[str] = frozenset()) -> SalesRef | None:
    """Carta SOLTA em condição LP → SalesRef (mediana de ≥3 vendas cujo título diz LP /
    Lightly Played, sem nota nem outra condição, mesma variante) ou None. Só "LP" é
    suportado (ValueError para outra condição: NM vem do TCGplayer). LP nunca
    aceita amostra "thin" (1–2 vendas): sem ≥3 vendas não há referência."""
    if condition != "LP":
        raise ValueError(f"raw_condition_reference: só 'LP' é suportado (recebido {condition!r})")
    found = _product_page(card_name, number, set_label, cache_dir)
    if found is None:
        return None
    url, page = found
    comps = lp_sales(parse_sales(page), variants)
    ref = sales_reference(comps, url, "LP", allow_thin=False)
    if ref is None:
        log.info("PC: %s #%s sem ≥%d vendas LP comparáveis%s em %d dias (%d achadas).",
                 clean_card_name(card_name), norm_number(number), MIN_COMPARABLE_SALES,
                 f" {sorted(variants)}" if variants else "", SALES_LOW_LIQUIDITY_MAX_AGE_DAYS, len(comps))
    return ref
