"""Orquestracao: watchlist -> preco justo -> anuncios -> avaliacao."""
import sys

from .models import WatchCard
from . import pricecharting, scorer
from .ebay_api import EbayClient, EbayAuthError

# Sufixos de busca por grade: uma query generica acha raw + graded juntos,
# mas queries dedicadas a PSA/BGS/CGC melhoram o recall de slabs baratos.
GRADE_QUERY_SUFFIXES = ["", " psa", " bgs", " cgc"]


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
        ))
    return cards


def scan_card(card, ebay, config, log=print):
    """Escaneia uma carta da watchlist. Retorna (fair_value, [Opportunity])."""
    fair = pricecharting.get_fair_value(card.pc_url)
    if not fair.prices:
        log(f"  AVISO: sem precos no PriceCharting para {card.name} ({card.pc_url})")
        return fair, []

    seen_ids = set()
    seen_count = 0
    opportunities = []
    base_query = card.default_query()
    for suffix in GRADE_QUERY_SUFFIXES:
        listings = ebay.search(
            base_query + suffix,
            min_price=float(config.get("min_price_usd", 10.0)),
        )
        for listing in listings:
            # Dedupe por id E por (titulo, preco): anuncios multi-variacao do
            # eBay voltam com itemId diferente por variacao, mesmo conteudo.
            fingerprint = (listing.title.strip().lower(), listing.price)
            if listing.item_id in seen_ids or fingerprint in seen_ids:
                continue
            seen_ids.add(listing.item_id)
            seen_ids.add(fingerprint)
            seen_count += 1
            opp = scorer.evaluate(card, listing, fair, config)
            if opp is not None:
                opp.fair_value_source = fair.source_url
                opportunities.append(opp)
    log(f"  {card.name} #{card.number}: {seen_count} anuncios vistos, "
        f"{len(opportunities)} acima do threshold")
    return fair, opportunities


def run_scan(watchlist_path="watchlist.yaml", config=None, pricing_only=False,
             log=print):
    """Roda o scan completo. Retorna (fair_values, opportunities)."""
    config = config or {}
    cards = load_watchlist(watchlist_path)
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
                fair_values[card.name + card.number] = (
                    card, pricecharting.get_fair_value(card.pc_url))
                log(f"  preco justo OK: {card.name} #{card.number}")
            else:
                fair, opps = scan_card(card, ebay, config, log=log)
                fair_values[card.name + card.number] = (card, fair)
                all_opportunities.extend(opps)
        except EbayAuthError as e:
            log(f"ERRO de autenticacao eBay: {e}")
            sys.exit(2)
        except Exception as e:
            log(f"  ERRO em {card.name} #{card.number}: {e} -- seguindo adiante")
    return fair_values, all_opportunities
