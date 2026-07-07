"""Testes da entrega canonica (ebay_summary.py) sobre um JSON sintetico."""
import json

import ebay_summary
from src import report


def row(**kw):
    base = {
        "card": "Charizard", "set": "Base Set", "number": "4",
        "language": "EN", "group": "", "grade": "PSA 9",
        "price": 2200.0, "shipping": 4.5, "fair_value": 3175.04,
        "ref_kind": "pricecharting",
        "ref_url": "https://www.pricecharting.com/game/pokemon-base-set/charizard-4",
        "tcg_market": None, "tcg_url": "",
        "margin_pct": 44.3, "ebay_median": 0.0,
        "liquidity_per_month": 30.0, "tier": "A", "trend": 39.13,
        "score": 80.0, "trust_score": 85.0,
        "seller_feedback": 1200, "seller_feedback_pct": 99.8,
        "protections": ["AG"], "verdict": "OPORTUNIDADE", "flags": [],
        "url": "https://www.ebay.com/itm/111", "item_id": "111",
        "title": "Charizard 4/102 PSA 9",
    }
    base.update(kw)
    return base


def payload():
    rows = [
        row(),  # OPORTUNIDADE graded (pricecharting)
        row(card="Umbreon VMAX", number="215", grade="RAW", price=300.0,
            fair_value=450.0, ref_kind="tcgplayer", tcg_market=450.0,
            tcg_url="https://www.tcgplayer.com/product/999",
            ref_url="https://www.tcgplayer.com/product/999",
            margin_pct=50.0, score=70.0, verdict="REVISAR",
            flags=["LEILAO: preco atual pode subir | ate o fim"],
            url="https://www.ebay.com/itm/222", item_id="222"),
        row(card="Pikachu", number="25", grade="RAW", price=50.0,
            fair_value=120.0, ref_kind="pricecharting", margin_pct=140.0,
            score=55.0, verdict="SUSPEITO",
            flags=["MARGEM: 140% acima do normal"],
            url="https://www.ebay.com/itm/333", item_id="333"),
        row(card="Blastoise", number="2", grade="FORA DO ESCOPO", price=500.0,
            score=0.0, verdict="REJEITADO",
            flags=["GRADE: empresa/nota fora do escopo"],
            url="https://www.ebay.com/itm/444", item_id="444"),
    ]
    return {"meta": {"timestamp": "2026-07-06T12:00:00+00:00",
                     "watchlist_count": 4, "group": "chase-en",
                     "include_raw": True, "trusted_mode": False,
                     "config": {}},
            "rows": rows}


def test_all_four_sections_always_present():
    md = ebay_summary.build_markdown(payload())
    for title in ("## 🟢 OPORTUNIDADE", "## ⚠️ REVISAR (validar manualmente)",
                  "## 🚨 SUSPEITO (margem alta demais — validar)",
                  "## ⛔ REJEITADO"):
        assert title in md


def test_empty_bucket_renders_placeholder_not_dropped():
    p = payload()
    p["rows"] = [row()]  # so OPORTUNIDADE
    md = ebay_summary.build_markdown(p)
    assert "## ⛔ REJEITADO" in md
    assert "_Nenhuma linha neste bucket._" in md


def test_all_rows_present_including_rejected():
    md = ebay_summary.build_markdown(payload())
    assert "Charizard 4" in md
    assert "Umbreon VMAX 215" in md
    assert "Pikachu 25" in md
    assert "Blastoise 2" in md
    assert "GRADE: empresa/nota fora do escopo" in md  # motivo do rejeitado


def test_links_format_both_kinds():
    md = ebay_summary.build_markdown(payload())
    # ref_kind=tcgplayer -> [oferta] · [TCG]
    assert ("[oferta](https://www.ebay.com/itm/222) · "
            "[TCG](https://www.tcgplayer.com/product/999)") in md
    # ref_kind=pricecharting -> [oferta] · [ref]
    assert ("[oferta](https://www.ebay.com/itm/111) · "
            "[ref](https://www.pricecharting.com/game/pokemon-base-set/"
            "charizard-4)") in md


def test_missing_url_shows_only_existing_link():
    p = payload()
    p["rows"] = [row(ref_url="", verdict="OPORTUNIDADE")]
    md = ebay_summary.build_markdown(p)
    assert "[oferta](https://www.ebay.com/itm/111)" in md
    assert "[ref](" not in md
    assert "· \n" not in md  # sem separador orfao


def test_flagged_sections_have_separate_flags_column():
    md = ebay_summary.build_markdown(payload())
    # Regressao real do smoke: [:-1] gerava "| Links Flags |" (coluna fundida).
    assert "| Links | Flags |" in md
    assert "Links Flags" not in md


def test_pipe_escaped_in_cells():
    md = ebay_summary.build_markdown(payload())
    assert "subir \\| ate o fim" in md


def test_coverage_line():
    md = ebay_summary.build_markdown(payload())
    assert ("Cobertura de referência: 2 graded (PriceCharting) · "
            "1 raw c/ TCGplayer real · 1 raw só PriceCharting") in md


def test_header_meta_and_verdict_counts():
    md = ebay_summary.build_markdown(payload())
    assert "# Scan eBay — 2026-07-06" in md
    assert "Watchlist: 4 carta(s)" in md
    assert "grupo `chase-en`" in md
    assert "1 OPORTUNIDADE" in md and "1 REVISAR" in md
    assert "1 SUSPEITO" in md and "1 REJEITADO" in md


def test_rows_sorted_by_score_desc_within_bucket():
    p = payload()
    p["rows"] = [row(card="Low", score=10.0, item_id="a",
                     url="https://www.ebay.com/itm/a"),
                 row(card="High", score=90.0, item_id="b",
                     url="https://www.ebay.com/itm/b")]
    md = ebay_summary.build_markdown(p)
    assert md.index("High") < md.index("Low")


def test_carta_does_not_duplicate_embedded_number():
    p = payload()
    p["rows"] = [row(card="Charizard 4", number="4")]
    md = ebay_summary.build_markdown(p)
    assert "Charizard 4 4" not in md
    assert "Charizard 4" in md


def test_cli_writes_file_and_prints(tmp_path, capsys):
    scan = tmp_path / "scan.json"
    out = tmp_path / "out.md"
    scan.write_text(json.dumps(payload()), encoding="utf-8")
    ebay_summary.main([str(scan), "-o", str(out)])
    body = out.read_text(encoding="utf-8")
    assert "## 🟢 OPORTUNIDADE" in body
    captured = capsys.readouterr()
    assert "## 🟢 OPORTUNIDADE" in captured.out


def test_report_to_markdown_uses_same_links_helper():
    # Anti-duplicacao: o modo console usa o MESMO links_cell da entrega.
    assert report.links_cell("u", "r", ref_label="TCG",
                             keep_placeholders=False) == "[oferta](u) · [TCG](r)"
    assert report.links_cell("", "", keep_placeholders=True) == "— · —"
    assert report.links_cell("u", "", keep_placeholders=False) == "[oferta](u)"
