"""Censo fino e re-pontuação da entrega (modo chinês)."""
from src import chinese_scan as cs


def test_thin_census_is_not_scarcity(monkeypatch):
    monkeypatch.setattr(cs, "character_points", lambda name: 25)
    thin = cs.longterm("Charizard ex", "Special Illustration Rare",
                       {"pop_psa10": 1, "pop_total": 3, "sales_per_month_observed": 0.0})
    assert thin["scarcity"] is None and thin["coverage"] == "3/4" and "censo fino" in thin["pop_note"]
    ok = cs.longterm("Charizard ex", "Special Illustration Rare",
                     {"pop_psa10": 30, "pop_total": 40, "sales_per_month_observed": 0.0})
    assert ok["scarcity"] == 25 and ok["pop_note"] is None and ok["coverage"] == "4/4"


def test_rescore_is_idempotent_and_uses_current_rule(monkeypatch):
    monkeypatch.setattr(cs, "character_points", lambda name: 25)
    row = {"card": "Charizard ex", "rarity": "Special Illustration Rare", "exclusive": False, "match": "nome+numero",
           "rarity_check": None, "language": "ZH-HANS", "ratio": 5.0,
           "en_ref": {"price": 500.0, "source": "vendas", "n": 4},
           "listing": {"price": 100.0, "title": "x"},
           "zh": {"status": "ok", "n_sales_90d": 3, "median_90d": 150.0, "pop_psa10": 1, "pop_total": 2,
                  "sales_per_month_observed": 1.0},
           "lt": {"score": 999}, "bucket": "validar", "reasons": ["velho"]}
    out = cs.rescore({"meta": {"params": {}}, "rows": [row]})
    r = out["rows"][0]
    assert r["bucket"] == "candidata" and r["reasons"] == [] and r["zh_margin_pct"] == 50.0
    assert r["lt"]["scarcity"] is None and r["lt"]["coverage"] == "3/4" and r["lt"]["score"] == 25 + 25 + 3
    assert cs.rescore(out)["rows"][0]["lt"] == r["lt"]
