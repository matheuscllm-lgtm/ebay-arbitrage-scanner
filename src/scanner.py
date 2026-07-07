"""Orquestracao: watchlist -> preco justo -> anuncios -> avaliacao."""
import statistics
import sys

from .models import WatchCard
from . import pricecharting, scorer, tcg_reference, title_parser
from .ebay_api import EbayClient, EbayAuthError

# Se o preco justo estiver muito longe da mediana dos anuncios reais da mesma
# grade, a REFERENCIA pode estar errada/defasada (nao o anuncio). Limites:
REF_HIGH_RATIO = 1.5   # justo > 1.5x mediana dos anuncios -> ref pode estar inflada
REF_LOW_RATIO = 0.6    # justo < 0.6x mediana -> ref pode estar defasada pra baixo
REF_MIN_SAMPLES = 3    # minimo de anuncios limpos pra calcular mediana

# Sufixos de busca por grade: uma query generica acha raw + graded juntos,
# mas queries dedicadas a PSA/BGS/CGC melhoram o recall de slabs baratos.
GRADE_QUERY_SUFFIXES = ["", " psa", " bgs", " cgc"]
# Em modo graded-only a query generica so traria raw (descartado) -- buscar
# direto por empresa de grading rende mais slabs por pagina.
GRADED_ONLY_SUFFIXES = [" psa", " bgs", " cgc"]


def load_watchlist(path="watchlist.yaml"):
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    cards = []
    for entry in data.get("cards", []):
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
    """Filtra a watchlist por grupo. `group` vazio/None = todas as cartas."""
    if not group:
        return cards
    return [c for c in cards if c.group == group]


def _clean_ask_prices(card, listings):
    """Precos pedidos por grade, so de anuncios 'limpos' (carta certa, sem
    acessorio/lote, raw com NM). E a base da mediana usada pra conferir se a
    REFERENCIA (PriceCharting) esta alinhada com o mercado real do eBay."""
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
        if grade == "RAW" and not title_parser.is_nm_acceptable(
                listing.title, listing.condition):
            continue
        asks.setdefault(grade, []).append(listing.price)
    return asks


def _annotate_ref_alignment(opp, asks):
    """Compara o preco justo com a mediana dos anuncios da mesma grade."""
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
            f"REF DESALINHADA: preco justo e {ratio:.1f}x a mediana de "
            f"{len(prices)} anuncios (${median:,.0f}) -- referencia pode "
            "estar inflada; conferir no link antes de confiar na margem")
        if opp.verdict == "OPORTUNIDADE":
            opp.verdict = "REVISAR"
    elif ratio < REF_LOW_RATIO:
        opp.risk_flags.append(
            f"REF DESALINHADA: preco justo e so {ratio:.1f}x a mediana de "
            f"{len(prices)} anuncios (${median:,.0f}) -- referencia pode "
            "estar defasada pra baixo")


def scan_card(card, ebay, config, log=print):
    """Escaneia uma carta da watchlist. Retorna (fair_value, [Opportunity])."""
    fair = pricecharting.get_fair_value(card.pc_url)
    if not fair.prices:
        log(f"  AVISO: sem precos no PriceCharting para {card.name} ({card.pc_url})")
        return fair, []

    # Referencia TCGplayer (tcgcsv) da carta: principal para RAW, sanity check
    # para graded. Tolerante a falha (None) -- o scan nunca quebra por isto, e
    # sem TCG o raw cai no fallback PriceCharting ROTULADO (nunca silencioso).
    tcg_ref = tcg_reference.get_tcg_reference(card)
    if tcg_ref is None:
        log(f"  (sem referencia TCGplayer p/ {card.name} -- raw usara "
            "PriceCharting rotulado; graded segue PriceCharting normal)")

    # 1) Coleta com dedupe (por id E por titulo+preco: anuncios multi-variacao
    #    do eBay voltam com itemId diferente por variacao, mesmo conteudo).
    seen_ids = set()
    unique_listings = []
    base_query = card.default_query()
    suffixes = (GRADED_ONLY_SUFFIXES if config.get("graded_only", True)
                else GRADE_QUERY_SUFFIXES)
    for suffix in suffixes:
        listings = ebay.search(
            base_query + suffix,
            min_price=float(config.get("min_price_usd", 10.0)),
        )
        for listing in listings:
            fingerprint = (listing.title.strip().lower(), listing.price)
            # item_id vazio nao identifica nada: se entrasse no set, o 1o
            # anuncio sem id faria TODOS os seguintes sem id sumirem do scan.
            if (listing.item_id and listing.item_id in seen_ids) \
                    or fingerprint in seen_ids:
                continue
            if listing.item_id:
                seen_ids.add(listing.item_id)
            seen_ids.add(fingerprint)
            unique_listings.append(listing)

    # 2) Mediana de mercado por grade (sanity check da referencia).
    asks = _clean_ask_prices(card, unique_listings)

    # 3) Avaliacao.
    opportunities = []
    for listing in unique_listings:
        opp = scorer.evaluate(card, listing, fair, config, tcg_ref=tcg_ref)
        if opp is not None:
            opp.fair_value_source = fair.source_url
            _annotate_ref_alignment(opp, asks)
            opportunities.append(opp)

    log(f"  {card.name} #{card.number}: {len(unique_listings)} anuncios vistos, "
        f"{len(opportunities)} acima do threshold")
    return fair, opportunities


def run_scan(watchlist_path="watchlist.yaml", config=None, pricing_only=False,
             log=print, group=None):
    """Roda o scan completo. Retorna (fair_values, opportunities).

    `group`: nome de um grupo da watchlist (campo `group:` por carta) para
    escanear so aquele subconjunto; None/vazio = todas as cartas."""
    config = config or {}
    cards = filter_group(load_watchlist(watchlist_path), group)
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

    fair_values = {}
    all_opportunities = []
    for card in cards:
        try:
            if pricing_only:
                fair_values[(card.name, card.number)] = (
                    card, pricecharting.get_fair_value(card.pc_url))
                log(f"  preco justo OK: {card.name} #{card.number}")
            else:
                fair, opps = scan_card(card, ebay, config, log=log)
                fair_values[(card.name, card.number)] = (card, fair)
                all_opportunities.extend(opps)
        except EbayAuthError as e:
            log(f"ERRO de autenticacao eBay: {e}")
            sys.exit(2)
        except Exception as e:
            log(f"  ERRO em {card.name} #{card.number}: {e} -- seguindo adiante")
    return fair_values, all_opportunities
