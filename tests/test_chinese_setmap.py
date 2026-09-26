"""Correspondência de set entre a página chinesa e o set EN (modo chinês)."""
from src import chinese_scan as cs


def test_zh_set_code_and_correspondence():
    assert cs.zh_set_code("https://www.pricecharting.com/game/pokemon-chinese-sv4af/charizard-ex-125") == "sv4a"
    assert cs.zh_set_code("https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191") == "151-collect"
    assert cs.zh_set_code("https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-155") == "csv5c"
    assert cs.zh_set_code("") is None
    assert cs.set_corresponds("SV: Scarlet & Violet 151", "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191") is True
    assert cs.set_corresponds("SV: Prismatic Evolutions", "https://www.pricecharting.com/game/pokemon-chinese-sv8a/umbreon-ex-217") is True
    assert cs.set_corresponds("SV03: Obsidian Flames", "https://www.pricecharting.com/game/pokemon-chinese-sv8a/umbreon-ex-217") is False
    assert cs.set_corresponds("SV: Scarlet & Violet 151", "https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-155") is None
    assert cs.set_corresponds("SV: Scarlet & Violet 151", "https://www.pricecharting.com/game/pokemon-chinese-promo/mew-ex-3sv-p") is None


def _row(**kw):
    base = {"exclusive": False, "match": "nome", "rarity_check": True, "language": "ZH-HANS", "ratio": 5.0,
            "set": "SV: Scarlet & Violet 151", "en_ref": {"price": 500.0, "source": "vendas", "n": 4},
            "zh": {"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191"}}
    base.update(kw)
    return base


def test_candidate_without_number_needs_same_set():
    p = cs.DEFAULT_PARAMS
    assert cs.classify(_row(), p) == ("candidata", [])
    b, why = cs.classify(_row(zh={"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-csv5c/charizard-ex-155"}), p)
    assert b == "validar" and why == ["set-zh-sem-correspondencia"]
    b, why = cs.classify(_row(zh={"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-sv8a/umbreon-ex-217"}), p)
    assert b == "validar" and why == ["set-zh-divergente"]
    # com número igual a correspondência de set não é exigida
    assert cs.classify(_row(match="nome+numero", zh={"status": "ok", "n_sales_90d": 3, "url": "https://www.pricecharting.com/game/pokemon-chinese-csv5c/x-1"}), p) == ("candidata", [])


def test_tag_team_and_hyphen_suffix_are_other_cards():
    from src.models import WatchCard
    c = WatchCard("Charizard", "Base Set", "4", "EN", "u", pokemon="Charizard", rarity="Rare Holo")
    assert cs.match_level(c, "Pokemon TCG S-Chinese Charizard and Braixen GX CSM2.5C 065/061 PSA10") is None
    assert cs.match_level(c, "PSA 10 Pokemon S-Chinese CSM2cC-183 UR Reshiram & Charizard-GX Holo") is None
    assert cs.match_level(c, "Pokemon Chinese Charizard-GX PSA 10") is None
    assert cs.match_level(c, "1999 Pokemon Chinese Base Set Charizard 4/102 Holo PSA 10") == "nome+numero"
    assert cs.match_level(c, "Pokemon PSA 10 GEM MT Charizard Holo 2024 001/012 CSMC S.Chinese") == "nome"
    r = WatchCard("Reshiram & Charizard GX", "SM - Unbroken Bonds", "20", "EN", "u", pokemon="Charizard", rarity="Ultra Rare")
    assert cs.match_level(r, "PSA 10 Pokemon S-Chinese Sun&Moon Reshiram & Charizard GX 20/214 Chinese") == "nome+numero"


def test_rescore_reapplies_identity_and_counts_dropped():
    row = {"card": "Charizard", "set": "Base Set", "number": "4", "pokemon": "Charizard", "rarity": "Rare Holo", "exclusive": False,
           "match": "nome", "rarity_check": None, "language": "ZH-HANS", "ratio": 100.0, "en_ref": {"price": 20000.0, "source": "vendas", "n": 5},
           "listing": {"price": 200.0, "title": "Pokemon TCG S-Chinese Charizard and Braixen GX CSM2.5C 065/061 PSA10"}, "zh": None, "lt": {}}
    out = cs.rescore({"meta": {"params": {}}, "rows": [row]})
    assert out["rows"] == [] and out["meta"]["funnel"]["rescore_outra_carta"] == 1
