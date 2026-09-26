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
