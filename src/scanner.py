"""Orquestracao: watchlist -> referencias da carta -> anuncios -> avaliacao -> funil.

Por carta (padrao COMC, 2026-09-03):
1. UMA pagina do PriceCharting (`pc_sales.fetch_page`, cache do dia) alimenta
   tanto as colunas/tendencia (`pricecharting.parse_product_page`, so informacao)
   quanto as vendas concluidas (`CardRefs`: mediana por certificadora+nota+
   variante para slabs; vendas LP para raw LP). Fonte falhou -> `PcError` ->
   contado no funil (`pc_error`) e, apos `PC_MAX_CONSECUTIVE_ERRORS` falhas
   seguidas, o breaker suspende a fonte (`pc_breaker`) em vez de martelar o site.
2. Referencia TCGplayer (tcgcsv) da carta raw EN (`tcg_reference`).
3. Browse API: UMA busca generica por carta, paginada (`limit` 200 x `max_pages`),
   so preco fixo, so EUA; dedupe por id E por titulo+preco.
4. `scorer.evaluate` por anuncio, com `stats` (Counter) recebendo o motivo de
   cada anuncio que nao vira linha -- nada some em silencio.

Erro por carta e CONTADO (`card_error`, `ebay_error`) e logado, nunca engolido;
falha de autenticacao no eBay ou erros seguidos da API ABORTAM o run
(`aborted=True`, exit != 0 no main) -- um scan parcial nunca passa por completo.
"""
import dataclasses
import logging
import statistics
from collections import Counter

from .models import FairValue, WatchCard
from . import grading, groups, pc_sales, pricecharting, scorer, tcg_reference, title_parser
from .ebay_api import EbayApiError, EbayAuthError, EbayClient

log = logging.getLogger(__name__)

# Se a referencia estiver muito longe da mediana dos anuncios reais da mesma
# grade, a REFERENCIA pode estar errada/defasada (nao o anuncio). Limites:
REF_HIGH_RATIO = 1.5   # ref > 1.5x mediana dos anuncios -> ref pode estar inflada
REF_LOW_RATIO = 0.6    # ref < 0.6x mediana -> ref pode estar defasada pra baixo
REF_MIN_SAMPLES = 3    # minimo de anuncios limpos pra calcular mediana

PC_MAX_CONSECUTIVE_ERRORS = 5    # breaker do PriceCharting
EBAY_MAX_CONSECUTIVE_ERRORS = 3  # erros seguidos da Browse API -> abort

# Sufixos LEGADOS por certificadora (`grade_query_suffixes: true` no config).
# Default 2026-09-03: UMA query generica paginada por carta (200 x max_pages) --
# `sort=price` ja traz os anuncios mais baratos, que sao os que importam.
_COMPANY_SUFFIX = {"PSA": " psa", "BGS": " bgs", "CGC": " cgc", "SGC": " sgc", "TAG": " tag"}
GRADED_ONLY_SUFFIXES = [" psa", " bgs", " cgc", " sgc", " tag"]
GRADE_QUERY_SUFFIXES = [""] + GRADED_ONLY_SUFFIXES


def parse_grades_arg(text, allow=None):
    """'psa10, cgc 10 pristine' -> ['PSA 10', 'CGC 10 PRISTINE']; ValueError alto
    em nota desconhecida/fora da allowlist (typo nunca vira scan vazio)."""
    return grading.parse_grades_arg(text, allow or grading.DEFAULT_GRADED_ALLOW)


def query_suffixes(config):
    """Sufixos de busca do run. Default: so a query generica ([""]). Com
    `grade_query_suffixes: true` (legado) busca por certificadora; com
    `allowed_grades` (--grades) so as certificadoras pedidas."""
    if not config.get("grade_query_suffixes"):
        return [""]
    allowed = config.get("allowed_grades") or []
    graded_only = config.get("graded_only", True)
    if allowed:
        companies = {g.split()[0] for g in allowed if g != "RAW"}
        sfx = [_COMPANY_SUFFIX[c] for c in ("PSA", "BGS", "CGC", "SGC", "TAG")
               if c in companies]
        if not graded_only:
            sfx = [""] + sfx
        return sfx or ([""] if not graded_only else [])
    return GRADED_ONLY_SUFFIXES if graded_only else GRADE_QUERY_SUFFIXES


def load_watchlist(path="watchlist.yaml"):
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    cards = []
    for entry in data.get("cards", []):
        year = entry.get("year")
        cards.append(WatchCard(
            name=entry["name"],
            set_name=entry["set"],
            number=str(entry.get("number", "")),
            language=entry.get("language", "EN"),
            pc_url=entry["pc_url"],
            ebay_query=entry.get("ebay_query", ""),
            exclude_keywords=entry.get("exclude_keywords", []) or [],
            group=str(entry.get("group", "") or ""),
            tcg_set=str(entry.get("tcg_set", "") or ""),
            pokemon=str(entry.get("pokemon", "") or ""),
            pokemon_rank=int(entry.get("pokemon_rank") or 9999),
            rarity=str(entry.get("rarity", "") or ""),
            year=int(year) if year not in (None, "") else None,
        ))
    return cards


def group_counts(cards):
    """Grupos presentes na watchlist -> contagem de cartas (ordem de aparicao).
    Cartas sem `group:` entram no bucket "(sem grupo)"."""
    counts = {}
    for card in cards:
        key = card.group or "(sem grupo)"
        counts[key] = counts.get(key, 0) + 1
    return counts


def filter_group(cards, group):
    """Filtra a watchlist por grupo. `group` vazio/None = todas as cartas;
    spec numerica (``3``, ``5-8``, ``1,3,10-12``, ``all`` -- grupos canonicos de
    ``src/groups.py``) ou nome literal do campo `group:` da watchlist."""
    if not group:
        return cards
    if groups.is_group_spec(group):
        wanted = {str(n) for n in groups.parse_group_arg(group)}
        picked = [c for c in cards if c.group in wanted]
    else:
        picked = [c for c in cards if c.group == group]
    if not picked:
        # typo/grupo ausente erra ALTO -- nunca vira um scan vazio "bem-sucedido"
        present = sorted({c.group for c in cards if c.group}, key=lambda g: (len(g), g))
        raise ValueError(f"grupo {group!r} sem cartas na watchlist "
                         f"(grupos presentes: {', '.join(present) or 'nenhum'})")
    return picked


# --- referencias por vendas (pagina do PriceCharting, 1x por carta) ---------------

class CardRefs:
    """Medianas de vendas comparaveis da pagina da carta no PriceCharting.

    `slab(grade, variants)` -> SalesRef da MESMA certificadora+nota+subcategoria+
    variante (coluna exata da nota vai em `column_price`, so sanidade) ou None;
    `lp(variants)` -> SalesRef de >=3 vendas LP explicitas ou None.
    `available` False = a fonte falhou para a carta (`error`), ou breaker aberto:
    slabs/LP da carta nao sao avaliados (contados como `ref_unavailable`)."""

    def __init__(self, card, body="", url="", error=None):
        self.card = card
        self.url = url or card.pc_url
        self.error = error
        self._body = body or ""
        self._sales = pc_sales.parse_sales(self._body) if self._body else []
        self._columns = pc_sales.parse_grade_prices(self._body) if self._body else {}
        self._memo = {}

    @property
    def available(self):
        return self.error is None and bool(self._body)

    @property
    def pc_url(self):
        return self.url

    @property
    def n_sales(self):
        return len(self._sales)

    def slab(self, grade, variants=frozenset()):
        key = ("slab", grade.key, frozenset(variants))
        if key not in self._memo:
            comps = pc_sales.comparable_sales(self._sales, grade.grader, grade.value,
                                              grade.qualifier, variants)
            ref = pc_sales.sales_reference(comps, self.url, grade.label, allow_thin=True)
            column_key = grading.pc_price_key(grade)
            column = self._columns.get(column_key) if column_key else None
            if ref is not None and column:
                ref = dataclasses.replace(ref, column_price=float(column))
            self._memo[key] = ref
        return self._memo[key]

    def lp(self, variants=frozenset()):
        key = ("lp", frozenset(variants))
        if key not in self._memo:
            comps = pc_sales.lp_sales(self._sales, variants)
            self._memo[key] = pc_sales.sales_reference(comps, self.url, "LP", allow_thin=False)
        return self._memo[key]


class PcBreaker:
    """Circuit breaker do PriceCharting: apos N falhas SEGUIDAS a fonte e suspensa
    no run (cartas seguintes contam `pc_breaker`); um sucesso zera a contagem."""

    def __init__(self, max_errors=PC_MAX_CONSECUTIVE_ERRORS):
        self.max_errors = max_errors
        self.errors = 0
        self.down = False

    def record_error(self):
        self.errors += 1
        if self.errors >= self.max_errors:
            self.down = True

    def record_ok(self):
        self.errors = 0


def load_card_page(card, config=None, stats=None, breaker=None, log=print):
    """(fair, refs) da carta: UMA pagina do PriceCharting. Falha -> `pc_error`
    contado, refs indisponivel (raw NM via TCG ainda e avaliavel)."""
    config = config or {}
    cache_dir = config.get("pc_cache_dir")
    if breaker is not None and breaker.down:
        if stats is not None:
            stats["pc_breaker"] += 1
        return FairValue(source_url=card.pc_url), CardRefs(card, error="breaker aberto")
    try:
        body = pc_sales.fetch_page(card.pc_url, cache_dir=cache_dir)
    except pc_sales.PcError as exc:
        if stats is not None:
            stats["pc_error"] += 1
        if breaker is not None:
            breaker.record_error()
        log(f"  AVISO: PriceCharting falhou para {card.name} #{card.number}: {exc}")
        return FairValue(source_url=card.pc_url), CardRefs(card, error=str(exc))
    if breaker is not None:
        breaker.record_ok()
    fair = pricecharting.parse_product_page(body, source_url=card.pc_url)
    return fair, CardRefs(card, body, card.pc_url)


# --- sanidade: referencia vs mediana dos anuncios ---------------------------------

def _clean_ask_prices(card, listings):
    """Precos pedidos por grade, so de anuncios 'limpos' (carta certa, sem
    acessorio/lote, raw com NM). E a base da mediana usada pra conferir se a
    REFERENCIA esta alinhada com o mercado real do eBay."""
    asks = {}
    for listing in listings:
        if not title_parser.card_matches_title(card, listing.title):
            continue
        grade = title_parser.detect_grade(listing.title)
        if grade is None:
            continue
        tf = title_parser.risk_flags(listing.title)
        if any(f.startswith(("REJEITAR", "LOTE")) for f in tf):
            continue
        if (card.language == "EN"
                and title_parser.jp_nomenclature_hint(listing.title)):
            continue
        if grade == "RAW" and not title_parser.is_nm_acceptable(
                listing.title, listing.condition):
            continue
        asks.setdefault(grade, []).append(listing.price)
    return asks


def _annotate_ref_alignment(opp, asks):
    """Compara a referencia com a mediana dos anuncios da mesma grade."""
    prices = asks.get(opp.grade, [])
    if len(prices) < REF_MIN_SAMPLES:
        return
    median = statistics.median(prices)
    opp.median_ask = round(median, 2)
    if median <= 0:
        return
    ratio = opp.fair_value / median
    if ratio > REF_HIGH_RATIO:
        opp.risk_flags.append(
            f"REF DESALINHADA: referencia e {ratio:.1f}x a mediana de "
            f"{len(prices)} anuncios (${median:,.0f}) -- referencia pode "
            "estar inflada; conferir no link antes de confiar na margem")
        opp.reasons.append(f"ref-desalinhada({ratio:.1f}x)")
        if opp.verdict == "OPORTUNIDADE":
            opp.verdict = "REVISAR"
    elif ratio < REF_LOW_RATIO:
        opp.risk_flags.append(
            f"REF DESALINHADA: referencia e so {ratio:.1f}x a mediana de "
            f"{len(prices)} anuncios (${median:,.0f}) -- referencia pode "
            "estar defasada pra baixo")


# --- scan --------------------------------------------------------------------------

def scan_card(card, ebay, config, log=print, stats=None, breaker=None,
              refs=None, fair=None):
    """Escaneia uma carta da watchlist. Retorna (fair_value, [Opportunity]).
    `refs`/`fair` podem ser injetados (testes); senao vem de `load_card_page`."""
    stats = stats if stats is not None else Counter()
    if refs is None or fair is None:
        fair, refs = load_card_page(card, config, stats=stats, breaker=breaker, log=log)

    tcg_ref = tcg_reference.get_tcg_reference(card)
    if tcg_ref is None and not config.get("graded_only", True):
        log(f"  (sem referencia TCGplayer p/ {card.name} -- raw NM usara "
            "PriceCharting rotulado)")

    calls_before = int(getattr(ebay, "calls", 0) or 0)
    dups_before = int(getattr(ebay, "dedup_dropped", 0) or 0)
    seen_ids = set()
    unique_listings = []
    base_query = card.default_query()
    try:
      for suffix in query_suffixes(config):
        listings = ebay.search(
            base_query + suffix,
            min_price=float(config.get("min_price_usd", 10.0)),
            max_pages=int(config.get("max_pages", 3) or 3),
            # Filtros server-side seguem o config (so preco fixo; so EUA) -- o
            # scorer repete a checagem como cinto de seguranca.
            fixed_price_only=bool(config.get("fixed_price_only", True)),
            location_country=str(config.get("required_location_country", "US") or ""),
        )
        for listing in listings:
            fingerprint = (listing.title.strip().lower(), listing.price)
            # item_id vazio nao identifica nada: se entrasse no set, o 1o
            # anuncio sem id faria TODOS os seguintes sem id sumirem do scan.
            if (listing.item_id and listing.item_id in seen_ids) \
                    or fingerprint in seen_ids:
                stats["dedup_dropped"] += 1
                continue
            if listing.item_id:
                seen_ids.add(listing.item_id)
            seen_ids.add(fingerprint)
            unique_listings.append(listing)
    finally:
        # Cota e duplicados contam mesmo quando a busca estoura no meio.
        stats["ebay_calls"] += max(0, int(getattr(ebay, "calls", 0) or 0) - calls_before)
        stats["dedup_dropped"] += max(0, int(getattr(ebay, "dedup_dropped", 0) or 0) - dups_before)
    stats["seen"] += len(unique_listings)

    asks = _clean_ask_prices(card, unique_listings)

    opportunities = []
    for listing in unique_listings:
        opp = scorer.evaluate(card, listing, fair, config, tcg_ref=tcg_ref,
                              refs=refs, stats=stats)
        if opp is not None:
            _annotate_ref_alignment(opp, asks)
            # Veredito FINAL (apos rebaixamento por referencia desalinhada) e o
            # que conta no funil -- review Codex 2026-09-03.
            stats[scorer.VERDICT_STAT.get(opp.verdict, "rows_review")] += 1
            opportunities.append(opp)

    log(f"  {card.name} #{card.number}: {len(unique_listings)} anuncios vistos, "
        f"{len(opportunities)} acima do desconto minimo"
        + ("" if refs.available else " (PriceCharting indisponivel p/ esta carta)"))
    return fair, opportunities


def run_scan(watchlist_path="watchlist.yaml", config=None, pricing_only=False,
             log=print, group=None):
    """Roda o scan completo. Retorna
    (fair_values, opportunities, pricing_only, stats, aborted).

    `pricing_only` no retorno e o modo EFETIVO do run (True tambem quando
    degradou por falta de EBAY_CLIENT_ID/SECRET). `stats` e o funil (Counter);
    `aborted` True quando o run parou antes do fim (autenticacao eBay,
    `EBAY_MAX_CONSECUTIVE_ERRORS` erros seguidos da API) -- o caller NAO pode
    tratar o resultado como scan completo."""
    config = config or {}
    cards = filter_group(load_watchlist(watchlist_path), group)
    stats = Counter()
    stats["cards"] = len(cards)
    if group:
        log(f"Watchlist (grupo '{group}'): {len(cards)} cartas")
        if not cards:
            log(f"AVISO: nenhum card no grupo '{group}' -- confira "
                "`python main.py --list-groups`")
    else:
        log(f"Watchlist: {len(cards)} cartas")

    ebay = None
    if not pricing_only:
        ebay = EbayClient()
        if not ebay.configured:
            log("EBAY_CLIENT_ID/SECRET ausentes -> rodando em modo pricing-only.")
            log("(Setup gratis em ~5 min: veja README.md, secao 'Chaves do eBay'.)")
            pricing_only = True

    breaker = PcBreaker()
    fair_values = {}
    all_opportunities = []
    aborted = False
    ebay_errors_in_a_row = 0
    for card in cards:
        try:
            if pricing_only:
                fair, _ = load_card_page(card, config, stats=stats, breaker=breaker, log=log)
                fair_values[(card.name, card.number)] = (card, fair)
                log(f"  preco de referencia OK: {card.name} #{card.number}")
            else:
                fair, opps = scan_card(card, ebay, config, log=log, stats=stats,
                                       breaker=breaker)
                fair_values[(card.name, card.number)] = (card, fair)
                all_opportunities.extend(opps)
                ebay_errors_in_a_row = 0
        except EbayAuthError as e:
            log(f"ERRO de autenticacao eBay: {e} -- RUN ABORTADO")
            stats["aborted"] = 1
            aborted = True
            break
        except EbayApiError as e:
            stats["ebay_error"] += 1
            ebay_errors_in_a_row += 1
            log(f"  ERRO na Browse API em {card.name} #{card.number}: {e}")
            if ebay_errors_in_a_row >= EBAY_MAX_CONSECUTIVE_ERRORS:
                log(f"ERRO: {ebay_errors_in_a_row} falhas seguidas da Browse API -- "
                    "RUN ABORTADO (cartas restantes nao varridas)")
                stats["aborted"] = 1
                aborted = True
                break
        except Exception as e:  # noqa: BLE001 -- contado e logado, nunca engolido
            stats["card_error"] += 1
            log(f"  ERRO em {card.name} #{card.number}: {type(e).__name__}: {e} "
                "-- carta pulada (contada no funil)")
    return fair_values, all_opportunities, pricing_only, stats, aborted
