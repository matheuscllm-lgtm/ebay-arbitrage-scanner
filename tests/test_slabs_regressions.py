"""Regressoes portadas do diff local pre-#29 (branch `wip/local-slabs-diff-2026-09-04`).

Cobrem, sobre a base #31:
- bloco 2 = contadores do funil (contagem de por que cada anuncio foi descartado):
  `fetched`, `skip_invalid_payload`, `skip_fetch_error`, `skip_evaluation_error`;
- bloco 3 = identidade da venda usada na referencia (`comparable_sales(..., card=)`),
  CGC "Pristine" antes da nota, nome com limite de palavra + numero completo,
  preco/referencia nao finitos (`invalid_reference`).

NAO portados (com o porque):
- bloco 1 (escopo "somente slabs" via `scan_config`/`parse_grades_arg`/CLI): o PR #29
  ja cobre o escopo com outro mecanismo (`slab_strategy`, `conditionIds:{2750}`);
- gate em Decimal (aritmetica exata): o gate vigente compara o Desconto% JA
  arredondado a 2 casas (`report.compute_metrics`); com centavos reais um caso de
  fronteira mudaria de lado (ver `test_discount_gate_compares_rounded_percent_today`)
  -> freio (f)7 do prompt: pergunta ao operador, hunk nao portado.
"""
import dataclasses
from collections import Counter

import pytest

from src import ebay_api, grading, pc_sales, report, scanner, scorer, title_parser
from src.models import FairValue
from tests.test_ebay_api import _item, _page
from tests.test_scan_funnel import CARD, FakeEbay, L, no_tcg  # noqa: F401 (fixture)
from tests.test_scorer import FakeRefs, REF


# ── bloco 3: identidade da venda / nota (so caminho legado) ───────────────────

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
    "Blastoise 4/102 PSA 9",                        # outra carta
    "Dark Charizard 4/102 PSA 9",                   # prefixo muda a carta
    "Charizard ex 4/102 PSA 9",                     # sufixo muda a carta
    "Charizard 14/102 PSA 9",                       # outro numero
    "Charizard PSA 9 pop 4",                        # "pop 4" nao e numero de carta
    "Charizard 4/102 PSA 9 vs GMA GEM MINT 10",     # outra certificadora junto
    "Charizard 4/102 PSA GEM MT 10 vs PSA 9",       # duas notas (ambiguo)
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


def test_card_identity_with_empty_name_checks_only_number_and_exclusions():
    """`slab_strategy.identity_matches` chama com `name=''` e confere o nome por
    conta propria: o porte nao pode devolver False so por falta de nome."""
    card = dataclasses.replace(CARD, name="", number="4")
    assert title_parser.card_matches_title(card, "Charizard 4/102 Base Set PSA 9")
    assert not title_parser.card_matches_title(card, "Charizard 14/102 Base Set PSA 9")
    card = dataclasses.replace(card, exclude_keywords=["celebrations"])
    assert not title_parser.card_matches_title(card, "Charizard 4/102 Celebrations PSA 9")


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


# ── bloco 2: funil da coleta (nada some em silencio) ─────────────────────────

@pytest.mark.parametrize("failure", [ebay_api.EbayApiError, ebay_api.EbayAuthError])
def test_partial_pages_are_counted_even_when_request_aborts(monkeypatch, no_tcg, failure):
    client = ebay_api.EbayClient("id", "secret")

    def request(url):
        client.calls += 1
        if client.calls == 2:
            raise failure("failed page two")
        # Pagina cheia: 198 unicos + 1 repetido + 1 com estrutura ilegivel.
        items = [_item(str(i)) for i in range(198)]
        items += [_item("0"), dict(_item("broken"), price="nao-e-um-objeto")]
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
    assert stats["fetched"] == sum(stats[k] for k in (
        "dedup_dropped", "skip_invalid_payload", "skip_fetch_error"))


def test_successful_query_is_counted_when_next_query_fails(no_tcg):
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
        _item("1"), dict(_item("bad"), price="nao-e-um-objeto"), _item("2")], total=3))
    assert [item.item_id for item in client.search("q")] == ["1", "2"]
    assert client.fetched == 3 and client.parse_dropped == 1


def test_unreadable_price_is_kept_as_none_and_counted_at_the_floor(monkeypatch, no_tcg):
    """Valor de preco ilegivel vira `price=None` (comportamento de #31, nao e
    descarte na coleta): no caminho legado conta no piso, nunca vira linha nem
    erro de avaliacao."""
    client = ebay_api.EbayClient("id", "secret")
    monkeypatch.setattr(client, "_request_search_json", lambda url: _page([
        dict(_item("x"), title="Charizard 4/102 PSA 9", price={"value": "oops"})], total=1))
    listings = client.search("q")
    assert [lst.price for lst in listings] == [None] and client.parse_dropped == 0
    stats = Counter()
    _, rows = scanner.scan_card(CARD, FakeEbay(listings), {}, stats=stats,
                                refs=FakeRefs(slab={"PSA 9": REF(100.0)}),
                                fair=FairValue(), log=lambda *a: None)
    assert rows == []
    assert stats["skip_price_floor"] == 1 and stats["skip_evaluation_error"] == 0


def test_one_evaluation_failure_preserves_other_rows(monkeypatch, no_tcg):
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


def test_run_scan_marks_evaluation_errors_as_partial(tmp_path, monkeypatch):
    """Erro interno ao avaliar um anuncio conta no funil E marca o run como
    parcial (`aborted=True`), como ja acontecia quando o mesmo erro derrubava a
    carta inteira (`card_error`): cobertura parcial nunca passa por completa."""
    from tests.test_scan_funnel import _patch_scan_card, _watchlist

    def behaviour(card, stats):
        if card.name == "Blastoise":
            stats["skip_evaluation_error"] += 1
        return FairValue(), []

    _patch_scan_card(monkeypatch, behaviour)
    _, _, _, stats, aborted = scanner.run_scan(
        watchlist_path=_watchlist(tmp_path), log=lambda *a, **k: None)
    assert aborted is True and stats["aborted"] == 1
    assert stats["skip_evaluation_error"] == 1 and stats["cards"] == 4


# ── bloco 3: preco/referencia nao finitos (so caminho legado) ─────────────────

@pytest.mark.parametrize("price", [None, float("nan"), float("inf"), -1, 0])
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


# ── gate: teste de fronteira (Fase 0.4 do prompt) ────────────────────────────

@pytest.mark.parametrize("price,eligible", [
    (70.00, True),    # desconto exatamente 30% -> passa (>= limiar)
    (70.01, False),   # 1 centavo acima -> 29,99% -> abaixo do gate
    (69.99, True),    # 1 centavo abaixo -> 30,01% -> passa
])
def test_discount_gate_boundary_at_30_percent(price, eligible):
    """Fronteira do gate (Desconto% minimo = 30, config vigente) com referencia
    de US$ 100: resultado do gate em float ANTES de qualquer porte de Decimal.
    O hunk Decimal NAO foi portado (ver docstring do modulo); estes casos nao
    mudam de lado em nenhuma das duas aritmeticas."""
    stats = Counter()
    row = scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", price, "1"), FairValue(),
                          {"min_discount_percent": 30},
                          refs=FakeRefs(slab={"PSA 9": REF(100.0)}), stats=stats)
    assert (row is not None) == eligible
    assert stats["below_discount"] == int(not eligible)


@pytest.mark.parametrize("reference,price,eligible_today", [
    (250.00, 175.01, True),    # exato 29,996% -> arredondado 30,00 -> passa hoje
    (250.00, 175.02, False),   # exato 29,992% -> arredondado 29,99 -> nao passa
])
def test_discount_gate_compares_rounded_percent_today(reference, price, eligible_today):
    """Documenta o comportamento VIGENTE: o gate compara o Desconto% ja arredondado
    a 2 casas (`report.compute_metrics`). Um anuncio 29,996% abaixo da referencia
    e admitido como 30,00%. Aritmetica exata (Decimal) rejeitaria esse caso =
    fronteira mudando de lado -> hunk nao portado; decisao registrada como pergunta
    ao operador no PR-A. Este teste NAO e endosso do arredondamento."""
    stats = Counter()
    row = scorer.evaluate(CARD, L("Charizard 4/102 PSA 9", price, "1"), FairValue(),
                          {"min_discount_percent": 30},
                          refs=FakeRefs(slab={"PSA 9": REF(reference)}), stats=stats)
    assert (row is not None) == eligible_today
