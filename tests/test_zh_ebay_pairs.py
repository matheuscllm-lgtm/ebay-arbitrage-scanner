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
])
def test_name_ok(name, title, expected):
    assert guards.name_ok(name, title) is expected


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
    def __init__(self, gone=(), prices=None, budget_at=None, shipping=None, errors=None):
        self.gone, self.prices, self.budget_at, self.asked = set(gone), prices or {}, budget_at, []
        self.shipping, self.errors = shipping or {}, errors or {}

    def get_item(self, item_id):
        if self.budget_at is not None and len(self.asked) >= self.budget_at:
            raise ebay_pair.EbayBudgetExceeded("Limite")
        self.asked.append(item_id)
        if item_id in self.errors:
            raise self.errors[item_id]
        if item_id in self.gone:
            raise ebay_pair.EbayApiError("eBay Browse API HTTP 404 Not Found (nao repetivel)")
        p = item_payload(itemId=item_id)
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
    assert d["rows"][1]["verified"] == "caiu: razão abaixo do crivo com o preço atual"


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
        return self.payload


def test_cheapest_en_keeps_true_cheapest_and_zh_drops_low_outlier():
    # tirar o EN mais barato INFLARIA a razão; no ZH, tirar o barato suspeito é conservador
    client = SearchClient([20, 45, 50, 52])
    en, _, _ = ebay_pair.cheapest(client, "q", lambda t: True, drop_low_outliers=False)
    zh, _, _ = ebay_pair.cheapest(client, "q", lambda t: True, drop_low_outliers=True)
    assert (en.price, zh.price) == (20.0, 45.0)


def test_render_without_verification_says_so(capsys):
    ebay_pair.render(dump())
    assert "NÃO verificados" in capsys.readouterr().out
