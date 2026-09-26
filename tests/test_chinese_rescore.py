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
           "listing": {"price": 100.0, "title": "Charizard ex 199/165 Simplified Chinese PSA 10"},
           "zh": {"status": "ok", "n_sales_90d": 3, "median_90d": 150.0, "pop_psa10": 1, "pop_total": 2,
                  "sales_per_month_observed": 1.0},
           "lt": {"score": 999}, "bucket": "validar", "reasons": ["velho"]}
    out = cs.rescore({"meta": {"params": {}}, "rows": [row]})
    r = out["rows"][0]
    assert r["match"] == "nome+numero"   # identidade recalculada do título
    assert r["bucket"] == "candidata" and r["reasons"] == [] and r["zh_margin_pct"] == 50.0
    assert r["lt"]["scarcity"] is None and r["lt"]["coverage"] == "3/4" and r["lt"]["score"] == 25 + 25 + 3
    assert cs.rescore(out)["rows"][0]["lt"] == r["lt"]


def test_compact_groups_large_buckets_but_keeps_candidates(monkeypatch):
    from src import chinese_report
    import ebay_summary
    monkeypatch.setattr(cs, "character_points", lambda name: 25)

    def row(i, bucket, price, exclusive=False):
        return {"card": "Mew ex", "number": "232", "set": "SV: Scarlet & Violet 151", "pokemon": "Mew", "base_name": "mew",
                "rarity": "Special Illustration Rare", "exclusive": exclusive, "exclusive_marker": "promo" if exclusive else None,
                "match": "nome", "rarity_check": True, "language": "ZH-HANS", "ratio": None if exclusive else 3000 / price,
                "zh_number": "191", "zh_set_hint": "151-collect",
                "en_ref": None if exclusive else {"price": 3000.0, "source": "vendas", "n": 9, "url": "https://www.pricecharting.com/game/x/mew-ex-232"},
                "listing": {"price": price, "title": "Mew ex 191/151 SAR Chinese PSA 10", "url": f"https://www.ebay.com/itm/{i}", "country": "CN", "item_id": str(i)},
                "zh": {"status": "ok", "n_sales_90d": 30, "months_90d": 3, "median_90d": 396.5, "sales_per_month_observed": 10.0,
                       "url": "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191", "pop_psa10": None, "pop_total": None}}

    rows = [row(i, "candidata", 400.0 + i) for i in range(45)] + [row(100 + i, "exclusiva", 50.0 + i, exclusive=True) for i in range(45)]
    payload = {"meta": {"kind": "chinese-psa10", "params": {}, "funnel": {}, "group": "2"}, "rows": rows}
    full = ebay_summary.build_markdown(payload)
    chat = ebay_summary.build_markdown(payload, compact=True)
    # candidatas (45, todas nome + set correspondente + evidência) saem inteiras nas duas versões
    assert full.count("[oferta](https://www.ebay.com/itm/") == 90 and chat.count("| 45 |") >= 1
    assert "🟢 Candidatas" in chat and chat.count("itm/0)") == 1 and chat.count("itm/44)") == 1
    # exclusivas agrupadas no chat (1 grupo de 45), inteiras no completo
    assert "agrupados por carta chinesa" in chat and "| Mew 191 · 151-collect | simplificado | 45 |" in chat
    assert "| 45 | Mew ex" not in full and full.count("itm/144)") == 1
    assert "None" not in chat and "nan" not in chat
