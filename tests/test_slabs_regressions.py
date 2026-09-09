"""Slab-only scope and regressions from the second-opinion review."""
import dataclasses
from collections import Counter

import pytest

import main
from src import ebay_api, grading, pc_sales, report, scanner, scorer, title_parser
from src.models import FairValue
from tests.test_ebay_api import _item, _page
from tests.test_scan_funnel import CARD, FakeEbay, L
from tests.test_scorer import FakeRefs, REF


@pytest.mark.parametrize("title", [
    "Charizard 4/102 Pristine CGC 10",
    "Charizard 4/102 CGC Pristine 10",
    "Charizard 4/102 CGC 10 Pristine",
])
def test_cgc_pristine_uses_same_parser_for_listing_and_sale(title):
    result = grading.grade_from_title(title)
    assert result.grade == grading.Grade("CGC", 10, "PRISTINE")
    sale = {"title": title, "price": 500.0}
    assert pc_sales.comparable_sales([sale], "CGC", 10, "PRISTINE", card=CARD) == [sale]
    assert pc_sales.comparable_sales([sale], "CGC", 10, "GEM", card=CARD) == []


@pytest.mark.parametrize("title", [
    "Blastoise 4/102 PSA 9",
    "Dark Charizard 4/102 PSA 9",
    "Charizard ex 4/102 PSA 9",
    "Charizard 14/102 PSA 9",
    "Charizard PSA 9 pop 4",
    "Charizard 4/102 PSA 9 vs GMA GEM MINT 10",
    "Charizard 4/102 PSA GEM MT 10 vs PSA 9",
])
def test_wrong_card_or_ambiguous_sale_cannot_supply_reference(title):
    assert pc_sales.comparable_sales(
        [{"title": title, "price": 1000.0}], "PSA", 9, card=CARD) == []


def test_card_identity_respects_name_boundaries_and_full_collector_number():
    card = dataclasses.replace(CARD, name="Mew", number="004/102")
    assert title_parser.card_matches_title(card, "Mew #4/102 PSA 9")
    assert not title_parser.card_matches_title(card, "Mewtwo #4/102 PSA 9")
    assert not title_parser.card_matches_title(card, "Mew #4/25 PSA 9")
    assert not title_parser.card_matches_title(card, "Mew PSA 9 pop 4")


def test_card_refs_filters_identity_before_median(monkeypatch):
    sales = [
        {"title": "Charizard 4/102 PSA 9", "price": 100.0},
        {"title": "Blastoise 4/102 PSA 9", "price": 9000.0},
    ]
    monkeypatch.setattr(pc_sales, "parse_sales", lambda body: sales)
    captured = []

    def reference(comps, *args, **kwargs):
        captured.extend(comps)
        return REF(100.0)

    monkeypatch.setattr(pc_sales, "sales_reference", reference)
    refs = scanner.CardRefs(CARD, "<html>fixture</html>")
    assert refs.slab(grading.Grade("PSA", 9)).price == 100.0
    assert captured == sales[:1]


def test_scan_never_fetches_tcg_or_emits_raw_or_auction(monkeypatch):
    monkeypatch.setattr(scanner.tcg_reference, "get_tcg_reference",
                        lambda card: pytest.fail("slab scan must not fetch raw reference"))
    batch = [
        L("Charizard 4/102 PSA 9", 75.0, "slab"),
        L("Charizard 4/102 NM", 10.0, "raw", condition="Ungraded"),
        L("Charizard 4/102 PSA 9", 60.0, "auction", buying_option="AUCTION"),
    ]
    stats = Counter()
    config = {"graded_only": False, "fixed_price_only": False}
    _, rows = scanner.scan_card(CARD, FakeEbay(batch), config, stats=stats,
                                refs=FakeRefs(slab={"PSA 9": REF(100.0)}),
                                fair=FairValue(prices={"RAW": 10000.0}), log=lambda *a: None)
    assert [row.listing.item_id for row in rows] == ["slab"]
    assert rows[0].verdict == "OPORTUNIDADE"
    assert stats["skip_raw"] == stats["skip_not_fixed_price"] == 1
    assert config == {"graded_only": False, "fixed_price_only": False}


@pytest.mark.parametrize("args", [["--include-raw"], ["--grades", "RAW"]])
def test_cli_rejects_raw_before_scanning(args, monkeypatch):
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: pytest.fail("must not scan"))
    with pytest.raises(SystemExit) as exc:
        main.main(args)
    assert exc.value.code != 0


def test_config_cannot_select_raw():
    with pytest.raises(ValueError, match="RAW fora do escopo"):
        scanner.scan_config({"allowed_grades": ["RAW", "PSA 9"]})


@pytest.mark.parametrize("failure", [ebay_api.EbayApiError, ebay_api.EbayAuthError])
def test_partial_pages_are_counted_even_when_request_aborts(monkeypatch, failure):
    client = ebay_api.EbayClient("id", "secret")
    calls = []

    def request(url):
        client.calls += 1
        calls.append(url)
        if client.calls == 2:
            raise failure("failed page two")
        # One duplicate and one invalid price in the full first page.
        items = [_item(str(i)) for i in range(198)]
        items += [_item("0"), dict(_item("broken"), price={"value": "invalid"})]
        return _page(items, total=400)

    monkeypatch.setattr(client, "_request_search_json", request)
    stats = Counter()
    with pytest.raises(failure):
        scanner.scan_card(CARD, client, {}, stats=stats, refs=FakeRefs(),
                          fair=FairValue(), log=lambda *a: None)
    assert stats["fetched"] == 200
    assert stats["dedup_dropped"] == 1
    assert stats["skip_invalid_payload"] == 1
    assert stats["skip_fetch_error"] == stats["seen"] == 198
    assert stats["ebay_calls"] == 2
    assert "conditionIds%3A%7B2750%7D" in calls[0]
    assert stats["fetched"] == sum(stats[k] for k in (
        "dedup_dropped", "skip_invalid_payload", "skip_fetch_error"))


def test_successful_query_is_counted_when_next_query_fails():
    class Client:
        calls = 0

        def search(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise ebay_api.EbayApiError("failed query")
            return [L("Charizard 4/102 PSA 9", 75.0, "1")]

    stats = Counter()
    with pytest.raises(ebay_api.EbayApiError):
        scanner.scan_card(CARD, Client(), {"grade_query_suffixes": True},
                          stats=stats, refs=FakeRefs(), fair=FairValue(), log=lambda *a: None)
    assert stats["skip_fetch_error"] == stats["seen"] == 1


def test_invalid_item_does_not_lose_later_items(monkeypatch):
    client = ebay_api.EbayClient("id", "secret")
    monkeypatch.setattr(client, "_request_search_json", lambda url: _page([
        _item("1"), dict(_item("bad"), price={"value": "oops"}), _item("2")], total=3))
    assert [item.item_id for item in client.search("q")] == ["1", "2"]
    assert client.fetched == 3 and client.parse_dropped == 1


def test_one_evaluation_failure_preserves_other_rows(monkeypatch):
    evaluate = scorer.evaluate

    def sometimes_fails(card, listing, *args, **kwargs):
        if listing.item_id == "broken":
            raise ValueError("bad listing")
        return evaluate(card, listing, *args, **kwargs)

    monkeypatch.setattr(scorer, "evaluate", sometimes_fails)
    stats = Counter()
    batch = [L("Charizard 4/102 PSA 9", price, item_id)
             for price, item_id in [(75, "first"), (74, "broken"), (73, "last")]]
    _, rows = scanner.scan_card(CARD, FakeEbay(batch), {}, stats=stats,
                                refs=FakeRefs(slab={"PSA 9": REF(100)}),
                                fair=FairValue(), log=lambda *a: None)
    assert [row.listing.item_id for row in rows] == ["first", "last"]
    assert stats["skip_evaluation_error"] == 1
    assert stats["seen"] == 3
    assert stats["rows_opportunity"] == 2


@pytest.mark.parametrize("price,eligible", [(80, True), (80.001, False), (79.999, True), (101, False)])
def test_discount_gate_uses_unrounded_value(price, eligible):
    stats = Counter()
    row = scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", price, "1"), FairValue(),
                          refs=FakeRefs(slab={"PSA 9": REF(100)}), stats=stats)
    assert (row is not None) == eligible
    assert stats["below_discount"] == int(not eligible)


@pytest.mark.parametrize("price,eligible", [(80.04, True), (80.041, False)])
def test_discount_boundary_with_decimal_reference(price, eligible):
    row = scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", price, "1"), FairValue(),
                          refs=FakeRefs(slab={"PSA 9": REF(100.05)}))
    assert (row is not None) == eligible


@pytest.mark.parametrize("price", [float("nan"), float("inf"), -1, 0])
def test_invalid_listing_price_never_emits_row(price):
    stats = Counter()
    assert scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", price, "1"), FairValue(),
                           {"min_price_usd": 0}, refs=FakeRefs(), stats=stats) is None
    assert stats["skip_price_floor"] == 1


@pytest.mark.parametrize("price", [float("nan"), float("inf"), -1, 0])
def test_invalid_reference_never_emits_row(price):
    stats = Counter()
    assert scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", 50, "1"), FairValue(),
                           refs=FakeRefs(slab={"PSA 9": REF(price)}), stats=stats) is None
    assert stats["invalid_reference"] == 1
    assert pc_sales.comparable_sales(
        [{"title": "Charizard 4/102 PSA 9", "price": price}], "PSA", 9, card=CARD) == []


def test_legacy_row_with_infinite_rank_does_not_break_report():
    assert report.sort_key({"margin_pct": 20, "pokemon_rank": float("inf")}) == (
        -20, 0, 0, report.UNRANKED)


def test_pricecharting_breaker_opens_on_fifth_consecutive_failure(monkeypatch):
    calls = []

    def fail(url, **kwargs):
        calls.append(url)
        raise pc_sales.PcError("source unavailable")

    monkeypatch.setattr(pc_sales, "fetch_page", fail)
    breaker = scanner.PcBreaker()
    stats = Counter()
    for _ in range(6):
        scanner.load_card_page(CARD, stats=stats, breaker=breaker, log=lambda *a: None)
    assert len(calls) == 5
    assert stats["pc_error"] == 5 and stats["pc_breaker"] == 1
    assert breaker.down
