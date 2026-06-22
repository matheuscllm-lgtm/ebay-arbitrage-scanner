from src import report
from src.models import WatchCard, Listing, Opportunity


CARD = WatchCard(name="Umbreon VMAX", set_name="Evolving Skies", number="215",
                 language="EN", pc_url="")


def L(url="https://ebay.com/itm/123"):
    return Listing(item_id="x", title="t", price=1000.0, shipping=0.0,
                   currency="USD", buying_option="FIXED_PRICE",
                   condition="PSA 10", seller_feedback_pct=99.9,
                   seller_feedback_score=900, url=url)


def O(ebay_url="https://ebay.com/itm/123", ref_url="https://pricecharting.com/g/p/x"):
    return Opportunity(card=CARD, listing=L(ebay_url), grade="PSA 10",
                       fair_value=1500.0, gross_margin_pct=50.0,
                       liquidity_per_month=30.0, liquidity_tier="A",
                       trend_delta=0.0, spread_psa9_pct=0, spread_psa10_pct=0,
                       verdict="OPORTUNIDADE", fair_value_source=ref_url)


def test_links_single_combined_column():
    md = report.to_markdown([O()])
    header = md.splitlines()[0]
    # Coluna canonica unica "Links" (cross-scanner), sem colunas separadas
    assert "| Links |" in header
    assert "Anuncio" not in header
    assert "Referencia" not in header


def test_links_cell_has_both_sublinks():
    md = report.to_markdown([O(ebay_url="https://ebay.com/itm/99",
                               ref_url="https://pricecharting.com/g/p/y")])
    assert "[oferta](https://ebay.com/itm/99)" in md
    assert "[referência](https://pricecharting.com/g/p/y)" in md
    assert "·" in md  # separador canonico


def test_links_missing_side_renders_dash():
    md = report.to_markdown([O(ebay_url="", ref_url="")])
    # ambos os lados ausentes -> em-dash em cada lado, ainda combinados
    assert "— · —" in md


def test_sorted_by_score_descending():
    low = O()
    low.score = 10.0
    high = O()
    high.score = 90.0
    md = report.to_markdown([low, high])
    body = md.splitlines()[2:]
    assert body[0].count("| 90 |") or "| 90 " in body[0]
    # a linha de maior score vem primeiro
    assert md.index("| 90") < md.index("| 10")
