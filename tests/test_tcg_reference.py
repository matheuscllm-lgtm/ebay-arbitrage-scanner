"""Testes offline do cliente tcgcsv (referencia TCGplayer).

Fixtures JSON locais (dicts) + monkeypatch do `_fetch_json` -- nenhuma rede.
"""
from src import tcg_reference
from src.models import WatchCard


def card(**kw):
    defaults = dict(name="Charizard", set_name="Base Set", number="4",
                    language="EN", pc_url="")
    defaults.update(kw)
    return WatchCard(**defaults)


GROUPS = {"results": [
    {"groupId": 604, "name": "Base Set", "abbreviation": "BS"},
    {"groupId": 23237, "name": "SV: Scarlet & Violet 151", "abbreviation": "MEW"},
]}

PRODUCTS = {"results": [
    {"productId": 100, "name": "Charizard",
     "url": "https://www.tcgplayer.com/product/100",
     "extendedData": [{"name": "Number", "value": "4/102"},
                      {"name": "Rarity", "value": "Holo Rare"}]},
    {"productId": 101, "name": "Blastoise",
     "url": "https://www.tcgplayer.com/product/101",
     "extendedData": [{"name": "Number", "value": "2/102"}]},
    # Mesmo numero de outro card (variante) -- o nome desempata.
    {"productId": 102, "name": "Charizard - Art Series",
     "url": "https://www.tcgplayer.com/product/102",
     "extendedData": [{"name": "Number", "value": "40/102"}]},
]}

PRICES = {"results": [
    {"productId": 100, "subTypeName": "Holofoil",
     "marketPrice": 412.5, "midPrice": 500.0, "lowPrice": 300.0},
    {"productId": 101, "subTypeName": "Holofoil",
     "marketPrice": None, "midPrice": 180.0, "lowPrice": 120.0},
]}


def patch_fetch(monkeypatch, groups=GROUPS, products=PRODUCTS, prices=PRICES):
    def fake_fetch(url, cache_dir=None):
        if url.endswith("/groups"):
            return groups
        if url.endswith("/products"):
            return products
        if url.endswith("/prices"):
            return prices
        raise AssertionError(f"URL inesperada: {url}")
    monkeypatch.setattr(tcg_reference, "_fetch_json", fake_fetch)


def test_happy_path_number_plus_name(monkeypatch):
    patch_fetch(monkeypatch)
    ref = tcg_reference.get_tcg_reference(card())
    assert ref is not None
    assert ref.market_usd == 412.5
    assert ref.product_url == "https://www.tcgplayer.com/product/100"
    assert ref.group_name == "Base Set"
    assert ref.sub_type == "Holofoil"


def test_set_match_is_exact_case_insensitive(monkeypatch):
    patch_fetch(monkeypatch)
    assert tcg_reference.get_tcg_reference(card(set_name="base set")) is not None
    # Match parcial NAO resolve (nunca chutar set errado).
    assert tcg_reference.get_tcg_reference(card(set_name="Base")) is None


def test_tcg_set_override(monkeypatch):
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 200, "name": "Mew ex",
         "url": "https://www.tcgplayer.com/product/200",
         "extendedData": [{"name": "Number", "value": "151/165"}]},
    ]}, prices={"results": [
        {"productId": 200, "subTypeName": "Normal", "marketPrice": 33.0},
    ]})
    c = card(name="Mew ex", set_name="151", number="151")
    # Sem override: "151" nao bate com "SV: Scarlet & Violet 151" -> None.
    assert tcg_reference.get_tcg_reference(c) is None
    # Com override da watchlist: resolve.
    c2 = card(name="Mew ex", set_name="151", number="151",
              tcg_set="SV: Scarlet & Violet 151")
    ref = tcg_reference.get_tcg_reference(c2)
    assert ref is not None and ref.market_usd == 33.0


def test_no_market_price_returns_none(monkeypatch):
    # Blastoise tem midPrice/lowPrice mas marketPrice=None -> None
    # (nunca degradar pra mid/low silenciosamente).
    patch_fetch(monkeypatch)
    ref = tcg_reference.get_tcg_reference(card(name="Blastoise", number="2"))
    assert ref is None


def test_unresolved_set_returns_none(monkeypatch):
    patch_fetch(monkeypatch)
    assert tcg_reference.get_tcg_reference(card(set_name="Jungle")) is None


def test_number_match_requires_name_confirmation(monkeypatch):
    # Numero 4 existe (Charizard), mas o nome esperado nao casa -> None.
    patch_fetch(monkeypatch)
    assert tcg_reference.get_tcg_reference(card(name="Venusaur")) is None


def test_subtype_preference_normal_first():
    price, sub = tcg_reference.pick_market_price([
        {"subTypeName": "Reverse Holofoil", "marketPrice": 9.0},
        {"subTypeName": "Normal", "marketPrice": 5.0},
        {"subTypeName": "Holofoil", "marketPrice": 7.0},
    ])
    assert (price, sub) == (5.0, "Normal")
    # Sem Normal: Holofoil vem antes de Reverse.
    price, sub = tcg_reference.pick_market_price([
        {"subTypeName": "Reverse Holofoil", "marketPrice": 9.0},
        {"subTypeName": "Holofoil", "marketPrice": 7.0},
    ])
    assert (price, sub) == (7.0, "Holofoil")


def test_number_embedded_in_product_name(monkeypatch):
    # Produto sem extendedData: numero extraido do nome ("Charizard - 4/102").
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 300, "name": "Charizard - 4/102",
         "url": "https://www.tcgplayer.com/product/300"},
    ]}, prices={"results": [
        {"productId": 300, "subTypeName": "Holofoil", "marketPrice": 400.0},
    ]})
    ref = tcg_reference.get_tcg_reference(card())
    assert ref is not None and ref.market_usd == 400.0


def test_fetch_failure_returns_none(monkeypatch):
    monkeypatch.setattr(tcg_reference, "_fetch_json", lambda url, cache_dir=None: None)
    assert tcg_reference.get_tcg_reference(card()) is None


def test_leading_zeros_in_numbers(monkeypatch):
    # extNumber "004/102" casa watchlist number "4".
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 400, "name": "Charizard",
         "url": "https://www.tcgplayer.com/product/400",
         "extendedData": [{"name": "Number", "value": "004/102"}]},
    ]}, prices={"results": [
        {"productId": 400, "subTypeName": "Holofoil", "marketPrice": 401.0},
    ]})
    ref = tcg_reference.get_tcg_reference(card(number="4"))
    assert ref is not None and ref.market_usd == 401.0


def test_non_numeric_collector_number_skipped(monkeypatch):
    # Watchlist numerica ("4") nao casa produto TG04/TG30 (sem chute).
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 500, "name": "Charizard",
         "url": "https://www.tcgplayer.com/product/500",
         "extendedData": [{"name": "Number", "value": "TG04/TG30"}]},
    ]})
    assert tcg_reference.get_tcg_reference(card(number="4")) is None


def test_non_numeric_watchlist_number_matches_exact(monkeypatch):
    # Watchlist "TG04" casa o produto TG04/TG30 (match exato case-insensitive
    # do texto cru, inclusive contra a parte antes do '/').
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 600, "name": "Charizard",
         "url": "https://www.tcgplayer.com/product/600",
         "extendedData": [{"name": "Number", "value": "TG04/TG30"}]},
    ]}, prices={"results": [
        {"productId": 600, "subTypeName": "Holofoil", "marketPrice": 55.0},
    ]})
    ref = tcg_reference.get_tcg_reference(card(number="TG04"))
    assert ref is not None and ref.market_usd == 55.0
    ref2 = tcg_reference.get_tcg_reference(card(number="tg04"))
    assert ref2 is not None  # case-insensitive


def test_non_numeric_number_never_degrades_to_name_only(monkeypatch):
    # MAJOR do review PR #18: watchlist "Charizard TG04" num set cujo unico
    # Charizard e o base 4/102 NAO pode devolver o base como referencia.
    # A restricao de numero nunca e dropada: sem match exato -> None.
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 100, "name": "Charizard",
         "url": "https://www.tcgplayer.com/product/100",
         "extendedData": [{"name": "Number", "value": "4/102"}]},
    ]}, prices={"results": [
        {"productId": 100, "subTypeName": "Holofoil", "marketPrice": 412.5},
    ]})
    assert tcg_reference.get_tcg_reference(card(number="TG04")) is None


def test_ambiguous_confirmed_match_returns_none(monkeypatch):
    # MINOR do review PR #18: 2 produtos com o mesmo numerador e nomes
    # compativeis = ambiguo -> None (perder deal > inventar deal).
    patch_fetch(monkeypatch, products={"results": [
        {"productId": 700, "name": "Charizard (Cosmos Holo)",
         "url": "https://www.tcgplayer.com/product/700",
         "extendedData": [{"name": "Number", "value": "4/102"}]},
        {"productId": 701, "name": "Charizard (Shadowless)",
         "url": "https://www.tcgplayer.com/product/701",
         "extendedData": [{"name": "Number", "value": "4/102"}]},
    ]}, prices={"results": [
        {"productId": 700, "subTypeName": "Holofoil", "marketPrice": 300.0},
        {"productId": 701, "subTypeName": "Holofoil", "marketPrice": 900.0},
    ]})
    assert tcg_reference.get_tcg_reference(card(number="4")) is None


def test_non_english_card_gets_no_tcg_reference(monkeypatch):
    # MAJOR do review PR #18: a categoria 3 do tcgcsv e o catalogo INGLES do
    # TCGplayer -- carta JP casaria com o produto EN homonimo e a margem
    # sairia do produto errado rotulada como "TCG real". JP => None (cai no
    # fallback PriceCharting ROTULADO), sem sequer tocar a rede/fixtures.
    def explode(url, cache_dir=None):
        raise AssertionError(f"carta nao-EN nao pode consultar o tcgcsv: {url}")
    monkeypatch.setattr(tcg_reference, "_fetch_json", explode)
    assert tcg_reference.get_tcg_reference(card(language="JP")) is None
    assert tcg_reference.get_tcg_reference(card(language="jp")) is None
    # EN continua passando pelo caminho normal (fixtures reais).
    patch_fetch(monkeypatch)
    assert tcg_reference.get_tcg_reference(card(language="EN")) is not None
