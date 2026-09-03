"""Funil do scan, breaker do PriceCharting, abort e referencias reais (fixture).

Regras (operador, COMC 2026-09-02 / eBay 2026-09-03): nada some em silencio --
todo anuncio que nao vira linha e contado; erro na fonte e contado e, se
persistente, suspende a fonte; erro de autenticacao/API ABORTA o run com
exit != 0; anuncio JP no meio da lista nao interrompe os EN seguintes.
"""
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

import main as main_mod
from src import grading, pc_sales, scanner
from src.ebay_api import EbayApiError, EbayAuthError
from src.models import FairValue, Listing, WatchCard
from tests.test_scorer import REF, FakeRefs

FIX = Path(__file__).parent / "fixtures"
PC_URL = "https://www.pricecharting.com/game/pokemon-base-set/charizard-4"
CARD = WatchCard(name="Charizard", set_name="Base Set", number="4", language="EN",
                 pc_url=PC_URL, pokemon="Charizard", pokemon_rank=1)


def L(title, price, item_id, **kw):
    d = dict(item_id=item_id, title=title, price=price, shipping=0.0, currency="USD",
             buying_option="FIXED_PRICE", condition="Graded", seller_feedback_pct=99.5,
             seller_feedback_score=800, url=f"https://www.ebay.com/itm/{item_id}",
             country="US")
    d.update(kw)
    return Listing(**d)


class FakeEbay:
    def __init__(self, batch):
        self.batch = batch
        self.calls = 0

    def search(self, query, min_price=10.0, **kw):
        self.calls += 1
        return list(self.batch) if self.calls == 1 else []


@pytest.fixture
def no_tcg(monkeypatch):
    monkeypatch.setattr(scanner.tcg_reference, "get_tcg_reference", lambda card: None)


# ── funil por anuncio ─────────────────────────────────────────────────────────

def test_scan_card_funnel_counts_everything_and_jp_in_middle_does_not_stop(no_tcg):
    refs = FakeRefs(slab={"PSA 9": REF(3175.0), "PSA 10": REF(30000.0, what="PSA 10")},
                    lp=REF(250.0, n=4, what="LP"), pc_url=PC_URL)
    fair = FairValue(prices={"RAW": 340.0, "PSA 9": 3175.0}, sales_per_month={"RAW": 50.0})
    batch = [
        L("Charizard 4/102 Base Set PSA 9", 2000.0, "1"),                        # OPORTUNIDADE
        L("Charizard 4/102 Base Set Japanese PSA 9", 2400.0, "2"),               # JP -> REVISAR (flag idioma)
        L("Charizard 4/102 Base Set PSA 9", 2100.0, "3", buying_option="AUCTION"),  # leilao
        L("Charizard 4/102 Base Set PSA 7", 500.0, "4"),                         # fora do escopo
        L("Charizard 4/102 Base Set BGS 9.5", 900.0, "5"),                       # sem vendas comparaveis
        L("Blastoise 2/102 Base Set PSA 9", 900.0, "6"),                         # outra carta
        L("Charizard 4/102 Base Set PSA 9", 3000.0, "7"),                        # abaixo do desconto
        L("Charizard 4/102 Base Set Holo LP", 150.0, "8", condition="Ungraded"),  # raw LP (graded_only)
        L("Charizard 4/102 Base Set PSA 10", 4000.0, "9"),                       # SUSPEITO
    ]
    stats = Counter()
    _, opps = scanner.scan_card(CARD, FakeEbay(batch), {"graded_only": True},
                                log=lambda *a: None, stats=stats, refs=refs, fair=fair)
    ids = sorted(o.listing.item_id for o in opps)
    assert ids == ["1", "2", "9"]  # o anuncio EN depois do JP (id 9) foi avaliado
    assert stats["seen"] == 9
    assert stats["skip_not_fixed_price"] == 1
    assert stats["skip_grade_out_of_scope"] == 1
    assert stats["slab_no_reference"] == 1
    assert stats["skip_no_match"] == 1
    assert stats["below_discount"] == 1
    assert stats["skip_raw"] == 1
    assert stats["rows_opportunity"] == 1
    assert stats["rows_review"] == 1
    assert stats["rows_suspect"] == 1
    assert stats["ebay_calls"] == 1


def test_scan_card_include_raw_lp_path(no_tcg):
    refs = FakeRefs(slab={}, lp=REF(250.0, n=4, what="LP"), pc_url=PC_URL)
    fair = FairValue(prices={"RAW": 400.0}, sales_per_month={"RAW": 50.0})
    batch = [
        L("Charizard 4/102 Base Set Holo LP", 150.0, "1", condition="Ungraded"),   # passa: 150 <= 320
        L("Charizard 4/102 Base Set Holo LP", 330.0, "2", condition="Ungraded"),   # pre-filtro
        L("Charizard 4/102 Base Set Holo", 150.0, "3", condition="Ungraded"),      # sem condicao
    ]
    stats = Counter()
    _, opps = scanner.scan_card(CARD, FakeEbay(batch),
                                {"graded_only": False, "min_discount_percent": 20},
                                log=lambda *a: None, stats=stats, refs=refs, fair=fair)
    assert [o.listing.item_id for o in opps] == ["1"]
    assert opps[0].fair_value == 250.0 and opps[0].ref_source == "pricecharting-sales-lp"
    assert stats["lp_prefilter"] == 1 and stats["skip_condition"] == 1


# ── CardRefs sobre a pagina REAL do Charizard 4/102 ───────────────────────────

def test_card_refs_from_real_page(monkeypatch):
    monkeypatch.setattr(pc_sales, "_today", lambda: dt.date(2026, 9, 3))
    body = (FIX / "pc_product_charizard_base_4.html").read_text(encoding="utf-8")
    refs = scanner.CardRefs(CARD, body, PC_URL)
    assert refs.available and refs.n_sales > 100
    psa8 = refs.slab(grading.Grade("PSA", 8.0))
    assert psa8 is not None and psa8.n_sales >= 3 and psa8.price > 0
    lp = refs.lp()
    assert lp is not None and lp.n_sales >= 3
    # 1st Edition nao casa vendas sem o token (e vice-versa)
    first = refs.slab(grading.Grade("PSA", 8.0), frozenset({"1st"}))
    assert first is None or first.price != psa8.price
    # coluna exata so quando existe (PSA 10) -- sanidade, nunca referencia
    psa10 = refs.slab(grading.Grade("PSA", 10.0))
    if psa10 is not None:
        assert psa10.column_price is None or psa10.column_price > 0


def test_card_refs_unavailable_without_body():
    refs = scanner.CardRefs(CARD, "", PC_URL, error="bloqueio")
    assert not refs.available and refs.pc_url == PC_URL


# ── load_card_page: erro na fonte e breaker ───────────────────────────────────

def test_load_card_page_counts_pc_error_and_breaker_opens(monkeypatch):
    def boom(url, cache_dir=None):
        raise pc_sales.PcError("bloqueio")

    monkeypatch.setattr(scanner.pc_sales, "fetch_page", boom)
    stats = Counter()
    breaker = scanner.PcBreaker(max_errors=2)
    fair, refs = scanner.load_card_page(CARD, {}, stats=stats, breaker=breaker,
                                        log=lambda *a: None)
    assert not refs.available and fair.prices == {}
    assert stats["pc_error"] == 1 and not breaker.down
    scanner.load_card_page(CARD, {}, stats=stats, breaker=breaker, log=lambda *a: None)
    assert breaker.down and stats["pc_error"] == 2
    # com o breaker aberto nao ha nova tentativa de rede: conta pc_breaker
    monkeypatch.setattr(scanner.pc_sales, "fetch_page",
                        lambda url, cache_dir=None: pytest.fail("nao devia chamar a rede"))
    _, refs3 = scanner.load_card_page(CARD, {}, stats=stats, breaker=breaker,
                                      log=lambda *a: None)
    assert not refs3.available and stats["pc_breaker"] == 1


def test_breaker_resets_on_success():
    b = scanner.PcBreaker(max_errors=3)
    b.record_error(); b.record_error(); b.record_ok(); b.record_error()
    assert not b.down and b.errors == 1


# ── run_scan: abort e erro por carta ──────────────────────────────────────────

WATCHLIST = """\
cards:
  - {name: Charizard, set: Base Set, number: 4, language: EN, pc_url: https://example.com/a}
  - {name: Blastoise, set: Base Set, number: 2, language: EN, pc_url: https://example.com/b}
  - {name: Venusaur, set: Base Set, number: 15, language: EN, pc_url: https://example.com/c}
  - {name: Pikachu, set: Jungle, number: 60, language: EN, pc_url: https://example.com/d}
"""


class _ConfiguredEbay:
    configured = True

    def __init__(self, *a, **k):
        self.calls = 0


def _watchlist(tmp_path):
    p = tmp_path / "w.yaml"
    p.write_text(WATCHLIST, encoding="utf-8")
    return str(p)


def _patch_scan_card(monkeypatch, behaviour):
    def fake_scan_card(card, ebay, config, log=print, stats=None, breaker=None, **kw):
        return behaviour(card, stats)
    monkeypatch.setattr(scanner, "scan_card", fake_scan_card)
    monkeypatch.setattr(scanner, "EbayClient", _ConfiguredEbay)


def test_run_scan_aborts_on_auth_error(tmp_path, monkeypatch):
    seen = []

    def behaviour(card, stats):
        seen.append(card.name)
        if card.name == "Blastoise":
            raise EbayAuthError("401")
        return FairValue(), []

    _patch_scan_card(monkeypatch, behaviour)
    _, opps, pricing_only, stats, aborted = scanner.run_scan(
        watchlist_path=_watchlist(tmp_path), log=lambda *a, **k: None)
    assert aborted is True and stats["aborted"] == 1
    assert seen == ["Charizard", "Blastoise"]  # Venusaur/Pikachu nao varridos


def test_run_scan_aborts_after_consecutive_api_errors(tmp_path, monkeypatch):
    def behaviour(card, stats):
        raise EbayApiError("503")

    _patch_scan_card(monkeypatch, behaviour)
    _, _, _, stats, aborted = scanner.run_scan(
        watchlist_path=_watchlist(tmp_path), log=lambda *a, **k: None)
    assert aborted is True
    assert stats["ebay_error"] == scanner.EBAY_MAX_CONSECUTIVE_ERRORS


def test_run_scan_counts_card_error_and_continues(tmp_path, monkeypatch):
    seen = []

    def behaviour(card, stats):
        seen.append(card.name)
        if card.name == "Blastoise":
            raise RuntimeError("kaboom")
        return FairValue(), []

    _patch_scan_card(monkeypatch, behaviour)
    _, _, _, stats, aborted = scanner.run_scan(
        watchlist_path=_watchlist(tmp_path), log=lambda *a, **k: None)
    assert aborted is False and stats["card_error"] == 1
    assert seen == ["Charizard", "Blastoise", "Venusaur", "Pikachu"]


def test_main_exit_code_1_and_artifact_marked_when_aborted(tmp_path, monkeypatch, capsys):
    out = tmp_path / "scan.json"
    stats = Counter({"cards": 4, "seen": 10, "aborted": 1})
    monkeypatch.setattr(scanner, "run_scan",
                        lambda **kw: ({}, [], False, stats, True))
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", _watchlist(tmp_path),
                                      "--out", str(out), "--min-discount", "10",
                                      "--min-price", "5"])
    assert main_mod.main() == main_mod.EXIT_ABORTED
    assert not out.exists()  # parcial vai para o arquivo irmao .aborted.json
    payload = json.loads((tmp_path / "scan.aborted.json").read_text(encoding="utf-8"))
    assert payload["meta"]["aborted"] is True
    assert payload["meta"]["funnel"]["seen"] == 10
    assert payload["meta"]["config"]["min_discount_percent"] == 10
    assert payload["meta"]["config"]["min_price_usd"] == 5.0
    assert "RUN ABORTADO" in capsys.readouterr().out


def test_main_grades_typo_errors_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", _watchlist(tmp_path),
                                      "--grades", "PSA 7"])
    with pytest.raises(SystemExit) as exc:
        main_mod.main()
    assert "PSA 7" in str(exc.value)


def test_scan_card_passes_fixed_price_and_country_from_config(no_tcg):
    class RecordingEbay:
        def __init__(self):
            self.calls = 0
            self.kwargs = []

        def search(self, query, **kw):
            self.calls += 1
            self.kwargs.append(kw)
            return []

    refs = FakeRefs(slab={}, pc_url=PC_URL)
    fair = FairValue()
    ebay = RecordingEbay()
    scanner.scan_card(CARD, ebay, {"graded_only": True, "fixed_price_only": False,
                                   "required_location_country": "CA", "max_pages": 2,
                                   "min_price_usd": 7.0},
                      log=lambda *a: None, refs=refs, fair=fair)
    kw = ebay.kwargs[0]
    assert kw["fixed_price_only"] is False and kw["location_country"] == "CA"
    assert kw["max_pages"] == 2 and kw["min_price"] == 7.0
    ebay2 = RecordingEbay()
    scanner.scan_card(CARD, ebay2, {"graded_only": True}, log=lambda *a: None,
                      refs=refs, fair=fair)
    assert ebay2.kwargs[0]["fixed_price_only"] is True
    assert ebay2.kwargs[0]["location_country"] == "US"


def test_aborted_run_never_overwrites_previous_complete_artifact(tmp_path, monkeypatch, capsys):
    out = tmp_path / "last_scan.json"
    out.write_text('{"meta": {"aborted": false, "complete": true}, "rows": [{"x": 1}]}',
                   encoding="utf-8")
    stats = Counter({"cards": 4, "seen": 10, "aborted": 1})
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: ({}, [], False, stats, True))
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", _watchlist(tmp_path),
                                      "--out", str(out)])
    assert main_mod.main() == main_mod.EXIT_ABORTED
    assert '"complete": true' in out.read_text(encoding="utf-8")  # preservado
    aborted_path = tmp_path / "last_scan.aborted.json"
    payload = json.loads(aborted_path.read_text(encoding="utf-8"))
    assert payload["meta"]["aborted"] is True
    assert "last_scan.aborted.json" in capsys.readouterr().out


def test_rows_counted_by_final_verdict_after_alignment_downgrade(no_tcg):
    # Review Codex 2026-09-03: OPORTUNIDADE rebaixada para REVISAR pela
    # referencia desalinhada contava como opportunity no funil.
    refs = FakeRefs(slab={"PSA 9": REF(3175.0)}, pc_url=PC_URL)  # 1.55x a mediana dos anuncios
    fair = FairValue()
    batch = [L("Charizard 4/102 Base Set PSA 9", 2000.0, "1"),
             L("Charizard 4/102 Base Set PSA 9", 2100.0, "2"),
             L("Charizard 4/102 Base Set PSA 9", 2050.0, "3")]
    stats = Counter()
    _, opps = scanner.scan_card(CARD, FakeEbay(batch), {"graded_only": True},
                                log=lambda *a: None, stats=stats, refs=refs, fair=fair)
    assert all(o.verdict == "REVISAR" for o in opps)
    assert stats["rows_review"] == 3 and stats["rows_opportunity"] == 0


def test_ebay_calls_counted_even_when_search_raises(no_tcg):
    class ExplodingEbay:
        calls = 0
        dedup_dropped = 0

        def search(self, query, **kw):
            self.calls += 2
            self.dedup_dropped += 1
            raise EbayApiError("boom")

    stats = Counter()
    with pytest.raises(EbayApiError):
        scanner.scan_card(CARD, ExplodingEbay(), {"graded_only": True}, log=lambda *a: None,
                          stats=stats, refs=FakeRefs(slab={}, pc_url=PC_URL), fair=FairValue())
    assert stats["ebay_calls"] == 2 and stats["dedup_dropped"] == 1


def test_load_config_makes_discount_gate_explicit(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("min_gross_margin_percent: 15\nmin_price_usd: 10.0\n", encoding="utf-8")
    loaded = main_mod._load_config(str(cfg))
    assert loaded["min_discount_percent"] == 20
    cfg.write_text("min_discount_percent: 12\n", encoding="utf-8")
    assert main_mod._load_config(str(cfg))["min_discount_percent"] == 12
