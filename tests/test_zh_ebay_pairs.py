"""Par EN × ZH-S raw no eBay (tools/zh_ebay_pairs): guards e tabela, tudo offline."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "zh_ebay_pairs"))

import ebay_pair  # noqa: E402
import guards  # noqa: E402

NOW = dt.datetime(2026, 10, 4, 12, 0, tzinfo=dt.timezone.utc)


def zrow(code, no, rar, how="tc-jp", en_rar="", total="100"):
    return {"cn_code": code, "cn_no": no, "cn_total": total, "cn_rar": rar, "how": how,
            "en_rar": en_rar, "jp": "s12a 234"}


# --- variante EN ------------------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("Umbreon (Master Ball Pattern)", "Master Ball Pattern"),
    ("Pikachu ex (Poke Ball Pattern)", "Poke Ball Pattern"),
    ("Eevee (Prerelease) [Staff]", "Prerelease"),
    ("Charizard ex - 199/165", None),
    ("Umbreon VMAX (Alternate Art Secret)", None),
])
def test_variant_qualifier(name, expected):
    assert guards.variant_qualifier(name) == expected


# --- escolha da impressão ZH ------------------------------------------------------
def test_pick_drops_gem_pack_rows():
    rows = [zrow("CBB1C", "01 07", "DR", how="set+illus+rar"), zrow("CSV1C", "13", "C")]
    best, multi = guards.pick_zh_row(rows, "Common")
    assert best["cn_code"] == "CSV1C" and multi is False


def test_pick_only_gem_pack_is_no_pair():
    assert guards.pick_zh_row([zrow("CBB1C", "01 07", "DR")], "Common") == (None, False)


def test_pick_gallery_prefers_special_art_over_first_row():
    # GG56 Zoroark VSTAR: o catálogo traz CS5.5C-58 (RRR) antes de CS5.5C-77 (SAR)
    rows = [zrow("CS5.5C", "58", "RRR", en_rar="RGGU", total="066"),
            zrow("CS5.5C", "77", "SAR", en_rar="RGGU", total="066")]
    best, multi = guards.pick_zh_row(rows, "Ultra Rare")
    assert best["cn_no"] == "77" and multi is False


def test_pick_other_rarity_family_is_no_pair():
    # EN SIR com só a SR chinesa no catálogo: carta bem mais barata, par falso por construção
    assert guards.pick_zh_row([zrow("CSV5C", "145", "SR")], "Special Illustration Rare") == (None, False)


def test_pick_prefers_rarity_then_tc_jp():
    rows = [zrow("CSV5C", "145", "SR"), zrow("CSV5C", "160", "SAR", how="set+rar"),
            zrow("CSV5C", "161", "SAR")]
    best, multi = guards.pick_zh_row(rows, "Special Illustration Rare")
    assert best["cn_no"] == "161" and multi is False


def test_pick_flags_tie_between_prints():
    rows = [zrow("CSV5C", "160", "SAR"), zrow("151C", "201", "SAR")]
    best, multi = guards.pick_zh_row(rows, "Special Illustration Rare")
    assert best["cn_no"] == "160" and multi is True


@pytest.mark.parametrize("en,cn,expected", [
    ("Special Illustration Rare", "SAR", True), ("Special Illustration Rare", "SR", False),
    ("Illustration Rare", "AR", True), ("Hyper Rare", "UR", True),
    ("Double Rare", "RR", True), ("Double Rare", "SR", False),
    ("Holo Rare", "R", None), ("Illustration Rare", "—", None),
])
def test_rarity_fit(en, cn, expected):
    assert guards.rarity_fit(en, zrow("X", "1", cn)) is expected


# --- nome + sufixo ----------------------------------------------------------------
@pytest.mark.parametrize("name,title,expected", [
    ("Pikachu", "Pokemon Pikachu 160/159 Chinese", True),
    ("Pikachu", "Pokemon Pikachu ex 160/159 Chinese", False),
    ("Pikachu ex", "Pokemon Pikachu 160/159 Chinese", False),
    ("Pikachu ex", "Pikachu-EX SAR CSV8C", True),
    ("Umbreon V", "Umbreon VMAX 215/203", False),
    ("Umbreon VMAX", "Umbreon VMAX 215/203", True),
    ("Mew ex", "Mewtwo ex 151", False),
    ("Team Rocket's Mewtwo ex", "Mewtwo ex SAR CSV10C", True),
    ("Charizard ex", "Charizard & Braixen GX and Charizard ex", False),
    ("Gengar & Mimikyu GX", "CSM2bC-033 RR Gengar & Mimikyu-GX Holo", True),
    ("Gengar & Mimikyu GX", "CSM2bC-033 RR Gengar Mimikyu-GX Holo NM", True),     # vendedor omite o "&"
    ("Gengar & Mimikyu GX", "Gengar GX 033", False),
    ("Gengar & Mimikyu GX", "Mimikyu GX 033", False),
])
def test_name_ok(name, title, expected):
    assert guards.name_ok(name, title) is expected


# --- caso real 2026-10-04: Gengar & Mimikyu GX (Team Up 2019) não aparecia ---------
def test_team_up_2019_is_inside_default_universe():
    assert ebay_pair.in_years({"publishedOn": "2019-02-01T00:00:00"}, ebay_pair.YEARS)
    assert not ebay_pair.in_years({"publishedOn": "2016-11-02T00:00:00"}, ebay_pair.YEARS)
    assert ebay_pair.parse_years("2022-2025") == (2022, 2025)


def test_tag_team_and_ace_spec_are_not_grading_companies():
    gm = zrow("CSM2bC", "33", "RR", how="illus+rar", total="150")
    assert guards.en_title_ok("Gengar & Mimikyu GX TAG TEAM 53/181 SM-Team Up Holo 240 HP English 2019",
                              "Gengar & Mimikyu GX", "53/181")
    assert guards.zh_title_ok("Pokemon S-Chinese Card Sun&Moon CSM2bC-033 RR Gengar & Mimikyu-GX Holo Mint New",
                              "Gengar & Mimikyu GX", gm)
    assert guards.en_title_ok("Prime Catcher ACE SPEC 157/162 Temporal Forces", "Prime Catcher", "157/162")
    assert not guards.en_title_ok("Gengar & Mimikyu GX 53/181 TAG 10 Pristine", "Gengar & Mimikyu GX", "53/181")
    assert not guards.en_title_ok("Gengar & Mimikyu GX 53/181 ACE 10", "Gengar & Mimikyu GX", "53/181")


# --- lote -------------------------------------------------------------------------
@pytest.mark.parametrize("title,expected", [
    ("Pokemon Chinese CSV5C 145/129 Charizard ex", False),
    ("Pokemon Chinese CSV5C 145/129 146/129 147/129 SR set", True),
    ("Pokemon Chinese Charizard ex lot", True),
    ("Charizard ex 199/165 x3", True),
    ("Charizard ex 199/165 Proxy", True),
])
def test_is_lot(title, expected):
    assert guards.is_lot(title) is expected


# --- título EN / ZH ---------------------------------------------------------------
@pytest.mark.parametrize("title,expected", [
    ("Charizard ex 199/165 SIR Pokemon 151 NM", True),
    ("Charizard ex 199/165 Japanese", False),
    ("Charizard ex 183/165 Pokemon 151", False),          # outra fração
    ("Charizard ex 199/165 PSA 10", False),               # graded
    ("Charizard 199/165", False),                         # sem o sufixo
    ("Charizard ex #199 Pokemon 151", True),
    ("Charizard ex 199th anniversary Pokemon", False),    # "199th" não é o número da carta
    ("Charizard ex 199/197 Obsidian Flames", False),      # mesmo nº, outro set (total difere)
    ("Charizard ex 199/0165 Pokemon 151", True),
])
def test_en_title_ok(title, expected):
    assert guards.en_title_ok(title, "Charizard ex", "199/165") is expected


def test_en_title_ok_prefixed_number():
    assert guards.en_title_ok("Hisuian Zoroark VSTAR GG56/GG70 Crown Zenith", "Hisuian Zoroark VSTAR", "GG56/GG70")
    assert not guards.en_title_ok("Hisuian Zoroark VSTAR GG55/GG70 Crown Zenith", "Hisuian Zoroark VSTAR", "GG56/GG70")


@pytest.mark.parametrize("title,expected", [
    ("Pokemon S-Chinese CSV5C 161/129 Charizard ex SAR", True),
    ("Pokemon Chinese CSV5C-161/129 Charizard ex", True),
    ("Pokemon Chinese CSV5C 145/129 Charizard ex SR", False),        # outra impressão
    ("Pokemon Traditional Chinese CSV5C 161/129 Charizard ex", False),
    ("Pokemon Chinese Japanese CSV5C 161/129 Charizard ex", False),   # outro idioma junto
    ("Pokemon CSV8C 161/129 Chinese Charizard ex", False),            # outro set
    ("Pokemon Chinese CSV5C 161/129 Charizard ex PSA 10", False),
    ("Pokemon Chinese CSV5C 161/129 Charizard", False),
    ("Pokemon Chinese CSV5C 161/151 Charizard ex", False),            # total de outra coleção
])
def test_zh_title_ok(title, expected):
    assert guards.zh_title_ok(title, "Charizard ex", zrow("CSV5C", "161", "SAR", total="129")) is expected


# --- crivo e disponibilidade ------------------------------------------------------
def test_ratio_uses_item_plus_shipping_and_none_is_zero():
    assert guards.total({"price": 40.0, "shipping": None}) == 40.0
    assert guards.pair_ratio({"price": 76.0, "shipping": 4.0}, {"price": 15.0, "shipping": 5.0}) == 4.0
    assert guards.pair_ratio({"price": 10.0, "shipping": 0}, {"price": 0.0, "shipping": 0}) is None


def item_payload(**over):
    p = {"itemId": "v1|1|0", "buyingOptions": ["FIXED_PRICE"],
         "estimatedAvailabilities": [{"estimatedAvailabilityStatus": "IN_STOCK"}],
         "price": {"value": "12.50", "currency": "USD"}}
    p.update(over)
    return p


@pytest.mark.parametrize("payload,ok,why", [
    (item_payload(), True, "a-venda"),
    (item_payload(estimatedAvailabilities=[{"estimatedAvailabilityStatus": "LIMITED_STOCK"}]), True, "a-venda"),
    (item_payload(estimatedAvailabilities=[{"estimatedAvailabilityStatus": "OUT_OF_STOCK"}]), False, "sem-estoque"),
    (item_payload(itemEndDate="2026-10-04T11:00:00.000Z"), False, "encerrado"),
    (item_payload(itemEndDate="2026-10-09T11:00:00.000Z"), True, "a-venda"),
    (item_payload(buyingOptions=["AUCTION"]), False, "nao-e-preco-fixo"),
    (item_payload(estimatedAvailabilities=[]), False, "disponibilidade-nao-informada"),
])
def test_availability(payload, ok, why):
    assert guards.availability(payload, NOW) == (ok, why)


# --- verificação na entrega + tabela ----------------------------------------------
def it(item_id, price, shipping=0.0, title="t"):
    return {"item_id": item_id, "price": price, "shipping": shipping, "title": title,
            "url": f"https://www.ebay.com/itm/{item_id}", "country": "US"}


def dump():
    def row(name, en, zh, **over):
        r = {"name": name, "set": "SV: Scarlet & Violet 151", "num": "199/165", "how": "tc-jp",
             "multi": False, "fit": True, "zh": "151C-201/151", "res": {
                 "en": {"query": "q", "err": None, "n": 9, "item": en},
                 "zh": {"query": "q", "err": None, "n": 9, "item": zh}}}
        r.update(over)
        return r
    return {"collected": "2026-10-04 12:00 UTC", "calls": 8, "selected": 4, "cands": 50, "stop": None,
            "variants_excluded": 2, "rows": [
                row("Charizard ex", it("A", 200.0), it("B", 40.0)),       # 5,0×
                row("Mew ex", it("C", 90.0), it("D", 10.0), how="set+rar"),  # 9,0×
                row("Pikachu", it("E", 30.0), it("F", 10.0)),             # 3,0× — fora
                row("Eevee", it("G", 80.0), None)]}                      # sem anúncio ZH


class FakeClient:
    def __init__(self, gone=(), prices=None, budget_at=None, shipping=None, errors=None, conds=None):
        self.gone, self.prices, self.budget_at, self.asked = set(gone), prices or {}, budget_at, []
        self.shipping, self.errors, self.conds = shipping or {}, errors or {}, conds or {}

    def get_item(self, item_id):
        if self.budget_at is not None and len(self.asked) >= self.budget_at:
            raise ebay_pair.EbayBudgetExceeded("Limite")
        self.asked.append(item_id)
        if item_id in self.errors:
            raise self.errors[item_id]
        if item_id in self.gone:
            raise ebay_pair.EbayApiError("eBay Browse API HTTP 404 Not Found (nao repetivel)")
        p = item_payload(itemId=item_id)
        if item_id in self.conds:
            p["conditionDescriptors"] = [{"name": "Card Condition", "values": [{"content": self.conds[item_id]}]}]
        if item_id in self.shipping:
            p["shippingOptions"] = [{"shippingCost": {"value": str(self.shipping[item_id]), "currency": "USD"}}]
        if item_id in self.prices:
            p["price"] = {"value": str(self.prices[item_id]), "currency": "USD"}
        else:
            p.pop("price")
        return p, "url"


def test_verify_only_checks_pairs_at_or_above_ratio():
    d = dump()
    client = FakeClient()
    ebay_pair.verify(d, client, now=NOW)
    assert sorted(client.asked) == ["A", "B", "C", "D"]
    assert [r["verified"] for r in d["rows"][:2]] == ["a-venda", "a-venda"]
    assert "verified" not in d["rows"][2]


def test_verify_drops_ended_listing_and_refreshed_price_below_ratio():
    d = dump()
    ebay_pair.verify(d, FakeClient(gone={"B"}, prices={"D": 30.0}), now=NOW)
    assert d["rows"][0]["verified"].startswith("caiu: ZH")
    assert d["rows"][1]["verified"] == ebay_pair.BELOW


def test_verify_refreshes_price_and_shipping_from_get_item():
    d = dump()
    d["rows"][0]["res"]["zh"]["item"]["shipping"] = None
    client = FakeClient(prices={"B": 41.0}, shipping={"B": 6.0})
    ebay_pair.verify(d, client, now=NOW)
    zh = d["rows"][0]["res"]["zh"]["item"]
    assert (zh["price"], zh["shipping"]) == (41.0, 6.0)
    assert d["rows"][0]["verified"] == "a-venda"            # 200 / 47 = 4,3×


def test_verify_never_adds_newly_learned_shipping_to_the_en_side():
    # EN entrou como o mais barato com frete desconhecido (conta 0); somar o frete descoberto
    # depois INFLARIA a razão — outro anúncio EN poderia ser mais barato no total.
    d = dump()
    d["rows"][0]["res"]["en"]["item"]["shipping"] = None
    ebay_pair.verify(d, FakeClient(shipping={"A": 35.0}), now=NOW)
    assert d["rows"][0]["res"]["en"]["item"]["shipping"] is None
    assert d["rows"][0]["verified"] == "a-venda"


def test_verify_transient_error_is_not_reported_as_ended():
    d = dump()
    ebay_pair.verify(d, FakeClient(errors={"B": ebay_pair.EbayApiError("HTTP 503 falhou 3x"),
                                           "D": ValueError("payload ilegível")}), now=NOW)
    assert d["rows"][0]["verified"].startswith("não verificado: ZH")
    assert d["rows"][1]["verified"].startswith("não verificado: ZH")


# --- condição: NM × NM (caso real: EN mais barato era "Heavily played") -------------
@pytest.mark.parametrize("payload,expected", [
    ({"conditionId": "4000", "conditionDescriptors": [
        {"name": "Card Condition", "values": [{"content": "Near mint or better"}]}]}, "NM"),
    ({"conditionId": "4000", "conditionDescriptors": [
        {"name": "Card Condition", "values": [{"content": "Heavily played (Poor)"}]}]}, "OUTRA"),
    ({"conditionId": "4000", "conditionDescriptors": [
        {"name": "Card Condition", "values": [{"content": "Lightly played (Excellent)"}]}]}, "OUTRA"),
    ({"conditionId": "2750", "conditionDescriptors": [{"name": "Grade", "values": [{"content": "10"}]}]}, "OUTRA"),
    ({"conditionId": "4000"}, None),
    ({}, None),
])
def test_card_condition(payload, expected):
    assert guards.card_condition(payload) == expected


@pytest.mark.parametrize("title,expected", [
    ("Gengar & Mimikyu GX TAG TEAM 53/181 English - Damaged", False),
    ("Gengar & Mimikyu GX 53/181 Team Up - HP", False),
    ("Gengar & Mimikyu GX 53/181 Team Up Heavily Played", False),
    ("Gengar & Mimikyu GX 53/181 Team Up Holo EN LP", False),
    ("Gengar & Mimikyu GX 53/181 Team Up Ultra Rare Holo 240HP English 2019", True),
    ("Gengar & Mimikyu GX 53/181 Team Up Holo 240 HP English", True),
    ("Gengar & Mimikyu GX 53/181 NM Unplayed 240-HP", True),
    ("Gengar & Mimikyu GX 53/181 Never Played Mint HP: 240", True),
    ("Gengar & Mimikyu GX 53/181 Holo 240  HP", True),
    ("Gengar & Mimikyu GX 53/181 small crease", False),
])
def test_played_titles_are_out(title, expected):
    assert guards.en_title_ok(title, "Gengar & Mimikyu GX", "53/181") is expected


def gengar():
    d = dump()
    row = d["rows"][2]                       # mais barato EN ÷ ZH = 2,4× — mas o EN barato é jogado
    row["res"]["en"].update(items=[it("HP1", 120.0), it("NM1", 300.0), it("NM2", 330.0)], median=300.0,
                            item=it("HP1", 120.0))
    row["res"]["zh"].update(items=[it("Z1", 50.0), it("Z2", 59.0)], item=it("Z1", 50.0))
    d["rows"] = [row]
    return d


def test_verify_walks_past_played_listing_to_the_cheapest_nm():
    d = gengar()
    client = FakeClient(conds={"HP1": "Heavily played (Poor)", "NM1": "Near mint or better",
                               "Z1": "Near mint or better"})
    ebay_pair.verify(d, client, now=NOW)
    row = d["rows"][0]
    assert client.asked == ["HP1", "NM1", "Z1"]
    assert (row["res"]["en"]["item"]["item_id"], row["res"]["zh"]["item"]["item_id"]) == ("NM1", "Z1")
    assert row["verified"] == "a-venda" and row["res"]["en"]["item"]["cond"] == "NM"


def test_verify_skips_pair_that_cannot_reach_ratio_even_by_median():
    d = gengar()
    d["rows"][0]["res"]["en"].update(items=[it("HP1", 120.0), it("X", 150.0)], median=150.0)  # teto 150 / 50 = 3×
    client = FakeClient()
    ebay_pair.verify(d, client, now=NOW)
    assert client.asked == [] and "verified" not in d["rows"][0]


def test_candidate_looks_at_every_listing_the_walk_can_reach():
    # 3 EN plausíveis, os 2 baratos jogados: a mediana (150) dá 3×, mas o 3º (400) dá 8×
    en = [it("a", 100.0), it("b", 150.0), it("c", 400.0)]
    assert ebay_pair._candidate(en, [it("z", 50.0)], 150.0)
    assert not ebay_pair._candidate(en[:2], [it("z", 50.0)], 150.0)


def test_verify_all_listings_played_is_declared():
    d = gengar()
    ebay_pair.verify(d, FakeClient(conds={k: "Moderately played (Very good)" for k in ("HP1", "NM1", "NM2")}), now=NOW)
    assert d["rows"][0]["verified"].startswith("caiu: EN sem anúncio NM à venda")


def test_render_flags_unknown_condition_and_counts_below(capsys):
    d = dump()
    ebay_pair.verify(d, FakeClient(prices={"D": 30.0}, conds={"A": "Near mint or better", "B": "Near mint or better"}),
                     now=NOW)
    ebay_pair.render(d)
    out = capsys.readouterr().out
    assert "1 pares ≥ 4×" in out and "1 abaixo do crivo após conferir" in out
    assert "condição não informada" not in out             # Charizard: os dois NM
    assert "Mew ex" not in out                              # abaixo do crivo: não é listado


def test_verify_budget_exhausted_is_declared_not_assumed():
    d = dump()
    ebay_pair.verify(d, FakeClient(budget_at=0), now=NOW)
    assert d["rows"][0]["verified"] == "não verificado: teto de chamadas eBay"


def test_render_only_verified_pairs_sorted_by_ratio_with_two_links(capsys):
    d = dump()
    ebay_pair.verify(d, FakeClient(), now=NOW)
    ebay_pair.render(d)
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.startswith("| ") and "itm/" in l]
    assert len(lines) == 2
    assert "Mew ex" in lines[0] and "9.0×" in lines[0] and "Charizard ex" in lines[1]
    for line in lines:
        assert line.count("https://www.ebay.com/itm/") == 2
    assert "Pikachu" not in out and "Eevee" not in out
    assert "4 cartas consultadas" in out and "3 pares com dois anúncios" in out
    assert "2 pares ≥ 4×" in out and "2 variantes EN excluídas" in out
    assert "junção fraca" in lines[0]


def test_render_declares_dropped_pairs(capsys):
    d = dump()
    ebay_pair.verify(d, FakeClient(gone={"B"}), now=NOW)
    ebay_pair.render(d)
    out = capsys.readouterr().out
    assert "1 descartado(s) na verificação" in out
    assert "Charizard ex" in out and "caiu: ZH" in out      # declarado fora da tabela
    assert len([l for l in out.splitlines() if l.startswith("| ") and "itm/" in l]) == 1


def test_render_counts_source_errors_apart_from_no_listing(capsys):
    d = dump()
    d["rows"][3]["res"]["zh"]["err"] = "erro: EbayApiError"
    ebay_pair.render(d)
    assert "1 busca(s) com erro de fonte" in capsys.readouterr().out


class SearchClient:
    def __init__(self, totals):
        self.payload = {"itemSummaries": [
            {"itemId": f"v1|{i}|0", "title": "ok", "price": {"value": str(t), "currency": "USD"},
             "itemWebUrl": f"https://www.ebay.com/itm/{i}", "buyingOptions": ["FIXED_PRICE"],
             "shippingOptions": [{"shippingCost": {"value": "0", "currency": "USD"}}]}
            for i, t in enumerate(totals)]}

    def _request_search_json(self, url):
        self.url = url
        return self.payload


def test_plausible_drops_low_outliers_and_keeps_order_and_median():
    # caso real: "Gengar & Mimikyu-GX (Alternate Art) 165/181" a US$10 numa carta de ~US$800
    client = SearchClient([10, 420, 800, 850, 900])
    items, median, err, n = ebay_pair.plausible(client, "q", lambda t: True)
    assert [i["price"] for i in items] == [420.0, 800.0, 850.0, 900.0]   # 10 < 50% da mediana
    assert (median, err, n) == (800.0, None, 5)


def test_plausible_asks_ebay_for_near_mint_ungraded_only():
    import urllib.parse
    client = SearchClient([100])
    ebay_pair.plausible(client, "q", lambda t: True)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(client.url).query)
    assert query["aspect_filter"] == ["categoryId:183454,Card Condition:{Near Mint or Better},Graded:{No}"]


def test_plausible_keeps_at_most_ten():
    items, _, _, _ = ebay_pair.plausible(SearchClient(list(range(100, 130))), "q", lambda t: True)
    assert len(items) == ebay_pair.KEEP


def test_render_without_verification_says_so(capsys):
    ebay_pair.render(dump())
    assert "NÃO verificados" in capsys.readouterr().out
