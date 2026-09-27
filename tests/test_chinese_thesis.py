"""Consolidação dos JSONs do modo chinês + análise da tese (offline, sem rede)."""
import json

import chinese_thesis as ct
from src import chinese_scan as cs

ZH_151 = "https://www.pricecharting.com/game/pokemon-chinese-151-collect/mew-ex-191"
ZH_OUTRO = "https://www.pricecharting.com/game/pokemon-chinese-xyz-nao-mapeado/mew-ex-12"


def _row(i, price, *, zh_url=ZH_151, n_sales=30, exclusive=False, language="ZH-HANS"):
    return {"card": "Mew ex", "number": "232", "set": "SV: Scarlet & Violet 151", "pokemon": "Mew", "base_name": "mew",
            "rarity": "Special Illustration Rare", "exclusive": exclusive, "exclusive_marker": "promo" if exclusive else None,
            "match": "nome", "rarity_check": True, "language": language, "ratio": None if exclusive else 3000 / price,
            "zh_number": "191", "zh_set_hint": "151-collect",
            "en_ref": None if exclusive else {"price": 3000.0, "source": "vendas", "n": 9,
                                              "url": "https://www.pricecharting.com/game/x/mew-ex-232"},
            "listing": {"price": price, "title": "Mew ex 191/151 SAR Chinese PSA 10",
                        "url": f"https://www.ebay.com/itm/{i}?_skw=x", "country": "CN", "item_id": str(i)},
            "zh": {"status": "ok", "n_sales_90d": n_sales, "months_90d": 3, "median_90d": 396.5,
                   "sales_per_month_observed": n_sales / 3, "url": zh_url, "pop_psa10": None, "pop_total": None},
            "bucket": "validar", "reasons": ["velho"]}


def _payload(group, rows, scheduled, completed, funnel):
    return {"meta": {"kind": cs.KIND, "policy_version": cs.POLICY_VERSION, "timestamp": f"2026-09-26T0{group}:00:00Z",
                     "group": str(group), "watchlist_count": scheduled, "scheduled": scheduled, "params": dict(cs.DEFAULT_PARAMS),
                     "funnel": funnel, "aborted": False, "outlook_available": True,
                     "selection": {"cards_completed": completed, "cards_deferred": scheduled - completed}},
            "rows": rows}


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "character_points", lambda name: 25)
    a = _payload(1, [_row(1, 400.0), _row(2, 500.0, zh_url=ZH_OUTRO), _row(3, 600.0, n_sales=1)],
                 scheduled=10, completed=10, funnel={"ebay_calls": 10, "pages": 3})
    b = _payload(2, [_row(4, 2000.0), _row(5, 50.0, exclusive=True), _row(6, 450.0, language="ZH")],
                 scheduled=8, completed=5, funnel={"ebay_calls": 5})
    pa, pb = tmp_path / "chinese-g1.json", tmp_path / "chinese-g2.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")
    return pa, pb


def test_merge_consolidates_meta_and_rescores_rows(tmp_path, monkeypatch):
    pa, pb = _fixture(tmp_path, monkeypatch)
    merged = ct.merge(ct.load_payloads([str(tmp_path / "chinese-g*.json")]))
    m = merged["meta"]
    assert m["kind"] == cs.KIND and m["group"] == "1, 2" and "consolidado de 2 runs" in m["timestamp"]
    assert m["scheduled"] == 18 and m["selection"] == {"cards_completed": 15, "cards_deferred": 3}
    assert m["funnel"] == {"ebay_calls": 15, "pages": 3}
    assert m["sources"] == [str(pa), str(pb)]
    by_item = {r["listing"]["item_id"]: r for r in merged["rows"]}
    assert by_item["1"]["bucket"] == "candidata" and by_item["1"]["reasons"] == []      # nome + set correspondente + evidência
    assert "set-zh-sem-correspondencia" in by_item["2"]["reasons"]                       # página chinesa fora do mapa curado
    assert any(x.startswith("evidencia-zh-insuficiente") for x in by_item["3"]["reasons"])
    assert by_item["4"]["bucket"] == "abaixo-do-corte"                                   # razão 1.5 < 4
    assert by_item["5"]["bucket"] == "exclusiva"
    assert "idioma-nao-especificado" in by_item["6"]["reasons"]
    assert all(r["_group"] in {"1", "2"} for r in merged["rows"])


def test_ratio_funnel_explains_why_ratio_alone_is_not_a_candidate(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    merged = ct.merge(ct.load_payloads([str(tmp_path / "chinese-g*.json")]))
    steps = dict((label, (n_in, n_out)) for label, n_in, n_out in ct.ratio_funnel(merged["rows"], "ZH-HANS", 4.0))
    # 3 anúncios simplificados passam o crivo (itens 1, 2, 3); o de razão 1.5 e o exclusivo não entram
    assert steps["identidade: nome sem número EN e set chinês sem correspondência curada"] == (3, 1)
    assert steps["menos vendas PSA 10 em chinês que o mínimo (90 d)"] == (2, 1)
    assert steps["candidatas"] == (1, 0)
    zh = dict((label, (n_in, n_out)) for label, n_in, n_out in ct.ratio_funnel(merged["rows"], "ZH", 4.0))
    assert zh["idioma não especificado no título"] == (1, 1) and zh["candidatas"] == (0, 0)


def test_thesis_markdown_has_aggregates_no_purchase_advice_and_cli_writes_files(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    out_md, out_json = tmp_path / "tese.md", tmp_path / "all.json"
    assert ct.main([str(tmp_path / "chinese-g*.json"), "-o", str(out_md), "--merge-out", str(out_json)]) == 0
    md = out_md.read_text(encoding="utf-8")
    # 4 pares simplificados com referência EN por vendas (3 acima do crivo + 1 abaixo); 1 candidata
    assert "| simplificado | 4 |" in md and "## Funil do crivo" in md and "| candidatas | 1 | — |" in md
    # menor anúncio da página chinesa mais líquida = o exclusivo (item 5); URL sem rastreio
    assert "Páginas chinesas mais líquidas" in md and "itm/5)" in md and "_skw" not in md
    assert "Nenhuma recomendação de compra" in md and "COMPRAR" not in md
    assert "None" not in md and "nan" not in md
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["meta"]["kind"] == cs.KIND and len(payload["rows"]) == 6
    # o consolidado é consumível pelo gerador de entrega
    import ebay_summary
    chat = ebay_summary.build_markdown(payload, compact=True)
    assert "🟢 Candidatas" in chat and "itm/1)" in chat


def test_rejects_json_of_another_kind(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"meta": {"kind": "slab"}, "rows": []}), encoding="utf-8")
    try:
        ct.load_payloads([str(p)])
    except SystemExit as e:
        assert "meta.kind" in str(e)
    else:
        raise AssertionError("JSON de outro modo aceito")
