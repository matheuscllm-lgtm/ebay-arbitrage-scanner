from src import report
from src.models import WatchCard, Listing, Opportunity


CARD = WatchCard(name="Umbreon VMAX", set_name="Evolving Skies", number="215",
                 language="EN", pc_url="https://www.pricecharting.com/g/p/x",
                 pokemon="Umbreon", pokemon_rank=4)


def L(url="https://ebay.com/itm/123"):
    return Listing(item_id="x", title="t", price=1000.0, shipping=0.0,
                   currency="USD", buying_option="FIXED_PRICE",
                   condition="Graded", seller_feedback_pct=99.9,
                   seller_feedback_score=900, url=url)


def O(ebay_url="https://ebay.com/itm/123", ref_url="https://pricecharting.com/g/p/x",
      **kw):
    base = dict(card=CARD, listing=L(ebay_url), grade="PSA 10", fair_value=1500.0,
                gross_margin_pct=50.0, liquidity_per_month=30.0, liquidity_tier="A",
                trend_delta=0.0, spread_psa9_pct=0, spread_psa10_pct=0,
                verdict="OPORTUNIDADE", fair_value_source=ref_url, pc_url=ref_url,
                discount_pct=33.33, spread_usd=500.0, ref_source="pricecharting-sales",
                ref_label="vendas PSA 10 (n=5, 2026-03..2026-08)", ref_n_sales=5,
                ref_liquidity="ok", listing_type="PSA 10", grade_label="PSA 10")
    base.update(kw)
    return Opportunity(**base)


def test_links_single_combined_column():
    md = report.to_markdown([O()])
    header = md.splitlines()[0]
    assert "| Links |" in header
    assert "Anuncio" not in header
    assert "Referencia" not in header


def test_links_cell_has_both_sublinks():
    md = report.to_markdown([O(ebay_url="https://ebay.com/itm/99",
                               ref_url="https://pricecharting.com/g/p/y")])
    assert "[oferta](https://ebay.com/itm/99)" in md
    assert "[referência](https://pricecharting.com/g/p/y)" in md
    assert "·" in md


def test_links_missing_both_renders_dash():
    md = report.to_markdown([O(ebay_url="", ref_url="", tcg_url="")])
    assert "| — |" in md


def test_links_percent_encode_parentheses_and_spaces():
    cell = report.links_cell("https://e.com/itm/a (b) c", "https://p.com/x%20y")
    assert cell == ("[oferta](https://e.com/itm/a%20%28b%29%20c) · "
                    "[referência](https://p.com/x%20y)")


def test_reference_link_prefers_pricecharting_page_even_for_tcg_margin():
    o = O(ref_source="tcgplayer", ref_kind="tcgplayer", tcg_market=1500.0,
          tcg_url="https://www.tcgplayer.com/product/1")
    assert report.reference_link(o) == ("https://pricecharting.com/g/p/x", "referência")
    o2 = O(ref_url="", pc_url="", ref_source="tcgplayer", ref_kind="tcgplayer",
           tcg_url="https://www.tcgplayer.com/product/1")
    assert report.reference_link(o2) == ("https://www.tcgplayer.com/product/1", "TCG")


def test_sorted_by_roi_descending():
    low = O(gross_margin_pct=10.0, discount_pct=9.09)
    high = O(gross_margin_pct=90.0, discount_pct=47.37)
    md = report.to_markdown([low, high])
    assert md.index("| 90.00 |") < md.index("| 10.00 |")


def test_compute_metrics():
    assert report.compute_metrics(100.0, 75.0) == (25.0, 33.33, 25.0)
    d, r, s = report.compute_metrics(0.0, 75.0)
    assert d == float("-inf") and s == -75.0


def test_opportunity_row_carries_comc_fields():
    row = report.opportunity_row(O())
    for key in ("discount_pct", "roi_pct", "spread_usd", "ref_source", "ref_label",
                "ref_n_sales", "ref_liquidity", "pc_url", "listing_type", "pokemon",
                "pokemon_rank", "reasons"):
        assert key in row
    assert row["roi_pct"] == 50.0 and row["margin_pct"] == 50.0
    assert row["pc_url"] == "https://pricecharting.com/g/p/x"


def test_scan_payload_has_funnel_and_rows_ranked():
    low = O(gross_margin_pct=10.0)
    high = O(gross_margin_pct=90.0)
    payload = report.scan_payload([low, high], watchlist_count=1,
                                  config={"min_discount_percent": 20,
                                          "graded_allow": {"PSA 10", "PSA 9"}},
                                  funnel={"seen": 3}, aborted=False)
    assert payload["meta"]["funnel"] == {"seen": 3}
    assert payload["meta"]["config"]["min_discount_percent"] == 20
    assert payload["meta"]["config"]["graded_allow"] == ["PSA 10", "PSA 9"]
    assert [r["roi_pct"] for r in payload["rows"]] == [90.0, 10.0]


def test_funnel_lines_known_and_unknown_keys():
    lines = report.funnel_lines({"seen": 10, "skip_not_fixed_price": 2, "weird": 1, "zero": 0})
    assert lines[0].startswith("Anúncios analisados")
    assert any("leilão" in line and ": 2" in line for line in lines)
    assert "outros: weird=1" in lines[-1]
