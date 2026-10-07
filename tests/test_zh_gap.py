"""Ranking chinês simplificado × inglês (carta solta) — offline.

Fixture = marcação real da página de set do PriceCharting (``/console/pokemon-chinese-csv10c``,
2026-10-07), recortada para 4 linhas: completa, sem preço, variante "[Reverse]" e promo."""
import os
from types import SimpleNamespace

import pytest

from src import zh_gap, zh_identity

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def page():
    return _read("pc_console_chinese_csv10c.html")


# --- slug do console ------------------------------------------------------------------
@pytest.mark.parametrize("code,slug", [
    ("CSV10C", "csv10c"), ("CSV9.5C", "csv95c"), ("CS4aC", "cs4ac"), ("CSM2cC", "csm2cc"),
    ("151C", "151-collect"), ("CBB1C", "gem-pack"), ("CBB3C", "gem-pack-3"),
    ("SV-P", "promo"), ("S-P", "promo"), ("SM-P", "promo"), ("30thDC", "30th-celebration"),
    ("", None), (None, None),
])
def test_console_slug(code, slug):
    assert zh_gap.console_slug(code) == slug


def test_console_slug_round_trips_with_cn_key_from_pc_url():
    # O slug gerado tem de ser o mesmo que `cn_key_from_pc_url` sabe ler de volta.
    for code, tail, want in [("CSV10C", "mewtwo-ex-268", ("csv10c", "268")),
                             ("151C", "mew-ex-191", ("151c", "191")),
                             ("CBB3C", "clefable-103", ("cbb3c", "01 03")),
                             ("SV-P", "mew-ex-3sv-p", ("sv-p", "3"))]:
        url = f"https://www.pricecharting.com/game/pokemon-chinese-{zh_gap.console_slug(code)}/{tail}"
        assert zh_identity.cn_key_from_pc_url(url) == want


def test_console_url_pagination():
    assert zh_gap.console_url("csv10c") == "https://www.pricecharting.com/console/pokemon-chinese-csv10c"
    assert zh_gap.console_url("csv10c", 150) == "https://www.pricecharting.com/console/pokemon-chinese-csv10c?cursor=150"


# --- parser da página de set ------------------------------------------------------------
def test_parse_console_page(page):
    rows = zh_gap.parse_console_page(page)
    assert [r["title"] for r in rows] == ["Team Rocket's Mewtwo Ex #268", "Arboliva ex #22",
                                          "Combusken [Reverse] #37", "Mew ex #3"]
    full = rows[0]
    assert full["url"].endswith("/pokemon-chinese-csv10c/team-rocket%27s-mewtwo-ex-268")
    assert (full["ungraded"], full["grade9"], full["psa10"]) == (140.47, 193.90, 1714.87)
    assert full["variant"] is False
    empty = rows[1]
    assert (empty["ungraded"], empty["grade9"], empty["psa10"]) == (None, None, None)
    assert rows[2]["variant"] is True and rows[2]["ungraded"] == 0.01
    assert rows[3]["url"].endswith("/pokemon-chinese-promo/mew-ex-3sv-p")


def test_parse_console_page_empty_body():
    assert zh_gap.parse_console_page("") == []
    assert zh_gap.parse_console_page("<html><title>Just a moment...</title></html>") == []


def test_fetch_console_rows_paginates_until_short_page(page):
    start = page.find('<tr id="product-')
    row = page[start:page.find("</tr>", start) + 5]
    big = "<table>" + row * zh_gap.PAGE_SIZE + "</table>"
    calls = []

    def fetch(url, cache_dir=None):
        calls.append(url)
        return big if "cursor" not in url else page

    rows, pages = zh_gap.fetch_console_rows("csv10c", fetch=fetch, log=lambda *_: None)
    assert pages == 2 and len(rows) == zh_gap.PAGE_SIZE + 4
    assert calls == ["https://www.pricecharting.com/console/pokemon-chinese-csv10c",
                     "https://www.pricecharting.com/console/pokemon-chinese-csv10c?cursor=150"]


def test_fetch_console_rows_respects_max_pages(page):
    start = page.find('<tr id="product-')
    row = page[start:page.find("</tr>", start) + 5]
    big = "<table>" + row * zh_gap.PAGE_SIZE + "</table>"
    warnings = []
    rows, pages = zh_gap.fetch_console_rows("csv10c", fetch=lambda url, cache_dir=None: big, max_pages=2,
                                            log=warnings.append)
    assert pages == 2 and len(rows) == 2 * zh_gap.PAGE_SIZE
    assert warnings and "teto" in warnings[0]


# --- junção catálogo × preços × referência EN ---------------------------------------------
def _catalog():
    return zh_identity.Catalog([
        {"cn_code": "CSV10C", "cn_no": "268", "cn_rar": "SAR", "en_name": "Team Rocket's Mewtwo ex",
         "en_set": "SV10: Destined Rivals", "en_no": "231", "en_rar": "Special Illustration Rare", "how": "tc-jp",
         "zh_name": "火箭队的超梦ex"},
        {"cn_code": "CSV10C", "cn_no": "22", "cn_rar": "RR", "en_name": "Arboliva ex", "en_set": "SV10: Destined Rivals",
         "en_no": "22", "en_rar": "Double Rare", "how": "set+rar"},
        {"cn_code": "CSV10C", "cn_no": "37", "cn_rar": "C", "en_name": "Combusken", "en_set": "SV10: Destined Rivals",
         "en_no": "37", "en_rar": "Common", "how": "tc-jp"},
        # SV-P 3 ambíguo: duas cartas EN diferentes → fica fora (nunca chuta)
        {"cn_code": "SV-P", "cn_no": "3", "cn_rar": "—", "en_name": "Mew ex", "en_set": "SV: Paldean Fates",
         "en_no": "232", "en_rar": "SIR", "how": "illus+rar"},
        {"cn_code": "SV-P", "cn_no": "3", "cn_rar": "—", "en_name": "Mew ex", "en_set": "SV: Scarlet & Violet 151",
         "en_no": "205", "en_rar": "SIR", "how": "illus+rar"},
    ])


def _ref(market, url="https://www.tcgplayer.com/product/1"):
    return SimpleNamespace(market_usd=market, product_url=url, group_name="SV10: Destined Rivals")


def test_build_rows_ratio_floor_and_funnel(page):
    pc = {"csv10c": zh_gap.parse_console_page(page)}
    refs = {("SV10: Destined Rivals", "231"): _ref(560.0), ("SV10: Destined Rivals", "22"): _ref(4.0)}
    rows, funnel = zh_gap.build_rows(_catalog(), pc, lambda pair: refs.get((pair["en_set"], str(pair["en_no"]))),
                                     {"min_en_usd": 10.0})
    assert len(rows) == 1
    r = rows[0]
    assert r["en_name"] == "Team Rocket's Mewtwo ex" and r["cn_no"] == "268" and r["match"] == "exata"
    assert r["zh_ungraded"] == 140.47 and r["zh_psa10"] == 1714.87 and r["en_market"] == 560.0
    assert r["ratio"] == pytest.approx(560.0 / 140.47) and r["discount"] == pytest.approx(1 - 140.47 / 560.0)
    assert r["en_url"] == "https://www.tcgplayer.com/product/1"
    assert r["zh_url"].endswith("/team-rocket%27s-mewtwo-ex-268")
    # Arboliva: sem preço raw chinês; Combusken: variante [Reverse]; promo: par ambíguo
    assert funnel["pc-linhas"] == 4 and funnel["linhas"] == 1
    assert funnel["zh-sem-preco-raw"] == 1 and funnel["pc-variante-ignorada"] == 1 and funnel["par-ambiguo"] == 1


def test_build_rows_en_floor_and_missing_reference(page):
    pc = {"csv10c": zh_gap.parse_console_page(page)}
    rows, funnel = zh_gap.build_rows(_catalog(), pc, lambda pair: _ref(9.99), {"min_en_usd": 10.0})
    assert rows == [] and funnel["en-abaixo-do-piso"] == 1
    rows, funnel = zh_gap.build_rows(_catalog(), pc, lambda pair: None, {"min_en_usd": 10.0})
    assert rows == [] and funnel["en-sem-referencia-tcg"] == 1


def test_build_rows_sorted_by_ratio_desc():
    pc = {"x": [{"url": "https://www.pricecharting.com/game/pokemon-chinese-csv10c/a-1", "title": "A #1",
                 "ungraded": 10.0, "grade9": None, "psa10": None, "variant": False},
                {"url": "https://www.pricecharting.com/game/pokemon-chinese-csv10c/b-2", "title": "B #2",
                 "ungraded": 2.0, "grade9": None, "psa10": None, "variant": False}]}
    cat = zh_identity.Catalog([
        {"cn_code": "CSV10C", "cn_no": "1", "en_name": "A", "en_set": "S", "en_no": "1", "how": "tc-jp"},
        {"cn_code": "CSV10C", "cn_no": "2", "en_name": "B", "en_set": "S", "en_no": "2", "how": "tc-jp"},
    ])
    rows, _ = zh_gap.build_rows(cat, pc, lambda pair: _ref(20.0), {"min_en_usd": 10.0})
    assert [r["en_name"] for r in rows] == ["B", "A"] and rows[0]["ratio"] == 10.0


# --- oferta no eBay ----------------------------------------------------------------------
def _listing(title, price, shipping=0.0, url="https://www.ebay.com/itm/1", country="CN"):
    return SimpleNamespace(title=title, price=price, shipping=shipping, url=url, country=country)


ROW = {"en_name": "Team Rocket's Mewtwo ex", "cn_no": "268/212", "en_no": "231"}


def test_offer_query_uses_base_name_and_chinese_number():
    q = zh_gap.offer_query(ROW)
    assert q.startswith("mewtwo ex 268 ") and "chinese" in q and "简体" in q


def test_pick_offer_cheapest_raw_chinese_only():
    listings = [
        _listing("Pokemon Chinese Mewtwo ex 268/212 SAR CSV10C PSA 10", 90.0),          # gradada: fora
        _listing("Mewtwo ex 268/212 SAR Simplified Chinese CSV10C NM", 120.0, 5.0, "https://www.ebay.com/itm/2"),
        _listing("Mewtwo ex 268/212 S-Chinese raw", 118.0, 9.0, "https://www.ebay.com/itm/3"),
        _listing("Mewtwo ex 231/182 SIR English NM", 60.0),                                # inglês: fora
        _listing("Mewtwo ex 268 Chinese lot x3", 50.0),                                    # lote: fora
        _listing("Charizard ex 268 Chinese", 40.0),                                        # outra carta: fora
        _listing("Mewtwo ex 199 Chinese NM", 40.0),                                        # outro número: fora
    ]
    o = zh_gap.pick_offer(listings, ROW)
    assert o["url"] == "https://www.ebay.com/itm/2" and o["total"] == 125.0 and o["language"] == "simplificado"


def test_pick_offer_gem_pack_requires_pack_and_card_number():
    # Caso real (07/10): "Eevee 04 07" (Gem Pack vol. 4, carta 07) casava com "Eevee 7 Chinese"
    # de outro set a US$1.30 e inflava a razão para 60×.
    row = {"en_name": "Eevee", "cn_no": "04 07", "en_no": "188"}
    assert zh_gap.offer_query(row).startswith("eevee gem pack 4/07 ")
    wrong = _listing("Pokemon Chinese Eevee 7 151C NM", 1.30)
    right = _listing("Pokemon TCG S-Chinese Gem Pack Vol.4 Eevee 04/07 AR", 9.99, url="https://www.ebay.com/itm/44")
    assert zh_gap.pick_offer([wrong], row) is None
    assert zh_gap.pick_offer([wrong, right], row)["url"] == "https://www.ebay.com/itm/44"
    assert zh_gap.pick_offer([_listing("Chinese Gem Pack 4-7 Eevee", 5.0)], row) is not None


def test_pick_offer_none_when_only_graded():
    assert zh_gap.pick_offer([_listing("Mewtwo ex 268 Chinese PSA 9", 10.0)], ROW) is None
    assert zh_gap.pick_offer([], ROW) is None


def test_attach_offers_budget_and_failure():
    rows = [dict(ROW, cn_code="CSV10C") for _ in range(3)]
    calls = []

    def search(q, **kw):
        calls.append(q)
        if len(calls) == 2:
            raise RuntimeError("orçamento")
        return [_listing("Mewtwo ex 268/212 Chinese NM", 100.0)]

    n = zh_gap.attach_offers(rows, search, max_calls=5, limit=50, log=lambda *_: None)
    assert n == 1 and rows[0]["offer"]["total"] == 100.0 and rows[1]["offer"] is None and "offer_searched" not in rows[2]


# --- entrega: dois links em TODA linha ------------------------------------------------------
def _row(ratio=4.0, offer=None, searched=True):
    return {"ratio": ratio, "discount": 1 - 1 / ratio, "en_market": 100.0, "zh_ungraded": 100.0 / ratio, "zh_psa10": None,
            "en_name": "Mew ex", "en_no": "232", "en_set": "SV: Paldean Fates", "en_rar": "SIR", "cn_no": "191",
            "cn_code": "151C", "match": "exata", "en_url": "https://www.tcgplayer.com/product/9",
            "zh_url": "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191",
            "offer": offer, "offer_searched": searched}


def test_render_markdown_two_links_per_row_and_ratio_cut():
    offer = {"price": 50.0, "shipping": 5.0, "total": 55.0, "url": "https://www.ebay.com/itm/7", "title": "t",
             "country": "CN", "language": "simplificado"}
    rows = [_row(5.0, offer), _row(3.5), _row(2.0, searched=False)]
    meta = {"generated_at": "2026-10-07T00:00:00Z", "params": {"min_en_usd": 10.0}, "funnel": {"linhas": 3},
            "sets": 1, "pages": 1, "ebay_calls": 2}
    chat = zh_gap.render_markdown(rows, meta, min_ratio=3.0)
    lines = [l for l in chat.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    assert len(lines) == 2
    for l in lines:
        assert "[ref EN](https://www.tcgplayer.com/product/9)" in l and "[ref ZH](https://www.pricecharting.com/game/" in l
    assert "[oferta](https://www.ebay.com/itm/7)" in lines[0] and "US$50.00 + US$5.00" in lines[0]
    assert "| 1.8× |" in lines[0]          # razão EN÷oferta = 100 ÷ 55
    assert lines[1].count("|") == lines[0].count("|") == zh_gap._HEADER.splitlines()[0].count("|")
    assert "sem anúncio raw chinês no eBay" in lines[1]
    assert "razão ≥ 3×" in chat and "2 linhas" in chat
    full = zh_gap.render_markdown(rows, meta)
    assert sum(1 for l in full.splitlines() if l.startswith("| ") and not l.startswith("| #")) == 3
    assert "não buscado" in full
