"""build_watchlist.py: universo (chases x raridade x teto), entradas e relatorio -- offline."""
import yaml

import build_watchlist as bw
from src import pc_sales

RANK = {"charizard": 1, "mew": 20, "mewtwo": 6}
RX = bw.iconic_regex(RANK)


def P(pid, name, number, rarity):
    return {"productId": pid, "name": name, "url": f"https://www.tcgplayer.com/product/{pid}",
            "extendedData": [{"name": "Number", "value": number}, {"name": "Rarity", "value": rarity}]}


def PR(pid, market):
    return {"productId": pid, "subTypeName": "Holofoil", "marketPrice": market}


PRODUCTS = [
    P(1, "Charizard ex - 199/165", "199/165", "Special Illustration Rare"),
    P(2, "Mew ex - 151/165", "151/165", "Double Rare"),
    P(3, "Mewtwo - 150/165", "150/165", "Rare"),               # raridade fora
    P(4, "Mewtwo ex - 201/165", "201/165", "Ultra Rare"),
    P(5, "Pikachu - 025/165", "025/165", "Holo Rare"),         # nao e chase
    P(6, "Charizard - 006/165", "006/165", "Holo Rare"),
    P(7, "Charizard ex - 234/165", "", "Hyper Rare"),          # sem numero
]
PRICES = [PR(1, 300.0), PR(2, 20.0), PR(4, 45.0), PR(6, 12.5)]


def test_match_pokemon_word_boundary_prefers_longest():
    assert bw.match_pokemon("Mewtwo ex - 201/165", RX, RANK) == ("Mewtwo", 6)
    assert bw.match_pokemon("Mew ex", RX, RANK) == ("Mew", 20)
    assert bw.match_pokemon("Pikachu", RX, RANK) is None


def test_numerator_and_query_set_name():
    assert bw.numerator("004/102") == "4" and bw.numerator("199/165") == "199"
    assert bw.numerator("TG04/TG30") == "TG04" and bw.numerator("") == ""
    assert bw.query_set_name("SV10: Destined Rivals") == "Destined Rivals"
    assert bw.query_set_name("SWSH07: Evolving Skies") == "Evolving Skies"
    assert bw.query_set_name("Base Set") == "Base Set"
    assert bw.query_set_name("EX Emerald (em)") == "EX Emerald"


def test_select_candidates_filters_and_caps_by_market():
    rows = bw.select_candidates("SV: Scarlet & Violet 151", PRODUCTS, PRICES, RANK, RX, cap=3)
    assert [r["name"] for r in rows] == ["Charizard ex", "Mewtwo ex", "Mew ex"]
    assert rows[0]["number"] == "199" and rows[0]["number_raw"] == "199/165"
    assert rows[0]["market"] == 300.0 and rows[0]["pokemon_rank"] == 1
    everything = bw.select_candidates("S", PRODUCTS, PRICES, RANK, RX, cap=0)
    assert [r["name"] for r in everything] == ["Charizard ex", "Mewtwo ex", "Mew ex", "Charizard"]


def test_to_entry_fields():
    cand = bw.select_candidates("SV10: Destined Rivals", PRODUCTS, PRICES, RANK, RX)[0]
    e = bw.to_entry(cand, 1, "2025", "https://www.pricecharting.com/game/x/charizard-ex-199")
    assert e == {"name": "Charizard ex", "set": "SV10: Destined Rivals", "number": "199",
                 "language": "EN", "pc_url": "https://www.pricecharting.com/game/x/charizard-ex-199",
                 "tcg_set": "SV10: Destined Rivals",
                 "ebay_query": "pokemon Charizard ex 199 Destined Rivals", "group": "1",
                 "pokemon": "Charizard", "pokemon_rank": 1,
                 "rarity": "Special Illustration Rare", "year": 2025}


def _fake_fetch(url, cache_dir=None):
    if url.endswith("/groups"):
        return {"results": [{"groupId": 10, "name": "Base Set"}, {"groupId": 11, "name": "Jungle"}]}
    if url.endswith("/10/products"):
        return {"results": PRODUCTS}
    if url.endswith("/10/prices"):
        return {"results": PRICES}
    return {"results": []}


def test_build_excludes_cards_without_pc_page_and_reports(monkeypatch):
    calls = []

    def resolve(name, number, set_name, cache_dir=None):
        calls.append((name, number, set_name))
        if name.startswith("Mew ex"):
            return None
        if name.startswith("Mewtwo"):
            raise pc_sales.PcError("bloqueio")
        return f"https://www.pricecharting.com/game/pokemon-base-set/{number}"

    monkeypatch.setattr(bw, "load_iconic", lambda path=None: dict(RANK))
    monkeypatch.setattr(bw.groups, "SCAN_GROUPS", {3: bw.groups.GroupDef(
        number=3, title="t", description="d", era="vintage", sets=("Base Set", "Fossil"))})
    entries, report = bw.build([3], fetch_json=_fake_fetch, resolve_pc=resolve, cap=30,
                               log=lambda *a: None)
    assert [e["name"] for e in entries] == ["Charizard ex", "Charizard"]
    assert entries[0]["group"] == "3" and entries[0]["year"] == 1999
    assert entries[0]["pc_url"].endswith("/199/165")
    assert report["no_pc"] == [("Base Set", "Mew ex", "151")]
    assert report["pc_error"][0][:3] == ("Base Set", "Mewtwo ex", "201")
    assert report["missing_tcg_group"] == ["Fossil"]
    assert report["per_group"][3] == 2
    assert calls[0] == ("Charizard ex - 199/165", "199/165", "Base Set")  # nome/numero crus p/ o matcher
    text = bw.report_text(report, entries)
    assert "Watchlist: 2 cartas" in text and "sem PC: Base Set | Mew ex 151" in text


def test_render_yaml_roundtrips_into_load_watchlist(tmp_path):
    from src import scanner
    e = {"name": "Charizard", "set": "Base Set", "number": "4", "language": "EN",
         "pc_url": "https://www.pricecharting.com/game/pokemon-base-set/charizard-4",
         "tcg_set": "Base Set", "ebay_query": "pokemon Charizard 4 Base Set", "group": "3",
         "pokemon": "Charizard", "pokemon_rank": 1, "rarity": "Holo Rare", "year": 1999}
    out = tmp_path / "w.yaml"
    out.write_text(bw.render_yaml([e], note="teste"), encoding="utf-8")
    assert out.read_text(encoding="utf-8").startswith("# watchlist.yaml -- GERADA")
    cards = scanner.load_watchlist(str(out))
    assert cards[0].group == "3" and cards[0].pokemon_rank == 1 and cards[0].year == 1999
    assert cards[0].default_query() == "pokemon Charizard 4 Base Set"
    assert yaml.safe_load(out.read_text(encoding="utf-8"))["cards"][0]["number"] == "4"


def test_rarity_allow_covers_measured_catalog_rarities():
    for r in ("Holo Rare", "Ultra Rare", "Secret Rare", "Shiny Holo Rare", "Illustration Rare",
              "Special Illustration Rare", "Double Rare", "Hyper Rare", "Rainbow Rare",
              "Amazing Rare", "Radiant Rare", "Classic Collection", "Rare BREAK", "Prism Rare"):
        assert r.lower() in bw.RARITY_ALLOW, r
    for r in ("Common", "Uncommon", "Rare", "Code Card", ""):
        assert r.lower() not in bw.RARITY_ALLOW, r


# --- 5a geracao (2026-09-04): duplicata de produto e ano vazio no catalogo ------------

def test_select_candidates_dedups_same_card_keeping_priciest():
    # tcgcsv real: 3 pares com MESMO nome+numero e productId diferente (Mew ex 205
    # Hyper/Double Rare, Charizard Base Set 4, Celebi Triumphant 3). Sem dedupe viram
    # 2 chamadas ao eBay pela MESMA pagina e 2 linhas iguais na entrega.
    prods = [P(10, "Mew ex - 205/165", "205/165", "Hyper Rare"),
             P(11, "Mew ex - 205/165", "205/165", "Double Rare"),
             P(12, "Charizard - 004/102", "004/102", "Holo Rare")]
    prices = [PR(10, 90.0), PR(11, 120.0), PR(12, 300.0)]
    rows = bw.select_candidates("S", prods, prices, RANK, RX, cap=0)
    assert [(r["name"], r["number"], r["market"]) for r in rows] == [
        ("Charizard", "4", 300.0), ("Mew ex", "205", 120.0)]  # fica a mais cara


def test_build_fills_year_from_tcgcsv_when_catalog_has_none(monkeypatch):
    # Os 13 sets SV vieram do catalogo com year "" -> 182 cartas com year nulo.
    # O tcgcsv traz `publishedOn`: fonte real, nada inventado.
    def fetch(url, cache_dir=None):
        if url.endswith("/groups"):
            return {"results": [{"groupId": 10, "name": "Base Set", "publishedOn": "1999-01-09T00:00:00"},
                                {"groupId": 11, "name": "SV10: Destined Rivals", "publishedOn": "2025-05-30T00:00:00"}]}
        if url.endswith("/products"):
            return {"results": [P(1, "Charizard ex - 199/165", "199/165", "Special Illustration Rare")]}
        if url.endswith("/prices"):
            return {"results": [PR(1, 300.0)]}
        return {"results": []}
    monkeypatch.setattr(bw, "load_iconic", lambda path=None: dict(RANK))
    monkeypatch.setattr(bw.groups, "SCAN_GROUPS", {1: bw.groups.GroupDef(
        number=1, title="t", description="d", era="recent", sets=("SV10: Destined Rivals",))})
    monkeypatch.setattr(bw.groups, "catalog", lambda: {"SV10: Destined Rivals": {"year": ""}})
    entries, _ = bw.build([1], fetch_json=fetch, resolve_pc=lambda *a, **k: "https://x/y",
                          log=lambda *a: None)
    assert entries[0]["year"] == 2025


def test_build_reports_collision_when_two_cards_share_a_pc_page(monkeypatch):
    # Guarda contra o pior caso: duas cartas DIFERENTES resolvendo para a MESMA pagina
    # do PriceCharting = referencia de preco de outra carta. Hoje nao acontece (as
    # 1.669 da watchlist passaram limpas), mas uma regeracao futura com catalogo maior
    # pode criar o caso -- e ele nao pode passar em silencio.
    prods = [P(1, "Charizard ex - 199/165", "199/165", "Special Illustration Rare"),
             P(2, "Mew ex - 151/165", "151/165", "Double Rare")]
    prices = [PR(1, 300.0), PR(2, 20.0)]

    def fetch(url, cache_dir=None):
        if url.endswith("/groups"):
            return {"results": [{"groupId": 10, "name": "Base Set", "publishedOn": "1999-01-09"}]}
        if url.endswith("/products"):
            return {"results": prods}
        if url.endswith("/prices"):
            return {"results": prices}
        return {"results": []}
    monkeypatch.setattr(bw, "load_iconic", lambda path=None: dict(RANK))
    monkeypatch.setattr(bw.groups, "SCAN_GROUPS", {3: bw.groups.GroupDef(
        number=3, title="t", description="d", era="vintage", sets=("Base Set",))})
    monkeypatch.setattr(bw.groups, "catalog", lambda: {"Base Set": {"year": "1999"}})
    entries, report = bw.build([3], fetch_json=fetch,
                               resolve_pc=lambda *a, **k: "https://www.pricecharting.com/game/x/mesma-4",
                               log=lambda *a: None)
    assert len(report["pc_collision"]) == 1
    url, cards = report["pc_collision"][0]
    assert url.endswith("/mesma-4") and sorted(c[1] for c in cards) == ["Charizard ex", "Mew ex"]
    assert "COLISAO" in bw.report_text(report, entries)


def test_build_REMOVE_da_watchlist_as_cartas_em_colisao(monkeypatch):
    # Regressao 2026-09-04: a "guarda dura" so REPORTAVA a colisao; as duas cartas
    # continuavam na watchlist com o mesmo pc_url, e o scan usaria o preco de uma como
    # referencia da outra. Reportar nao basta -- tem de sair do artefato.
    prods = [P(1, "Charizard ex - 199/165", "199/165", "Special Illustration Rare"),
             P(2, "Mew ex - 151/165", "151/165", "Double Rare")]
    prices = [PR(1, 300.0), PR(2, 20.0)]

    def fetch(url, cache_dir=None):
        if url.endswith("/groups"):
            return {"results": [{"groupId": 10, "name": "Base Set", "publishedOn": "1999-01-09"}]}
        if url.endswith("/products"):
            return {"results": prods}
        if url.endswith("/prices"):
            return {"results": prices}
        return {"results": []}
    monkeypatch.setattr(bw, "load_iconic", lambda path=None: dict(RANK))
    monkeypatch.setattr(bw.groups, "SCAN_GROUPS", {3: bw.groups.GroupDef(
        number=3, title="t", description="d", era="vintage", sets=("Base Set",))})
    monkeypatch.setattr(bw.groups, "catalog", lambda: {"Base Set": {"year": "1999"}})
    entries, report = bw.build([3], fetch_json=fetch,
                               resolve_pc=lambda *a, **k: "https://www.pricecharting.com/game/x/mesma-4",
                               log=lambda *a: None)
    assert len(report["pc_collision"]) == 1
    # nenhuma das duas sobrevive: nao da para saber qual das duas e a dona da pagina
    assert entries == []


def test_main_erra_alto_quando_ha_colisao(monkeypatch, tmp_path):
    # Sair com 0 fazia a colisao passar despercebida em CI e em run nao-interativo.
    out = tmp_path / "w.yaml"
    monkeypatch.setattr(bw, "build", lambda *a, **k: (
        [], {"total": 0, "candidates": 0, "per_group": {}, "no_pc": [], "pc_error": [],
             "missing_tcg_group": [], "capped_sets": [],
             "pc_collision": [("https://x/mesma-4", [("S", "A", "1"), ("S", "B", "2")])]}))
    assert bw.main(["--groups", "3", "--out", str(out)]) == 1
    assert out.exists()  # o artefato limpo continua sendo gravado
