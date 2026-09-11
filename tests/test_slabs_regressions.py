"""Regressoes portadas do diff local pre-#29 (branch `wip/local-slabs-diff-2026-09-04`).

Cobrem, sobre a base #31:
- bloco 2 = contadores do funil (contagem de por que cada anuncio foi descartado):
  `fetched`, `skip_invalid_payload`, `skip_fetch_error`, `skip_evaluation_error`;
- bloco 3 = identidade da venda usada na referencia (`comparable_sales(..., card=)`),
  CGC "Pristine" antes da nota, nome com limite de palavra + numero completo,
  preco/referencia nao finitos (`invalid_reference`).

Rodada de review do PR #32 (secoes "rodada de review" abaixo): numero alfanumerico
com zero a esquerda, codigo de serie antes da fracao, matcher de nota da cesta
revertido, guarda de identidade da cesta so por contradicao, get_item ilegivel,
interrupcao no meio da carta, `skip_no_price`, mediana de asks com preco None,
mensagem do run parcial por causa.

Testes que NASCEM VERDES contra os fontes da `main` (guarda de comportamento
vigente, nao prova de correcao -- mutation-check do review):
- test_card_identity_with_empty_name_checks_only_number_and_exclusions
- test_pricecharting_breaker_opens_on_fifth_consecutive_failure (duplica cobertura)
- test_discount_gate_boundary_at_30_percent (x3)
- test_discount_gate_compares_rounded_percent_today (x2)
- test_invalid_listing_price_never_emits_row[-1] e [0]
- test_policy_resale_basket_reads_pristine_before_the_grader (fixa efeito na politica)

NAO portados (com o porque):
- bloco 1 (escopo "somente slabs" via `scan_config`/`parse_grades_arg`/CLI): o PR #29
  ja cobre o escopo com outro mecanismo (`slab_strategy`, `conditionIds:{2750}`);
- gate em Decimal (aritmetica exata): o gate vigente compara o Desconto% JA
  arredondado a 2 casas (`report.compute_metrics`); com centavos reais um caso de
  fronteira mudaria de lado (ver `test_discount_gate_compares_rounded_percent_today`)
  -> freio (f)7 do prompt: pergunta ao operador, hunk nao portado.
"""
import dataclasses
import re
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
def test_cgc_pristine_before_grader_is_read_on_the_listing(title):
    """Lado do ANUNCIO (parser compartilhado `grading.grade_from_title`, usado nos
    dois caminhos): "Pristine" antes da sigla e CGC 10 PRISTINE. O lado da VENDA
    do caminho legado (`comparable_sales`) continua com o matcher antigo
    (`_grade_mentions` + `_CGC_PRISTINE_RE`): a cesta nao muda nesta rodada
    (review do PR #32); unificar os dois e assunto do PR-B."""
    result = grading.grade_from_title(title)
    assert result.grade == grading.Grade("CGC", 10, "PRISTINE")


def test_legacy_basket_keeps_the_previous_grade_matcher():
    """A cesta legada so muda por IDENTIDADE nesta rodada: o matcher de nota e o
    de antes do PR #32. "BGS GEM MINT 9.5" (nota depois do qualificador) segue
    fora, e "Pristine CGC 10" (antes da sigla) segue na cesta GEM, como na main."""
    gem_mint = {"title": "Charizard 4/102 BGS GEM MINT 9.5", "price": 500.0}
    assert pc_sales.comparable_sales([gem_mint], "BGS", 9.5, card=CARD) == []
    pristine_first = {"title": "Charizard 4/102 Pristine CGC 10", "price": 500.0}
    assert pc_sales.comparable_sales([pristine_first], "CGC", 10, "GEM", card=CARD) == [pristine_first]
    assert pc_sales.comparable_sales([pristine_first], "CGC", 10, "PRISTINE", card=CARD) == []


@pytest.mark.parametrize("title", [
    "Blastoise 4/102 PSA 9",                        # outra carta
    "Dark Charizard 4/102 PSA 9",                   # prefixo muda a carta
    "Charizard ex 4/102 PSA 9",                     # sufixo muda a carta
    "Charizard 14/102 PSA 9",                       # outro numero
    "Charizard #14 PSA 9",                          # outro numero (marcador #)
])
def test_wrong_card_sale_cannot_supply_reference(title):
    """Venda de OUTRA carta nunca entra na cesta. ("Charizard PSA 9 pop 4" fica:
    "pop 4" nao e numero, e sem numero nao ha contradicao -- ver
    `test_legacy_basket_excludes_sales_only_by_contradiction`.)"""
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


def test_unreadable_price_is_kept_as_none_and_counted_as_no_price(monkeypatch, no_tcg):
    """Valor de preco ilegivel vira `price=None` (comportamento de #31, nao e
    descarte na coleta): no caminho legado conta como "sem preco legivel"
    (`skip_no_price`), nunca vira linha nem erro de avaliacao."""
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
    # Ausencia de preco != preco abaixo do piso: chave propria no funil (review #32).
    assert stats["skip_no_price"] == 1 and stats["skip_price_floor"] == 0
    assert stats["skip_evaluation_error"] == 0


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
    # Preco AUSENTE (None) e "sem preco legivel"; NaN/infinito/zero/negativo e piso.
    assert stats["skip_no_price" if price is None else "skip_price_floor"] == 1
    assert sum(stats.values()) == 1


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


# ── rodada de review do PR #32 ───────────────────────────────────────────────

@pytest.mark.parametrize("name,number,title", [
    ("Arcanine", "H02", "Arcanine H02 Aquapolis PSA 9"),
    ("Arcanine", "H02", "Arcanine H2 Aquapolis PSA 9"),
    ("Arcanine", "H02", "Arcanine #H02 Aquapolis PSA 9"),
    ("Charizard V", "TG03", "Charizard V TG03 Brilliant Stars Trainer Gallery PSA 10"),
    ("Charizard V", "TG03", "Charizard V TG3 Brilliant Stars PSA 10"),
    ("Charizard V", "TG03", "Charizard V TG03/TG30 Brilliant Stars PSA 10"),
    ("Charizard GX", "SV049", "Charizard GX SV049 Hidden Fates Shiny Vault PSA 10"),
    ("Charizard GX", "SV049", "Charizard GX SV49/SV94 Hidden Fates PSA 10"),
    ("Charizard", "004", "Charizard 004/102 Base Set PSA 9"),
    ("Charizard", "004", "Charizard #4 Base Set PSA 9"),
])
def test_alphanumeric_number_with_leading_zero_matches_both_spellings(name, number, title):
    """Numero com letras + zero a esquerda (H02, TG03, SV049): o titulo pode trazer
    o zero ("H02") ou nao ("H2"); os dois casam. Regressao apontada no review
    (32 cartas da watchlist): o zero fica ENTRE o prefixo de letras e os digitos."""
    card = dataclasses.replace(CARD, name="", number=number)   # como identity_matches
    assert title_parser.card_matches_title(card, title)
    assert title_parser.card_matches_title(dataclasses.replace(card, name=name), title)


@pytest.mark.parametrize("number,title", [
    ("H02", "Arcanine H12 Aquapolis PSA 9"),
    ("H02", "Arcanine H20 Aquapolis PSA 9"),
    ("TG03", "Charizard V TG13 Brilliant Stars PSA 10"),
    ("4", "Charizard 14/102 Base Set PSA 9"),
    ("14", "Charizard 4/102 Base Set PSA 9"),
])
def test_alphanumeric_number_does_not_match_other_numbers(number, title):
    card = dataclasses.replace(CARD, name="", number=number)
    assert not title_parser.card_matches_title(card, title)


@pytest.mark.parametrize("name,number,title", [
    ("Charizard GX", "150", "Charizard GX SM 150/147 Burning Shadows PSA 10"),
    ("Charizard EX", "11", "Charizard EX XY 11/106 Flashfire PSA 10"),
    ("Charizard V", "50", "Charizard V SWSH 50/202 Sword & Shield PSA 10"),
    ("Charizard GX", "SM211", "Charizard GX SM211 Black Star Promo PSA 10"),
    ("Charizard V", "SWSH050", "Charizard V SWSH050 Black Star Promo PSA 10"),
])
def test_series_code_before_fraction_or_as_promo_number_is_not_stripped(name, number, title):
    """"SM 150/147": o codigo da serie vem SOLTO antes da fracao, e a fracao e o
    numero da carta -- o strip de "codigo de serie + numero" nao pode come-la.
    Promo "SM211"/"SWSH050": o proprio numero da carta tem o prefixo da serie."""
    card = dataclasses.replace(CARD, name=name, number=number)
    assert title_parser.card_matches_title(card, title)
    assert title_parser.card_matches_title(dataclasses.replace(card, name=""), title)


@pytest.mark.parametrize("number,title", [
    ("12", "Charizard SM12 Cosmic Eclipse #4/236 PSA 10"),     # SM12 = set, nao carta
    ("12", "Charizard Base Set #4 PSA 9 pop 12"),               # pop 12 = populacao
    ("12", "Charizard Base Set #4 PSA 9 cert 12"),              # cert 12 = certificado
    ("45", "Charizard V SWSH 45 Vivid Voltage #25/185 PSA 10"),  # SWSH 45 = set
])
def test_series_code_or_pop_cert_number_never_counts_as_card_number(number, title):
    card = dataclasses.replace(CARD, name="", number=number)
    assert not title_parser.card_matches_title(card, title)


@pytest.mark.parametrize("title,kept", [
    ("1999 Pokemon Charizard Base Set Holo PSA 9", True),        # propria carta, sem numero
    ("Pokemon Vintage Base Set Charizard Holo PSA 9 MINT 1999", True),
    ("Charizard 4/102 PSA 9", True),
    ("Charizard #4 Base Set PSA 9", True),
    ("Charizard Expedition #39/165 PSA 9", False),               # outro numero (fracao)
    ("Charizard #14 Base Set PSA 9", False),                     # outro numero (#)
    ("Blastoise Holo PSA 9", False),                             # outro nome
    ("Dark Charizard Holo PSA 9", False),                        # prefixo muda a carta
    ("Charizard ex Holo PSA 9", False),                          # sufixo muda a carta
])
def test_legacy_basket_excludes_sales_only_by_contradiction(title, kept):
    """Na pagina da PROPRIA carta, a venda so sai da cesta por CONTRADICAO de
    identidade (outro nome, prefixo/sufixo, outro numero) -- nunca por AUSENCIA de
    numero no titulo (review do PR #32: exigir numero amputava vendas da propria
    carta e movia a mediana). Exigir numero como a politica faz = pergunta ao operador."""
    sale = {"title": title, "price": 1000.0}
    got = pc_sales.comparable_sales([sale], "PSA", 9, card=CARD)
    assert got == ([sale] if kept else [])


def test_legacy_basket_on_real_fixture_changes_only_by_identity():
    """Fixture real (pagina da Charizard 4/102): com a guarda de identidade, as cestas
    PSA 9 / PSA 10 / BGS 9.5 / CGC 9 sao IGUAIS as de antes (nenhuma venda da propria
    carta amputada) e so as vendas de OUTRA carta (Expedition #39/#40, TAG 10) saem."""
    from pathlib import Path
    body = (Path(__file__).parent / "fixtures" / "pc_product_charizard_base_4.html").read_text(encoding="utf-8")
    sales = pc_sales.parse_sales(body)
    for grader, value in [("PSA", 9.0), ("PSA", 10.0), ("BGS", 9.5), ("CGC", 9.0)]:
        assert (pc_sales.comparable_sales(sales, grader, value, card=CARD)
                == pc_sales.comparable_sales(sales, grader, value)), (grader, value)
    unguarded = pc_sales.comparable_sales(sales, "TAG", 10.0)
    guarded = pc_sales.comparable_sales(sales, "TAG", 10.0, card=CARD)
    dropped = [s["title"] for s in unguarded if s not in guarded]
    assert len(dropped) == 2 and all(re.search(r"#(?:39|40)/165", t) for t in dropped)
    assert guarded == []


# ── caminho VIVO (slab_strategy): fase de detalhes (get_item) ────────────────

class _DetailClient:
    """Busca devolve o lote; get_item devolve um payload de detalhe por anuncio
    (o de `broken_id` vem com `price` ilegivel)."""
    fetched = parse_dropped = dedup_dropped = 0

    def __init__(self, batch, broken_id=None):
        self.batch, self.broken_id, self.calls = batch, broken_id, 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return list(self.batch) if self.calls == 1 else []

    def get_item(self, item_id):
        self.calls += 1
        item = _item(item_id)
        item["title"] = "Charizard #4/102 Base Set English PSA 9"
        item["localizedAspects"] = [{"name": "Language", "value": "English"}]
        if item_id == self.broken_id:
            item["price"] = "nao-e-um-objeto"
        return item, f"https://api.ebay.com/buy/browse/v1/item/{item_id}"


class _BudgetClient(_DetailClient):
    def get_item(self, item_id):
        self.calls += 1
        if item_id == self.broken_id:
            raise ebay_api.EbayBudgetExceeded("Limite de chamadas eBay atingido")
        return super().get_item(item_id)


def _policy_batch():
    # Sem "English" no titulo: idioma nao declarado -> get_item e chamado.
    return [L("Charizard #4/102 Base Set PSA 9", price, item_id)
            for price, item_id in [(75.0, "p1"), (74.0, "p2"), (73.0, "p3")]]


def _per_listing_buckets(stats):
    return sum(v for k, v in stats.items() if k.startswith(
        ("rows_", "skip_", "invalid_", "slab_no", "ref_un", "below")))


def test_unreadable_item_details_do_not_drop_the_card(no_tcg):
    """Payload de detalhe (get_item) com `price` ilegivel: o anuncio segue com o
    que a busca trouxe, marcado `detalhes-do-anuncio-ilegiveis` (REVISAR), e conta
    em `item_details_error`; a carta NAO cai inteira (review do PR #32)."""
    from src import slab_strategy
    stats = Counter()
    # Historical multi-grade plumbing: keep PSA 9 in scope here so that the new
    # investment-only PSA 10 restriction cannot mask the unreadable-detail review.
    config = slab_strategy.policy_config({})
    config['slab_strategy']['economics']['gate_mode'] = 'gross_margin'
    _, rows = scanner.scan_card(CARD, _DetailClient(_policy_batch(), "p2"),
                                config, stats=stats,
                                refs=FakeRefs(), fair=FairValue(), log=lambda *a: None)
    assert [row.listing.item_id for row in rows] == ["p1", "p2", "p3"]
    broken = rows[1]
    assert broken.listing.price == 74.0 and broken.verdict == "REVISAR"
    assert "detalhes-do-anuncio-ilegiveis" in broken.reasons
    assert stats["item_details_error"] == 1 and stats["item_details_fetched"] == 2
    assert stats["seen"] == 3 == _per_listing_buckets(stats)


def test_budget_exhausted_during_item_details_keeps_the_funnel_honest(no_tcg):
    """Cota/autenticacao estourando em get_item NO MEIO da carta: o erro sobe (run
    parcial), mas as linhas ja avaliadas que se perdem contam em `rows_lost_abort`
    (nao em `rows_*`, que so contam linhas que chegam ao artefato) e os anuncios
    nao avaliados em `skip_details_abort` -- `seen` == soma dos baldes."""
    from src import slab_strategy
    stats = Counter()
    with pytest.raises(ebay_api.EbayBudgetExceeded):
        scanner.scan_card(CARD, _BudgetClient(_policy_batch(), "p3"),
                          slab_strategy.policy_config({}), stats=stats,
                          refs=FakeRefs(), fair=FairValue(), log=lambda *a: None)
    assert stats["seen"] == 3
    assert stats["rows_lost_abort"] == 2 and stats["skip_details_abort"] == 1
    assert stats["rows_review"] == 0 and stats["rows_opportunity"] == 0
    assert stats["seen"] == _per_listing_buckets(stats)
    assert dict(report.FUNNEL_LABELS)["rows_lost_abort"]
    assert dict(report.FUNNEL_LABELS)["skip_details_abort"]


# ── parser compartilhado (grading): efeito declarado na POLITICA ─────────────

@pytest.mark.parametrize("qualifier,expected_n", [("GEM", 2), ("PRISTINE", 1)])
def test_policy_resale_basket_reads_pristine_before_the_grader(qualifier, expected_n):
    """O hunk "CGC Pristine antes da sigla" vive em `grading.grade_from_title`, que a
    politica usa para o ANUNCIO e para a VENDA (`slab_strategy.reference_sales`):
    uma venda "Pristine CGC 10" sai da cesta CGC 10 GEM e entra na cesta PRISTINE.
    Efeito nos DOIS caminhos, declarado no CHANGELOG do PR #32 (o modulo
    `slab_strategy` nao foi tocado; este teste so fixa o comportamento)."""
    from src.slab_strategy import reference_sales
    from tests.test_slab_strategy import CARD as POLICY_CARD, cfg, refs, sales
    pool = sales("CGC 10", price=100, n=2, start=100) + sales("Pristine CGC 10", price=200, n=1, start=200)
    ref = reference_sales(POLICY_CARD, refs(pool), grading.Grade("CGC", 10, qualifier),
                          frozenset(), cfg()["slab_strategy"])
    assert ref["n_sales"] == expected_n
    assert all(("Pristine" in s["title"]) == (qualifier == "PRISTINE") for s in ref["sales"])


def test_legacy_ask_median_ignores_listings_without_readable_price(no_tcg):
    """Legado: `_clean_ask_prices` (mediana dos precos pedidos, usada para conferir
    se a referencia esta alinhada) recebia `price=None` e `statistics.median`
    levantava TypeError FORA do try/except da avaliacao -> carta inteira caia
    (fixture H1 do review do PR #32). Preco ausente/nao finito/<=0 fica de fora."""
    batch = [L("Charizard 4/102 Base Set PSA 9", price, item_id)
             for price, item_id in [(75.0, "a"), (None, "b"), (73.0, "c"), (72.0, "d"),
                                    (float("nan"), "e"), (0.0, "f")]]
    assert scanner._clean_ask_prices(CARD, batch) == {"PSA 9": [75.0, 73.0, 72.0]}
    stats = Counter()
    _, rows = scanner.scan_card(CARD, FakeEbay(batch), {"min_price_usd": 0}, stats=stats,
                                refs=FakeRefs(slab={"PSA 9": REF(100.0)}),
                                fair=FairValue(), log=lambda *a: None)
    assert [row.listing.item_id for row in rows] == ["a", "c", "d"]
    assert stats["skip_no_price"] == 1 and stats["skip_price_floor"] == 2
    assert stats["seen"] == 6 == _per_listing_buckets(stats)


# ── mensagem do run parcial por CAUSA (parada antecipada x erros contados) ────

@pytest.mark.parametrize("failure", [ebay_api.EbayAuthError, ebay_api.EbayBudgetExceeded])
def test_run_scan_marks_early_stop_separately_from_counted_errors(tmp_path, monkeypatch, failure):
    """Parada antecipada (autenticacao/cota) = `stopped_early` (cartas restantes NAO
    varridas). Erro contado por carta/anuncio com todas as cartas visitadas =
    `aborted` sem `stopped_early`."""
    from tests.test_scan_funnel import _patch_scan_card, _watchlist

    def stops(card, stats):
        if card.name == "Blastoise":
            raise failure("parou")
        return FairValue(), []

    _patch_scan_card(monkeypatch, stops)
    _, _, _, stats, aborted = scanner.run_scan(watchlist_path=_watchlist(tmp_path),
                                               log=lambda *a, **k: None)
    assert aborted and stats["stopped_early"] == 1

    def counts(card, stats):
        stats["skip_evaluation_error"] += 1
        return FairValue(), []

    _patch_scan_card(monkeypatch, counts)
    _, _, _, stats, aborted = scanner.run_scan(watchlist_path=_watchlist(tmp_path),
                                               log=lambda *a, **k: None)
    assert aborted and stats["aborted"] == 1 and stats["stopped_early"] == 0


@pytest.mark.parametrize("stopped_early,expected,unexpected", [
    (1, "cartas restantes NAO foram varridas", "todas as cartas foram visitadas"),
    (0, "todas as cartas foram visitadas", "cartas restantes NAO foram varridas"),
])
def test_main_and_summary_explain_partial_run_by_cause(tmp_path, monkeypatch, capsys,
                                                       stopped_early, expected, unexpected):
    import json
    import sys
    import ebay_summary
    import main as main_mod
    from tests.test_scan_funnel import _watchlist
    from tests.test_summary import payload

    stats = Counter({"cards": 4, "seen": 10, "aborted": 1, "skip_evaluation_error": 1,
                     "stopped_early": stopped_early})
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: ({}, [], False, stats, True))
    out = tmp_path / "scan.json"
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", _watchlist(tmp_path),
                                      "--out", str(out)])
    assert main_mod.main() == main_mod.EXIT_ABORTED
    console = capsys.readouterr().out
    assert "RUN ABORTADO" in console and expected in console and unexpected not in console
    funnel = json.loads((tmp_path / "scan.aborted.json").read_text(encoding="utf-8"))["meta"]["funnel"]
    md = ebay_summary.build_markdown(payload(aborted=True, funnel=funnel))
    assert "RUN ABORTADO" in md and expected.replace("NAO", "NÃO") in md
    assert unexpected.replace("NAO", "NÃO") not in md
