"""Modo CHINÊS (src/chinese_scan.py + src/chinese_report.py): tudo offline."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from types import SimpleNamespace

import pytest

import ebay_summary
from src import chinese_report, chinese_scan as cs, pc_sales
from src.ebay_api import EbayBudgetExceeded
from src.models import Listing, WatchCard

TODAY = dt.date(2026, 9, 26)
CARD = WatchCard("Charizard ex", "SV: Scarlet & Violet 151", "199", "EN",
                 "https://www.pricecharting.com/game/pokemon-scarlet-&-violet-151/charizard-ex-199",
                 pokemon="Charizard", rarity="Special Illustration Rare", group="1", year=2023)
ROCKET = WatchCard("Team Rocket's Mewtwo ex", "SV10: Destined Rivals", "231", "EN",
                   "https://www.pricecharting.com/game/pokemon-destined-rivals/team-rockets-mewtwo-ex-231",
                   pokemon="Mewtwo", rarity="Special Illustration Rare", group="1", year=2025)


def listing(title, price=50.0, country="CN", item_id="1", shipping=15.0):
    return Listing(item_id, title, price, shipping, "USD", "FIXED_PRICE", "Graded", 99.5, 800,
                   f"https://www.ebay.com/itm/{item_id}", country=country)


# --- idioma ---------------------------------------------------------------------
@pytest.mark.parametrize("title,code", [
    ("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR", "ZH-HANS"),
    ("Pokemon PSA 10 Charizard ex SR 2025 175/151 151C S.Chinese", "ZH-HANS"),
    ("PSA 10 Gem Mint Cynthia Caitlin TT #182 Simplified PTCG FA Holo Trainer", "ZH-HANS"),
    ("2025 POKEMON SIMPLIFIED CHINESE CSV5 C-DARK CRYSTAL BLAZE #039 MEWTWO EX PSA 10", "ZH-HANS"),
    ("Pokemon S-Chinese Scarlet & Violet CSV5C-162/129 Charizard EX Ultra Rare Psa 10", "ZH-HANS"),
    ("2025 POKEMON TRADITIONAL CHINESE M2 F-INFERNO X #094 MEGA CHARIZARD X EX PSA 10", "ZH-HANT"),
    ("PSA 10 PTCG Charizard Holo 001/025 2021 Pokemon Traditional Chinese 25th", "ZH-HANT"),
    ("Pokemon Charizard ex sv4aF 125/190 PSA 10", "ZH-HANT"),
    ("Charizard Traditional Chinese Pokemon TCG Classic & Ho-Oh ex Deck (CLL F) PSA 10", "ZH-HANT"),
    ("Pokemon 2025 Charizard EX 006/151 PSA 10 GEM MINT - Chinese", "ZH"),
    ("2020 POKEMON CHINESE SUN & MOON DOUBLE BURST #002 RESHIRAM & CHARIZARD GX PSA 10", "ZH"),
    ("Pokémon Gem Pack Vol 2 Umbreon #04 PSA 10", None),
    ("Charizard ex 199/165 Japanese PSA 10", None),
    ("Chinese + Japanese Charizard lot PSA 10", None),
    ("Charizard 4/102 Base Set English PSA 10", None),
])
def test_chinese_language(title, code):
    assert cs.chinese_language(title)[0] == code


def test_chinese_language_conflicting_markers_is_generic():
    code, ev = cs.chinese_language("Simplified and Traditional Chinese Pikachu PSA 10")
    assert code == "ZH" and "simplificado-e-tradicional" in ev


def test_slab_strategy_language_untouched():
    from src.slab_strategy import language
    assert language("Chinese") is None  # contrato travado em test_policy_review


# --- identidade e busca ---------------------------------------------------------------
def test_name_parts_and_query():
    assert cs.name_parts("Team Rocket's Mewtwo ex") == ("mewtwo", "ex")
    assert cs.name_parts("Umbreon VMAX") == ("umbreon", "vmax")
    assert cs.name_parts("Ethan's Ho-Oh ex") == ("ho-oh", "ex")
    assert cs.name_parts("Pikachu") == ("pikachu", "")
    q = cs.discovery_query(ROCKET)
    assert q.startswith("mewtwo ex ") and "(chinese,chn,simplified,traditional)" in q and "(psa 10,psa10)" in q
    assert "rocket" not in q


def test_match_level_strong_name_and_base():
    assert cs.match_level(CARD, "Pokemon Charizard ex 199/165 Chinese PSA 10") == "nome+numero"
    assert cs.match_level(CARD, "PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR") == "nome"
    assert cs.match_level(ROCKET, "2025 Pokemon SV10 Chinese #125 Rocket's Mewtwo ex SAR PSA 10") == "nome"   # dono escrito de outro jeito
    assert cs.match_level(ROCKET, "Mewtwo ex SAR Chinese PSA 10") == "nome-base"                            # sem dono, raridade compatível
    assert cs.match_level(ROCKET, "2025 POKEMON SIMPLIFIED CHINESE CSV5 C-DARK CRYSTAL BLAZE #039 MEWTWO EX PSA 10") is None  # sem dono, sem SAR
    assert cs.match_level(ROCKET, "Garchomp ex Chinese PSA 10 SR") is None
    assert cs.match_level(ROCKET, "Team Rocket's Mewtwo ex 231/182 Chinese PSA 10") == "nome+numero"
    assert cs.match_level(CARD, "Charizard VMAX Chinese PSA 10") is None      # sufixo muda a carta
    assert cs.match_level(CARD, "Mega Charizard ex Chinese PSA 10") is None   # prefixo muda a carta
    assert cs.match_level(CARD, "Pikachu ex Chinese PSA 10") is None


def test_owner_tokens_rarity_families_and_lots():
    assert cs.owner_tokens("Team Rocket's Mewtwo ex") == ["rocket"]
    assert cs.owner_tokens("Cynthia's Garchomp ex") == ["cynthia"] and cs.owner_tokens("Charizard ex") == []
    assert cs.rarity_compatible("Special Illustration Rare", "Charizard ex SAR PSA 10") is True
    assert cs.rarity_compatible("Special Illustration Rare", "Charizard ex Special Art Rare PSA 10") is True
    assert cs.rarity_compatible("Special Illustration Rare", "Charizard ex SR CSV5C PSA 10") is False
    assert cs.rarity_compatible("Special Illustration Rare", "Charizard ex AR PSA 10") is False
    assert cs.rarity_compatible("Illustration Rare", "Umbreon AR CBB2 PSA 10") is True
    assert cs.rarity_compatible("Illustration Rare", "Umbreon Special Illustration Rare PSA 10") is False
    assert cs.rarity_compatible("Hyper Rare", "Mewtwo ex UR gold PSA 10") is True
    assert cs.rarity_compatible("Special Illustration Rare", "Charizard ex Chinese PSA 10") is None
    assert cs.rarity_compatible("", "Charizard ex SAR PSA 10") is None
    assert cs.lot_or_reject("Charizard Traditional Chinese Pokemon TCG Classic & Ho-Oh ex Deck (CLL F) PSA 10") == "lote-ou-deck"
    assert cs.lot_or_reject("PSA10 Gem Mint 5 FA Trainer Lot Lisia Dana Fantina SC S&M Simplified PTCG") == "lote-ou-deck"
    assert cs.lot_or_reject("Charizard Chinese proxy PSA 10") == "rejeitar-palavra-de-replica-ou-acessorio"
    assert cs.lot_or_reject("2021 POKEMON CHINESE 25TH ANNIVERSARY CLASSIC COLLECTION #022 MEWTWO EX PSA 10") is None


def test_exclusive_marker():
    assert cs.exclusive_marker("2025 POKEMON SIMPLIFIED CHINESE CBB2 C-GEM PACK VOL 2 #11 UMBREON PSA 10") == "cbb2"
    assert cs.exclusive_marker("2021 POKEMON CHINESE 25TH ANNIVERSARY CLASSIC COLLECTION #022 MEWTWO EX PSA 10") in ("25th", "classic")
    assert cs.exclusive_marker("PSA 10 Pokemon S-Chinese Card Charizard VMAX 080/S-P Promo Collection Gift Box") is not None
    assert cs.exclusive_marker("2024 POKEMON TRADITIONAL CHINESE SV-P PROMO #166 CHARIZARD EX PSA 10") is not None
    assert cs.exclusive_marker("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR") is None
    assert cs.exclusive_marker("Pokemon PSA 10 Charizard ex SR 2025 175/151 151C S.Chinese") is None


# --- página chinesa -------------------------------------------------------------------
def test_zh_number_and_set_hint():
    assert cs.zh_number_from_title("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR") == "145"
    assert cs.zh_number_from_title("2025 POKEMON TRADITIONAL CHINESE M2 F-INFERNO X #094 MEGA CHARIZARD X EX PSA 10") == "94"
    assert cs.zh_number_from_title("Charizard Chinese PSA 10 Gem Mint pop 12") is None
    assert cs.zh_set_hint("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR") == "csv5c"
    assert cs.zh_set_hint("Pokemon Charizard ex sv4aF 125/190 PSA 10") == "sv4af"
    assert cs.zh_set_hint("2025 POKEMON SIMPLIFIED CHINESE CBB2 C-GEM PACK VOL 2 #11 UMBREON PSA 10") == "gem-pack"
    assert cs.zh_set_hint("Pokemon PSA 10 Charizard ex SR 2025 175/151 151C S.Chinese") == "151-collect"
    assert cs.zh_set_hint("2024 POKEMON SIMPLIFIED CHINESE CS5.5 C-SHADOW OF GLORY RADIANT CHARIZARD PSA 10") == "cs55c" or \
        cs.zh_set_hint("2024 POKEMON SIMPLIFIED CHINESE CS5.5 C-SHADOW OF GLORY RADIANT CHARIZARD PSA 10") == "cs55"


def _search_html(paths, absolute=False, labels=None):
    labels = labels or {}
    pre = "https://www.pricecharting.com" if absolute else ""
    return "<html>" + "".join(f'<a href="{pre}{p}" title="1">{labels.get(p, "x")}</a>' for p in paths) + "</html>"


def test_pick_zh_page_unique_hint_and_ambiguous():
    body = _search_html(["/game/pokemon-chinese-csv5c/charizard-ex-145", "/game/pokemon-chinese-csv5c/charizard-ex-155",
                         "/game/pokemon-chinese-151-collect/charizard-ex-145", "/game/pokemon-japanese-sv2a/charizard-ex-145"])
    url, why = cs.pick_zh_page(body, "charizard", "ex", "145", "csv5c")
    assert url == "https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-145" and why == "unica"
    url, why = cs.pick_zh_page(body, "charizard", "ex", "145", None)
    assert url is None and why.startswith("ambigua")
    url, why = cs.pick_zh_page(body, "charizard", "ex", "999", None)
    assert url is None and why == "sem-pagina"
    # nome incompatível no slug nunca casa; página japonesa nunca entra
    assert cs.pick_zh_page(body, "pikachu", "", "145", None)[0] is None


def test_pick_zh_page_absolute_links_variants_glued_numbers_and_labels():
    body = _search_html(["/game/pokemon-chinese-151-collect/eevee-master-ball-133", "/game/pokemon-chinese-151-collect/eevee-133",
                         "/game/pokemon-chinese-151-collect/eevee-reverse-133", "/game/pokemon-chinese-promo/bulbasaur-130th-p",
                         "/game/pokemon-chinese-151-collect/bulbasaur-1", "/game/pokemon-chinese-gem-pack-4/eevee-407"],
                        absolute=True, labels={"/game/pokemon-chinese-promo/bulbasaur-130th-p": "Bulbasaur #1/30th-P",
                                               "/game/pokemon-chinese-gem-pack-4/eevee-407": "Eevee #407"})
    # variante só quando o título pede; sem pedido, a página comum
    assert cs.pick_zh_page(body, "eevee", "", "133", None, title="Eevee 133/165 Chinese PSA 10")[0].endswith("/eevee-133")
    assert cs.pick_zh_page(body, "eevee", "", "133", None, title="REVERSE HOLO #133 EEVEE Chinese PSA 10")[0].endswith("/eevee-reverse-133")
    assert cs.pick_zh_page(body, "eevee", "", "133", None, title="Eevee Master Ball 133 Chinese PSA 10")[0].endswith("/eevee-master-ball-133")
    # promo com número colado ao código: o rótulo "#1/30th-P" decide, e a pista "30th" casa pelo rótulo
    assert cs.pick_zh_page(body, "bulbasaur", "", "1", "30th", title="Bulbasaur 30th-P 001 Chinese PSA 10")[0].endswith("/bulbasaur-130th-p")
    assert cs.pick_zh_page(body, "bulbasaur", "", "1", None, title="Bulbasaur Chinese PSA 10")[1].startswith("ambigua")
    # Gem Pack: numerador+denominador colados no slug ("4/07" → 407), denominador como impresso
    assert cs.zh_fraction_from_title("Eevee 4/07 Gem Pack Chinese PSA 10") == ("4", "07")
    assert cs.pick_zh_page(body, "eevee", "", "4", "gem-pack", title="Eevee 4/07 Gem Pack Chinese PSA 10", denominator="07")[0].endswith("/eevee-407")
    # busca que REDIRECIONA para uma promo com número colado: o <title> "#003" prova o número
    redir = ('<html><head><title>Squirtle #003/30TH-P Prices | Pokemon Chinese Promo</title>'
             '<link rel="canonical" href="https://www.pricecharting.com/game/pokemon-chinese-promo/squirtle-330th-p"></head>'
             '<body><table id="price_data"></table></body></html>')
    assert cs.pick_zh_page(redir, "squirtle", "", "3", "30th")[1] == "redirect-canonical"
    assert cs.pick_zh_page(redir, "squirtle", "", "5", "30th")[0] is None


def test_pick_zh_page_without_number_needs_unique_set_hint():
    body = _search_html(["/game/pokemon-chinese-sv8a/umbreon-ex-217", "/game/pokemon-chinese-sv8a/umbreon-ex-60",
                         "/game/pokemon-chinese-csv95c/umbreon-ex-239"])
    assert cs.pick_zh_page(body, "umbreon", "ex", None, None) == (None, "sem-numero-e-sem-pista")
    url, why = cs.pick_zh_page(body, "umbreon", "ex", None, "csv95c")
    assert url.endswith("/pokemon-chinese-csv95c/umbreon-ex-239") and why == "unica"
    assert cs.pick_zh_page(body, "umbreon", "ex", None, "sv8a")[1].startswith("ambigua")
    assert cs.pick_zh_page(body, "umbreon", "ex", None, "cs4a") == (None, "sem-pagina")
    assert "csv95c" in cs.zh_search_url("umbreon", "ex", None, "csv95c") and "csv95c" not in cs.zh_search_url("umbreon", "ex", "217")


def test_zh_margin_pct():
    assert cs.zh_margin_pct({"listing": {"price": 969.69}, "zh": {"status": "ok", "median_90d": 530.0}}) == pytest.approx(-45.3, abs=0.1)
    assert cs.zh_margin_pct({"listing": {"price": 100.0}, "zh": {"status": "ok", "median_90d": 150.0}}) == 50.0
    assert cs.zh_margin_pct({"listing": {"price": 100.0}, "zh": {"status": "ok", "median_90d": None}}) is None
    assert cs.zh_margin_pct({"listing": {"price": 100.0}, "zh": {"status": "sem-pagina"}}) is None


def test_pick_zh_page_redirect_canonical():
    body = ('<html><head><link rel="canonical" href="https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-145">'
            '</head><body><table id="price_data"></table></body></html>')
    url, why = cs.pick_zh_page(body, "charizard", "ex", "145", None)
    # o <link rel=canonical> absoluto também é lido como resultado: 'unica' ou 'redirect-canonical', nunca chute
    assert url.endswith("/charizard-ex-145") and why in ("unica", "redirect-canonical")
    body_en = body.replace("pokemon-chinese-csv5c", "pokemon-scarlet-&-violet-151")
    assert cs.pick_zh_page(body_en, "charizard", "ex", "145", None)[0] is None


def test_parse_pop_data():
    assert cs.parse_pop_data('x VGPC.pop_data = {"cgc":[0,0,0,0,0,0,0,0,0,0],"psa":[0,0,0,0,0,2,0,3,34,223]}; y')["psa"][9] == 223
    assert cs.parse_pop_data("sem censo") is None
    assert cs.parse_pop_data('VGPC.pop_data = {"psa":[1,2]};') is None


def _row(sale_id, date, title, price):
    return (f'<tr id="ebay-{sale_id}"><td class="date">{date}</td>'
            f'<td class="title"><a href="https://ebay/{sale_id}">{title}</a> [eBay]</td>'
            f'<td class="numeric"><span class="js-price">${price:.2f}</span></td></tr>')


def _page(sales, columns='<tr><td>PSA 10</td><td>$1,000.00</td></tr>', pop=None):
    rows = "".join(_row(i, (TODAY - dt.timedelta(days=d)).isoformat(), t, p) for i, (d, t, p) in enumerate(sales, 1))
    popjs = f'<script>VGPC.pop_data = {json.dumps(pop)};</script>' if pop else ""
    return (f'<div id="full-prices"><table>{columns}</table></div>{popjs}'
            f'<div class="completed-auctions-graded"><table>{rows}</table></div>' + "x" * 3000)


def test_zh_evidence_counts_only_psa10_recent_and_same_page(monkeypatch):
    monkeypatch.setattr(cs, "sales_per_month_from_page", lambda body: 1.0)
    page = _page([(5, "Charizard ex 145 CSV5C PSA 10", 90), (40, "Charizard ex CSV5C PSA 10 Gem", 100),
                  (80, "Charizard ex PSA 10", 110), (10, "Charizard ex PSA 9", 40),
                  (20, "Charizard ex Japanese PSA 10", 30), (200, "Charizard ex PSA 10", 200),
                  (300, "Charizard ex PSA 10", 220), (350, "Charizard ex PSA 10", 240)],
                 pop={"cgc": [0] * 10, "psa": [0, 0, 0, 0, 0, 0, 0, 0, 10, 55]})
    ev = cs.zh_evidence(page, TODAY)
    assert ev["n_sales_90d"] == 3 and ev["months_90d"] >= 2 and ev["median_90d"] == 100.0
    assert ev["n_sales_prior"] == 3 and ev["median_prior"] == 220.0
    assert ev["trend_observed_pct"] == pytest.approx((100 / 220 - 1) * 100, abs=0.1)
    assert ev["pop_psa10"] == 55 and ev["pop_total"] == 65 and ev["psa10_column_usd"] == 1000.0
    assert ev["sales_per_month_site"] == 1.0 and ev["sales_per_month_observed"] == 1.0
    assert all(s["url"].startswith("https://www.ebay.com/itm/") for s in ev["sales_90d"])


def test_zh_evidence_empty_page_is_honest(monkeypatch):
    monkeypatch.setattr(cs, "sales_per_month_from_page", lambda body: None)
    ev = cs.zh_evidence(_page([], columns=""), TODAY)
    assert ev["n_sales_90d"] == 0 and ev["median_90d"] is None and ev["pop_psa10"] is None
    assert ev["psa10_column_usd"] is None and ev["trend_observed_pct"] is None


def test_en_reference_windows_and_column_fallback():
    page = _page([(3, "Charizard ex 199/165 PSA 10", 1400), (30, "Charizard ex 199 PSA 10", 1500),
                  (60, "Charizard ex 199/165 PSA 10 Gem Mint", 1300), (10, "Charizard ex 199 Chinese PSA 10", 80)])
    ref = cs.en_reference(CARD, page, TODAY)
    assert ref == {"price": 1400.0, "n": 3, "window_days": 90, "source": "vendas", "url": CARD.pc_url}
    page2 = _page([(3, "Charizard ex 199/165 PSA 10", 1400)])
    ref2 = cs.en_reference(CARD, page2, TODAY)
    assert ref2["source"] == "coluna-PC" and ref2["price"] == 1000.0 and ref2["n"] == 1
    ref3 = cs.en_reference(CARD, _page([], columns=""), TODAY)
    assert ref3["price"] is None and ref3["source"] == "sem-referencia"


# --- régua LT ---------------------------------------------------------------------------
def test_longterm_bands_mirror_outlook_and_never_zero(monkeypatch):
    assert cs.rarity_points("Special Illustration Rare") == 25 and cs.rarity_points("Charizard ex SAR PSA 10") == 25
    assert cs.rarity_points("Illustration Rare") == 20 and cs.rarity_points("Umbreon AR CBB2") == 20
    assert cs.rarity_points("Charizard ex SR CSV5C") == 12 and cs.rarity_points("Charizard Holo") == 3
    assert [cs.scarcity_points(x) for x in (10, 500, 501, 5000, 9999, 20000, None)] == [25, 22, 18, 12, 7, 3, None]
    assert [cs.demand_points(x) for x in (60, 30, 5, 2, 1.9, None)] == [25, 20, 14, 8, 3, None]
    monkeypatch.setattr(cs, "character_points", lambda name: 25)
    lt = cs.longterm("Charizard ex", "Special Illustration Rare", {"pop_psa10": 223, "pop_total": 262, "sales_per_month_site": 1.0})
    assert lt["score"] == 25 + 25 + 22 + 3 and lt["coverage"] == "4/4" and lt["character_tier"] == "S"
    lt2 = cs.longterm("Charizard ex", "SR", None)
    assert lt2["score"] == 25 + 12 and lt2["coverage"] == "2/4" and lt2["scarcity"] is None
    monkeypatch.setattr(cs, "character_points", lambda name: None)
    lt3 = cs.longterm("Charizard ex", "SR", {"pop_psa10": None, "sales_per_month_site": None, "sales_per_month_observed": 2.0})
    assert lt3["character"] is None and lt3["character_tier"] == "—" and lt3["demand"] == 8 and lt3["coverage"] == "2/4"


# --- classificação ------------------------------------------------------------------------
def _row_dict(**kw):
    base = {"exclusive": False, "match": "nome+numero", "rarity_check": None, "language": "ZH-HANS", "ratio": 5.0,
            "en_ref": {"price": 500.0, "source": "vendas", "n": 4}, "zh": {"status": "ok", "n_sales_90d": 3}}
    base.update(kw)
    return base


def test_classify_buckets():
    p = cs.DEFAULT_PARAMS
    assert cs.classify(_row_dict(), p) == ("candidata", [])
    assert cs.classify(_row_dict(exclusive=True), p)[0] == "exclusiva"
    assert cs.classify(_row_dict(ratio=3.9), p) == ("abaixo-do-corte", ["razao<4"])
    assert cs.classify(_row_dict(en_ref={"price": None, "source": "sem-referencia"}, ratio=None), p)[0] == "sem-referencia-en"
    b, why = cs.classify(_row_dict(match="nome", rarity_check=None), p)
    assert b == "validar" and why == ["match-nome", "raridade-nao-confirmada"]
    assert cs.classify(_row_dict(match="nome", rarity_check=True), p) == ("candidata", [])
    b, why = cs.classify(_row_dict(match="nome", rarity_check=False), p)
    assert b == "validar" and why == ["match-nome", "raridade-divergente"]
    b, why = cs.classify(_row_dict(match="nome+numero", rarity_check=False), p)
    assert b == "validar" and why == ["raridade-divergente"]
    b, why = cs.classify(_row_dict(match="nome-base", rarity_check=True), p)
    assert b == "validar" and why == ["match-nome-base", "raridade-nao-confirmada"]
    b, why = cs.classify(_row_dict(language="ZH"), p)
    assert b == "validar" and "idioma-nao-especificado" in why
    b, why = cs.classify(_row_dict(zh={"status": "ok", "n_sales_90d": 2}), p)
    assert b == "validar" and why == ["evidencia-zh-insuficiente(2<3)"]
    b, why = cs.classify(_row_dict(zh={"status": "sem-pagina"}), p)
    assert b == "validar" and why == ["zh-sem-pagina"]
    b, why = cs.classify(_row_dict(en_ref={"price": 500.0, "source": "coluna-PC", "n": 1}), p)
    assert b == "validar" and why == ["ref-en-coluna-PC"]


# --- scan_card / run_scan ------------------------------------------------------------------
class FakeEbay:
    def __init__(self, listings, calls_per_search=1):
        self.listings, self.calls, self.max_calls, self.configured = listings, 0, 500, True
        self.queries = []
        self._n = calls_per_search

    def search(self, query, **kw):
        self.queries.append((query, kw))
        self.calls += self._n
        return list(self.listings)


EN_PAGE = _page([(3, "Charizard ex 199/165 PSA 10", 1400), (30, "Charizard ex 199 PSA 10", 1500), (60, "Charizard ex 199 PSA 10", 1300)])
ZH_PAGE = _page([(5, "Charizard ex 145 CSV5C PSA 10", 90), (40, "Charizard ex CSV5C PSA 10", 100), (80, "Charizard ex PSA 10", 110)],
                columns='<tr><td>PSA 10</td><td>$95.00</td></tr>', pop={"cgc": [0] * 10, "psa": [0, 0, 0, 0, 0, 0, 0, 0, 10, 55]})
ZH_SEARCH = _search_html(["/game/pokemon-chinese-csv5c/charizard-ex-145", "/game/pokemon-chinese-151-collect/charizard-ex-199"])


def _fetch_factory(pages):
    calls = []

    def fetch(url, cache_dir=None):
        calls.append(url)
        for key, body in pages.items():
            if key in url:
                return body
        raise pc_sales.PcError(f"sem fixture para {url}")
    fetch.calls = calls
    return fetch


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(cs, "sales_per_month_from_page", lambda body: 1.0)
    monkeypatch.setattr(cs, "character_points", lambda name: 25)


def test_scan_card_end_to_end(quiet):
    ls = [
        listing("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR", price=58.0, item_id="a"),          # 1400/58 = 24× → nome → validar
        listing("Pokemon Charizard ex 199/165 Chinese PSA 10", price=200.0, item_id="b", country="US"),      # 7× nome+numero mas idioma ZH → validar
        listing("Charizard ex Simplified Chinese 199/165 PSA 10", price=300.0, item_id="c"),                 # 4.67× candidata (evidência ok)
        listing("Charizard ex Simplified Chinese 145/129 PSA 10", price=800.0, item_id="d"),                 # 1.75× abaixo do corte
        listing("2024 POKEMON TRADITIONAL CHINESE SV-P PROMO #166 CHARIZARD EX PSA 10", price=120.0, item_id="e"),  # exclusiva
        listing("Charizard ex Chinese PSA 9", price=20.0, item_id="f"),                                      # não é PSA 10
        listing("Pikachu ex Chinese PSA 10", price=20.0, item_id="g"),                                       # outra carta
        listing("Charizard ex 199/165 PSA 10", price=20.0, item_id="h"),                                     # sem marcador
        listing("Charizard ex Chinese PSA 10", price=5.0, item_id="i"),                                      # abaixo do piso
    ]
    ebay = FakeEbay(ls)
    fetch = _fetch_factory({"violet-151/charizard-ex-199": EN_PAGE, "search-products": ZH_SEARCH,
                            "charizard-ex-145": ZH_PAGE, "chinese-151-collect/charizard-ex-199": ZH_PAGE})
    stats = Counter()
    rows = cs.scan_card(CARD, ebay, dict(cs.DEFAULT_PARAMS), fetch=fetch, today=TODAY, stats=stats, log=lambda *a: None)
    # ordem de gasto do teto: pares ≥ corte antes das exclusivas (busca da 'e' vem por último)
    zh_urls = [u for u in fetch.calls if "search-products" in u]
    assert zh_urls and "166" in zh_urls[-1]
    assert stats["ebay_calls"] == 1 and stats["cards_scanned"] == 1 and stats["listings_fetched"] == 9
    assert stats["skip_not_psa10"] == 1 and stats["skip_name_mismatch"] == 1 and stats["skip_sem-marcador"] == 1 and stats["skip_below_floor"] == 1
    by_id = {r["listing"]["item_id"]: r for r in rows}
    assert set(by_id) == {"a", "b", "c", "d", "e"}
    assert by_id["a"]["bucket"] == "validar" and by_id["a"]["reasons"] == ["match-nome", "raridade-divergente"] and by_id["a"]["ratio"] == pytest.approx(1400 / 58, abs=0.01)
    assert by_id["b"]["bucket"] == "validar" and "idioma-nao-especificado" in by_id["b"]["reasons"]
    assert by_id["c"]["bucket"] == "candidata" and by_id["c"]["zh"]["status"] == "ok" and by_id["c"]["zh"]["n_sales_90d"] == 3
    assert by_id["d"]["bucket"] == "abaixo-do-corte" and by_id["d"]["zh"] is None        # não gasta página chinesa
    assert by_id["e"]["bucket"] == "exclusiva" and by_id["e"]["en_ref"] is None and by_id["e"]["ratio"] is None
    assert by_id["c"]["lt"]["score"] == 25 + 25 + 22 + 3 and by_id["c"]["lt"]["pop_psa10"] == 55
    assert by_id["c"]["en_ref"]["price"] == 1400.0 and by_id["c"]["en_ref"]["url"] == CARD.pc_url
    # página EN baixada UMA vez; a chinesa 145 reaproveitada entre linhas a/c
    assert sum(1 for u in fetch.calls if "violet-151/charizard-ex-199" in u) == 1
    assert sum(1 for u in fetch.calls if "charizard-ex-145" in u) == 1


def test_scan_card_respects_zh_page_cap_and_pc_error(quiet):
    ls = [listing(f"Charizard ex Simplified Chinese {n}/129 PSA 10", price=100.0, item_id=str(n)) for n in (101, 102, 103)]
    # 3 números distintos, teto 2: o terceiro (menos prioritário = maior preço/igual → ordem estável) fica sem página
    ebay = FakeEbay(ls)
    fetch = _fetch_factory({"violet-151/charizard-ex-199": EN_PAGE})   # busca chinesa sem fixture → PcError
    stats = Counter()
    params = {**cs.DEFAULT_PARAMS, "max_zh_pages_per_card": 2}
    rows = cs.scan_card(CARD, ebay, params, fetch=fetch, today=TODAY, stats=stats, log=lambda *a: None)
    statuses = sorted(r["zh"]["status"] for r in rows)
    assert statuses == ["pc-erro", "pc-erro", "teto-de-paginas-por-carta"]
    assert stats["pc_error"] == 2 and stats["zh_page_teto"] == 1
    assert all(r["bucket"] == "validar" for r in rows)


def test_scan_card_without_rows_skips_pricecharting(quiet):
    ebay = FakeEbay([listing("Pikachu ex Chinese PSA 10", item_id="z")])
    fetch = _fetch_factory({})
    rows = cs.scan_card(CARD, ebay, dict(cs.DEFAULT_PARAMS), fetch=fetch, today=TODAY, stats=Counter(), log=lambda *a: None)
    assert rows == [] and fetch.calls == []


def test_scan_card_counts_budget_even_when_search_raises(quiet):
    class Boom(FakeEbay):
        def search(self, query, **kw):
            self.calls += 1
            raise EbayBudgetExceeded("orçamento")
    stats = Counter()
    with pytest.raises(EbayBudgetExceeded):
        cs.scan_card(CARD, Boom([]), dict(cs.DEFAULT_PARAMS), fetch=_fetch_factory({}), today=TODAY, stats=stats, log=lambda *a: None)
    assert stats["ebay_calls"] == 1


def test_run_scan_payload_and_abort(monkeypatch, quiet):
    monkeypatch.setattr(cs.scanner, "load_watchlist", lambda path: [CARD, ROCKET])
    ebay = FakeEbay([listing("Charizard ex Simplified Chinese 199/165 PSA 10", price=300.0, item_id="c")])
    fetch = _fetch_factory({"violet-151/charizard-ex-199": EN_PAGE, "search-products": ZH_SEARCH, "charizard-ex-145": ZH_PAGE,
                            "chinese-151-collect/charizard-ex-199": ZH_PAGE})
    payload = cs.run_scan("x.yaml", group=None, params={"max_ebay_calls": 7}, log=lambda *a: None, ebay=ebay, fetch=fetch, today=TODAY)
    meta = payload["meta"]
    assert meta["kind"] == "chinese-psa10" and meta["aborted"] is False and ebay.max_calls == 7
    assert meta["scheduled"] == 2 and meta["selection"]["cards_completed"] == 2 and meta["funnel"]["ebay_calls"] == 2
    assert meta["params"]["min_ratio"] == 4.0 and meta["params"]["location_country"] == ""
    assert [r["bucket"] for r in payload["rows"]] == ["candidata"]   # ROCKET não casa "Charizard ex"
    json.dumps(payload, allow_nan=False)  # serializável

    class Boom(FakeEbay):
        def search(self, query, **kw):
            self.calls += 1
            raise EbayBudgetExceeded("orçamento")
    p2 = cs.run_scan("x.yaml", log=lambda *a: None, ebay=Boom([]), fetch=fetch, today=TODAY)
    assert p2["meta"]["aborted"] is True and p2["rows"] == [] and p2["meta"]["funnel"]["aborted_ebay"] == 1
    p3 = cs.run_scan("x.yaml", log=lambda *a: None, ebay=SimpleNamespace(configured=False, calls=0), fetch=fetch, today=TODAY)
    assert p3["meta"]["aborted"] is True


def test_run_scan_search_kwargs_any_country(monkeypatch, quiet):
    monkeypatch.setattr(cs.scanner, "load_watchlist", lambda path: [CARD])
    ebay = FakeEbay([])
    cs.run_scan("x.yaml", log=lambda *a: None, ebay=ebay, fetch=_fetch_factory({}), today=TODAY)
    q, kw = ebay.queries[0]
    assert kw["location_country"] is None and kw["graded_only"] is True and kw["fixed_price_only"] is True
    assert kw["max_pages"] == 1 and kw["limit"] == 200 and kw["min_price"] == 10.0


# --- entrega ----------------------------------------------------------------------------------
def _payload(quiet_rows):
    return {"meta": {"kind": "chinese-psa10", "timestamp": "2026-09-26T12:00:00Z", "group": "1", "watchlist_count": 98,
                     "scheduled": 1, "params": dict(cs.DEFAULT_PARAMS), "funnel": {"cards_scanned": 1, "ebay_calls": 1, "rows_candidata": 1},
                     "aborted": False, "selection": {"cards_completed": 1, "cards_deferred": 97}, "outlook_available": True},
            "rows": quiet_rows}


def test_render_all_rows_two_links_and_dispatch(quiet):
    ls = [listing("Charizard ex Simplified Chinese 199/165 PSA 10", price=300.0, item_id="c"),
          listing("PSA 10 2025 Pokemon CHN Charizard ex CSV5C 145/129 SR", price=58.0, item_id="a"),
          listing("Charizard ex Simplified Chinese 145/129 PSA 10", price=800.0, item_id="d"),
          listing("2024 POKEMON TRADITIONAL CHINESE SV-P PROMO #166 CHARIZARD EX PSA 10", price=120.0, item_id="e")]
    fetch = _fetch_factory({"violet-151/charizard-ex-199": EN_PAGE, "search-products": ZH_SEARCH, "charizard-ex-145": ZH_PAGE,
                            "chinese-151-collect/charizard-ex-199": ZH_PAGE})
    rows = cs.scan_card(CARD, FakeEbay(ls), dict(cs.DEFAULT_PARAMS), fetch=fetch, today=TODAY, stats=Counter(), log=lambda *a: None)
    md = ebay_summary.build_markdown(_payload(rows))
    assert md.startswith("# PSA 10 em chinês × PSA 10 em inglês — grupo 1")
    for r in rows:
        assert f"[oferta]({r['listing']['url']})" in md
    assert md.count("[oferta](") == 4
    assert "[ref EN](https://www.pricecharting.com/game/pokemon-scarlet-&-violet-151/charizard-ex-199)" in md
    assert "[ref ZH](https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-145)" in md
    assert "outros:" not in md and "Linhas 🟢 candidata: 1" in md
    assert "[US$1,400.00 (n=3, 90 d)](https://www.pricecharting.com/game/pokemon-scarlet-&-violet-151/charizard-ex-199)" in md
    assert "🟢 Candidatas" in md and "⚠️ Validar" in md and "🔎 Abaixo do corte" in md and "## 2. Exclusivas" in md
    assert "None" not in md and "nan" not in md
    assert "Nenhuma recomendação de compra" in md and "COMPRAR" not in md and "BUY" not in md
    assert "Funil:" in md and "Chamadas eBay: 1" in md
    # pares e exclusiva em tabelas diferentes
    pares, excl = md.split("## 2. Exclusivas")
    assert "itm/e" not in pares and "itm/e" in excl and "itm/c" in pares
    # margem contra a revenda chinesa (mediana 100 vs pedido 300 = −67%) e coluna presente nas duas tabelas
    assert "| -67% |" in pares and "Margem vs revenda ZH" in pares and "Margem vs revenda ZH" in excl
    # razão < 2× vai compacta por carta (d: 1400/800 = 1.75×), com o link do mais barato
    assert "agrupadas por carta EN" in pares and "| Charizard ex 199 (SV: Scarlet & Violet 151) | 1 | 1.8×–1.8× | US$800.00 |" in pares
    assert "itm/d" in pares


def test_render_empty_and_aborted():
    md = chinese_report.render({"meta": {"kind": "chinese-psa10", "aborted": True, "params": {}}, "rows": []})
    assert "ABORTADO" in md and md.count("_nenhuma linha_") == 5


def test_cli_writes_json_and_md(monkeypatch, tmp_path):
    import chinese_scan as cli
    rows = []
    monkeypatch.setattr(cli.chinese_scan, "run_scan", lambda *a, **k: _payload(rows))
    out = tmp_path / "zh.json"
    assert cli.main(["--group", "1", "--out", str(out)]) == 0
    assert out.exists() and (tmp_path / "zh.md").exists()
    assert json.loads(out.read_text())["meta"]["kind"] == "chinese-psa10"
    aborted = _payload(rows)
    aborted["meta"]["aborted"] = True
    monkeypatch.setattr(cli.chinese_scan, "run_scan", lambda *a, **k: aborted)
    assert cli.main(["--out", str(tmp_path / "zh2.json")]) == 1
    assert (tmp_path / "zh2.aborted.json").exists() and not (tmp_path / "zh2.json").exists()
    with pytest.raises(SystemExit):
        cli.main(["--min-ratio", "1", "--out", str(tmp_path / "x.json")])
