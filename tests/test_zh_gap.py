"""Ranking chinês simplificado × inglês (carta solta) — offline.

Fixture = marcação real da página de set do PriceCharting (``/console/pokemon-chinese-csv10c``,
2026-10-07), recortada para 4 linhas: completa, sem preço, variante "[Reverse]" (sintética a partir
de uma linha real) e promo (idem). Títulos de anúncio dos testes de oferta = títulos reais lidos
na coleta de 07/10 ou formatos vistos nela."""
import os
from types import SimpleNamespace

import pytest

from src import ebay_api, pc_sales, zh_gap, zh_identity

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def page():
    return _read("pc_console_chinese_csv10c.html")


def _first_row(page):
    start = page.find('<tr id="product-')
    return page[start:page.find("</tr>", start) + 5]


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
    assert (rows[1]["ungraded"], rows[1]["grade9"], rows[1]["psa10"]) == (None, None, None)
    assert rows[2]["variant"] is True and rows[2]["ungraded"] == 0.01
    assert rows[3]["url"].endswith("/pokemon-chinese-promo/mew-ex-3sv-p")


def test_parse_console_page_empty_body():
    assert zh_gap.parse_console_page("") == []
    assert zh_gap.parse_console_page("<html><title>Just a moment...</title></html>") == []


def test_fetch_console_rows_paginates_until_short_page(page):
    big = "<table>" + _first_row(page) * zh_gap.PAGE_SIZE + "</table>"
    calls = []

    def fetch(url, cache_dir=None):
        calls.append(url)
        return big if "cursor" not in url else page

    rows, pages, partial = zh_gap.fetch_console_rows("csv10c", fetch=fetch, log=lambda *_: None)
    assert (pages, partial, len(rows)) == (2, False, zh_gap.PAGE_SIZE + 4)
    assert calls == ["https://www.pricecharting.com/console/pokemon-chinese-csv10c",
                     "https://www.pricecharting.com/console/pokemon-chinese-csv10c?cursor=150"]


def test_fetch_console_rows_respects_max_pages(page):
    big = "<table>" + _first_row(page) * zh_gap.PAGE_SIZE + "</table>"
    warnings = []
    rows, pages, partial = zh_gap.fetch_console_rows("csv10c", fetch=lambda url, cache_dir=None: big, max_pages=2,
                                                     log=warnings.append)
    assert (pages, partial, len(rows)) == (2, True, 2 * zh_gap.PAGE_SIZE)
    assert warnings and "teto" in warnings[0]


def test_fetch_console_rows_keeps_pages_before_a_failure(page):
    big = "<table>" + _first_row(page) * zh_gap.PAGE_SIZE + "</table>"

    def fetch(url, cache_dir=None):
        if "cursor" in url:
            raise pc_sales.PcError("PriceCharting HTTP 403 e rota reserva falhou")
        return big

    warnings = []
    rows, pages, partial = zh_gap.fetch_console_rows("csv10c", fetch=fetch, log=warnings.append)
    assert (pages, partial, len(rows)) == (1, True, zh_gap.PAGE_SIZE)
    assert warnings and "parcial" in warnings[0]
    # Falha logo na primeira página: nada lido → o erro sobe (o CLI registra FALHOU)
    def fail(url, cache_dir=None):
        raise pc_sales.PcError("x")

    with pytest.raises(pc_sales.PcError):
        zh_gap.fetch_console_rows("csv10c", fetch=fail, log=lambda *_: None)


# --- identidade: título da página chinesa × carta EN ------------------------------------------
@pytest.mark.parametrize("pc_title,en_name,ok", [
    ("Team Rocket's Mewtwo Ex #268", "Team Rocket's Mewtwo ex", True),
    ("Mewtwo Ex #268", "Mew ex", False),                               # palavra inteira
    ("Ice Rider Calyrex VMAX #162", "Ice Rider Calyrex VMAX", True),
    ("Ice Rider Calyrex #162", "Ice Rider Calyrex VMAX", False),        # mesmo número, carta diferente
    ("Dawn Wings Necrozma GX #64", "Dusk Mane Necrozma-GX", False),     # catálogo set+rar trocou as formas
    ("Dusk Mane Necrozma GX #64", "Dusk Mane Necrozma-GX", True),
    ("Janine's Secret Art #250", "Janine's Secret Art", True),         # dono fora do nome-base
    ("Hero's Cape #187", "Hero's Cape", True),
    ("Dragonite GX #176", "Dragonite-GX", True),
    ("Flabebe #12", "Flabébé", True),                                   # acentos
    ("Zapdosex #190", "Zapdos ex", True),                               # site emendou as palavras
    ("Secret Rare Full Art #250", "Janine's Secret Art", False),        # frase, não palavras soltas
    ("Zeraora V #55", "Zeraora", False),                                # EN sem sufixo ≠ título com V
    ("Zeraora #210", "Zeraora", True),
    ("", "Mew ex", False), ("Mew ex #3", "", False),
])
def test_title_matches_en(pc_title, en_name, ok):
    assert zh_gap.title_matches_en(pc_title, en_name) is ok


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


def test_build_rows_zh_floor(page):
    # Operador (07/10): a carta chinesa também tem de valer algo (sinal de chase); piso elevado para
    # US$50 ainda em 07/10. O Mewtwo da fixture vale US$140,47 raw em chinês: passa com piso 50 e cai com 200.
    pc = {"csv10c": zh_gap.parse_console_page(page)}
    rows, funnel = zh_gap.build_rows(_catalog(), pc, lambda pair: _ref(560.0), {"min_en_usd": 10.0, "min_zh_usd": 50.0})
    assert len(rows) == 1 and funnel["zh-abaixo-do-piso"] == 0
    rows, funnel = zh_gap.build_rows(_catalog(), pc, lambda pair: _ref(560.0), {"min_en_usd": 10.0, "min_zh_usd": 200.0})
    assert rows == [] and funnel["zh-abaixo-do-piso"] == 1
    assert zh_gap.DEFAULT_PARAMS["min_zh_usd"] == 50.0


def _pc(slug, tail, title, ungraded):
    return {"url": f"https://www.pricecharting.com/game/pokemon-chinese-{slug}/{tail}", "title": title,
            "ungraded": ungraded, "grade9": None, "psa10": None, "variant": False}


def test_build_rows_same_number_twice_keeps_only_the_matching_title():
    # Caso real (07/10): o PriceCharting tem "Ice Rider Calyrex #162" (US$32.73) e
    # "Ice Rider Calyrex VMAX #162" (US$11.50) no mesmo console; o catálogo só conhece a VMAX.
    pc = {"cs3bc": [_pc("cs3bc", "ice-rider-calyrex-162", "Ice Rider Calyrex #162", 32.73),
                    _pc("cs3bc", "ice-rider-calyrex-vmax-162", "Ice Rider Calyrex VMAX #162", 11.50),
                    _pc("cs3bc", "dawn-wings-necrozma-gx-64", "Dawn Wings Necrozma GX #64", 2.87)]}
    cat = zh_identity.Catalog([
        {"cn_code": "CS3bC", "cn_no": "162", "en_name": "Ice Rider Calyrex VMAX", "en_set": "SWSH06: Chilling Reign",
         "en_no": "203", "how": "tc-jp"},
        {"cn_code": "CS3bC", "cn_no": "64", "en_name": "Dusk Mane Necrozma-GX", "en_set": "SM - Ultra Prism",
         "en_no": "145", "how": "set+rar"},
    ])
    rows, funnel = zh_gap.build_rows(cat, pc, lambda pair: _ref(39.59), {"min_en_usd": 10.0, "min_zh_usd": 0.0})
    assert [(r["zh_title"], r["zh_ungraded"]) for r in rows] == [("Ice Rider Calyrex VMAX #162", 11.50)]
    assert funnel["pc-titulo-nao-casa"] == 2


def test_build_rows_sorted_by_ratio_desc():
    pc = {"x": [_pc("csv10c", "a-1", "A #1", 20.0), _pc("csv10c", "b-2", "B #2", 10.0)]}
    cat = zh_identity.Catalog([
        {"cn_code": "CSV10C", "cn_no": "1", "en_name": "A", "en_set": "S", "en_no": "1", "how": "tc-jp"},
        {"cn_code": "CSV10C", "cn_no": "2", "en_name": "B", "en_set": "S", "en_no": "2", "how": "tc-jp"},
    ])
    rows, _ = zh_gap.build_rows(cat, pc, lambda pair: _ref(100.0), {"min_en_usd": 10.0, "min_zh_usd": 0.0})
    assert [r["en_name"] for r in rows] == ["B", "A"] and rows[0]["ratio"] == 10.0


# --- oferta no eBay ----------------------------------------------------------------------
def _listing(title, price, shipping=0.0, url="https://www.ebay.com/itm/1", country="CN"):
    return SimpleNamespace(title=title, price=price, shipping=shipping, url=url, country=country)


ROW = {"en_name": "Team Rocket's Mewtwo ex", "cn_no": "268/212", "en_no": "231", "cn_code": "CSV10C"}


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


@pytest.mark.parametrize("title", [
    "Mewtwo ex 268/212 Chinese ACE 10",            # certificadora fora da allowlist ≠ carta solta
    "Mewtwo ex 268/212 Chinese AGS 10 Gem Mint",
    "Mewtwo ex 268/212 Chinese PSA graded slab",   # sigla sem nota: ambíguo, não é raw
    "Mewtwo ex 268/212 Chinese PSA 9",
    "Mew ex 268/212 Chinese NM",                   # "mew" não é "mewtwo"
    "Mewtwo ex 268/212 Chinese CS5aC NM",          # código de set conflitante
    "Mewtwo ex 1268 Chinese NM",                   # número colado em outro
    "Mewtwo ex Chinese SM268b NM",                 # número dentro de um código
    "Mewtwo ex Chinese 55/122 268 HP",             # pontos de vida, não número
])
def test_pick_offer_rejects(title):
    assert zh_gap.pick_offer([_listing(title, 10.0)], ROW) is None


@pytest.mark.parametrize("row,title", [
    # Casos reais da coleta de 07/10 que passavam com palavras soltas
    ({"en_name": "Janine's Secret Art", "cn_no": "250", "en_no": "173", "cn_code": "CSV9.5C"},
     "Duraludon ex 250/222 Secret Rare SR Full Art Holo Chinese"),
    ({"en_name": "Zeraora", "cn_no": "210", "en_no": "151", "cn_code": "CSV9C"},
     "Pokémon Zeraora V Rapid Strike Holo 055/122 Chinese 210 HP"),
    ({"en_name": "Blastoise", "cn_no": "8", "en_no": "25", "cn_code": "CSM2aC"},
     "Blastoise GX 107/150 Pokémon TCG Chinese Holo RR HP 250 SM8b"),
])
def test_pick_offer_rejects_other_card_with_same_words_or_number(row, title):
    assert zh_gap.pick_offer([_listing(title, 3.0)], row) is None


@pytest.mark.parametrize("row,title", [
    # Casos reais de 07/10 apontados pelo operador: o anúncio era de OUTRA carta
    ({"en_name": "Charizard V", "cn_no": "132", "en_no": "154", "cn_code": "CS5aC"},
     "Pokemon Promo 132/S-P Charizard V Chinese Holo Mint Card Charizard V"),      # promo tradicional 132/S-P
    ({"en_name": "Charizard V", "cn_no": "132", "en_no": "154", "cn_code": "CS5aC"},
     "Charizard V 132 SV-P Chinese Holo"),                                           # código de promo solto
    ({"en_name": "Charizard V", "cn_no": "132", "en_no": "154", "cn_code": "CS5aC"},
     "Pokemon Chinese Promo Charizard V 132 Holo"),                                  # "promo" e a linha não é promo
])
def test_pick_offer_rejects_promo_of_another_set(row, title):
    assert zh_gap.pick_offer([_listing(title, 14.99)], row) is None


def test_pick_offer_accepts_promo_for_promo_row():
    row = {"en_name": "Magikarp", "cn_no": "24", "en_no": "203", "cn_code": "SV-P"}
    assert zh_gap.pick_offer([_listing("Pokemon Chinese Promo Magikarp 24/SV-P Holo NM", 80.0)], row) is not None
    assert zh_gap.pick_offer([_listing("Magikarp SVP 024 Simplified Chinese promo", 80.0)], row) is not None


def test_pick_offer_skips_new_seller_and_reports_feedback():
    # Caso real de 07/10: título certo ("Mew ex 151C #191/151"), foto de outra carta, vendedor com 0
    # avaliações. Título não denuncia; a única pista é o vendedor. Sem o dado (testes antigos) passa.
    row = {"en_name": "Mew ex", "cn_no": "191", "en_no": "232", "cn_code": "151C"}
    scam = _listing("2025 Pokemon TCG S-Chinese Mew ex 151C #191/151 SAR Full Art", 133.0, 3.99)
    scam.seller_feedback_score = 0
    ok = _listing("Pokemon S-Chinese Mew ex 151C 191/151 SAR NM", 180.0, 0.0, "https://www.ebay.com/itm/9")
    ok.seller_feedback_score = 412
    o = zh_gap.pick_offer([scam, ok], row)
    assert o["url"] == "https://www.ebay.com/itm/9" and o["seller_feedback"] == 412
    assert zh_gap.pick_offer([scam], row) is None
    scam.seller_feedback_score = zh_gap.DEFAULT_PARAMS["min_seller_feedback"]
    assert zh_gap.pick_offer([scam], row) is not None
    assert zh_gap.DEFAULT_PARAMS["min_seller_feedback"] == 5


def test_row_md_shows_seller_feedback():
    r = {"en_name": "Mew ex", "en_no": "232", "en_set": "S", "en_rar": "SIR", "cn_no": "191", "cn_code": "151C",
         "zh_title": "Mew ex #191", "match": "exata", "en_market": 800.0, "zh_ungraded": 200.0, "zh_psa10": None,
         "ratio": 4.0, "discount": 0.75, "en_url": "https://e", "zh_url": "https://z",
         "offer": {"price": 180.0, "shipping": 0.0, "total": 180.0, "url": "https://o", "title": "t",
                   "country": "CN", "language": "simplificado", "seller_feedback": 412}}
    assert "vendedor 412 aval." in zh_gap._row_md(1, r)


def test_pick_offer_accepts_phrase_with_suffix_anywhere():
    row = {"en_name": "Zapdos ex", "cn_no": "190", "en_no": "202", "cn_code": "151C"}
    assert zh_gap.pick_offer([_listing("Pokemon Chinese 151C Zapdos ex SAR 190/165 NM", 30.0)], row) is not None
    row = {"en_name": "Dragonite-GX", "cn_no": "176", "en_no": "229", "cn_code": "CSM2aC"}
    assert zh_gap.pick_offer([_listing("Pokemon TCG S-Chinese Sun&Moon CSM2aC-176 SR Dragonite GX Holo", 9.96)], row) is not None


def test_pick_offer_accepts_zero_padded_number_and_matching_code():
    row = {"en_name": "Arboliva ex", "cn_no": "22", "en_no": "22", "cn_code": "CSV10C"}
    o = zh_gap.pick_offer([_listing("Pokemon TCG S-Chinese CSV10C Arboliva ex 022/208 NM", 3.0)], row)
    assert o is not None and o["total"] == 3.0


def test_pick_offer_unknown_shipping_is_not_free():
    # Frete calculado no checkout vem como None na Browse API (14% dos anúncios reais).
    o = zh_gap.pick_offer([_listing("Mewtwo ex 268/212 Chinese NM", 10.0, shipping=None)], ROW)
    assert o["shipping"] is None and o["total"] is None and o["price"] == 10.0
    md = zh_gap._row_md(1, {**_row(2.0, o)})
    assert "US$10.00 + frete n/d" in md and "10.0× (sem frete)" in md


def test_pick_offer_skips_listing_without_price():
    assert zh_gap.pick_offer([_listing("Mewtwo ex 268/212 Chinese NM", None)], ROW) is None


@pytest.mark.parametrize("title,cn_no", [
    ("Pokemon Litten CBB4C-20-07/07 Gem Pack Vol 4 Simplified Chinese Holo NM", "20 07"),   # real
    ("Pokemon S-Chinese Gem Pack Vol.4 Cinccino CBB4C-16 07/07 Holo NM US SELLER", "16 07"),  # real
    ("Pokemon TCG S-Chinese Gem Pack Vol.4 Eevee 04/07 AR", "04 07"),
    ("Chinese Gem Pack Eevee #607", "06 07"),
    ("Chinese Gem Pack Vol 5 Eevee 1205/07", "12 05"),
    ("Chinese Gem Pack Eevee 0104/15", "01 04"),
])
def test_pick_offer_gem_pack_title_formats(title, cn_no):
    name = "Litten" if "Litten" in title else "Cinccino" if "Cinccino" in title else "Eevee"
    row = {"en_name": name, "cn_no": cn_no, "en_no": "1", "cn_code": "CBB4C" if "CBB4C" in title else "CBB5C"}
    assert zh_gap.pick_offer([_listing(title, 9.99)], row) is not None


def test_pick_offer_gem_pack_rejects_loose_number():
    # Caso real (07/10): "Eevee 04 07" casava com "Eevee 7 Chinese" de outro set a US$1.30 (razão 60×).
    row = {"en_name": "Eevee", "cn_no": "04 07", "en_no": "188", "cn_code": "CBB4C"}
    assert zh_gap.offer_query(row).startswith("eevee gem pack 4/07 ")
    assert zh_gap.pick_offer([_listing("Pokemon Chinese Eevee 7 151C NM", 1.30)], row) is None
    assert zh_gap.pick_offer([_listing("Pokemon Chinese Eevee 47 NM", 1.30)], row) is None


def test_attach_offers_budget_errors_and_stop():
    rows = [dict(ROW) for _ in range(4)]
    calls = []

    def search(q, **kw):
        calls.append(q)
        if len(calls) == 2:
            raise RuntimeError("timeout")
        return [_listing("Mewtwo ex 268/212 Chinese NM", 100.0)]

    n = zh_gap.attach_offers(rows, search, max_calls=3, limit=50, log=lambda *_: None)
    assert n == 3 and rows[0]["offer"]["total"] == 100.0                      # tentativa com erro conta
    assert rows[1]["offer"] is None and "timeout" in rows[1]["offer_error"]   # erro de uma linha segue
    assert rows[2]["offer"]["total"] == 100.0
    assert "offer" not in rows[3] and "offer_searched" not in rows[3]          # teto de chamadas

    def budget(q, **kw):
        raise ebay_api.EbayBudgetExceeded("500 chamadas")

    rows = [dict(ROW) for _ in range(2)]
    assert zh_gap.attach_offers(rows, budget, max_calls=5, limit=50, log=lambda *_: None) == 1
    assert "offer_searched" not in rows[1] and "offer" not in rows[1]           # orçamento esgotado para tudo

    def always_fails(q, **kw):
        raise RuntimeError("x")

    rows = [dict(ROW) for _ in range(5)]
    zh_gap.attach_offers(rows, always_fails, max_calls=5, limit=50, log=lambda *_: None, max_consecutive_errors=3)
    assert sum(1 for r in rows if r.get("offer_error")) == 3                   # para após 3 seguidos


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
            "sets": 1, "pages": 1, "ebay_calls": 2, "partial_sets": ["csv10c"]}
    chat = zh_gap.render_markdown(rows, meta, min_ratio=3.0)
    lines = [l for l in chat.splitlines() if l.startswith("| ") and not l.startswith("| #")]
    assert len(lines) == 2
    for l in lines:
        assert "[ref EN](https://www.tcgplayer.com/product/9)" in l and "[ref ZH](https://www.pricecharting.com/game/" in l
        assert l.count("|") == zh_gap._HEADER.splitlines()[0].count("|")
    assert "[oferta](https://www.ebay.com/itm/7)" in lines[0] and "US$50.00 + US$5.00" in lines[0]
    assert "| 1.8× |" in lines[0]          # razão EN÷oferta = 100 ÷ 55
    assert "sem anúncio raw chinês no eBay" in lines[1]
    assert "razão ≥ 3×" in chat and "2 linhas" in chat and "sets parciais: csv10c" in chat
    full = zh_gap.render_markdown(rows, meta)
    assert sum(1 for l in full.splitlines() if l.startswith("| ") and not l.startswith("| #")) == 3
    assert "não buscado" in full
    err = _row(4.0, searched=False)
    err["offer_error"] = "timeout"
    assert "busca falhou" in zh_gap._row_md(1, err)
