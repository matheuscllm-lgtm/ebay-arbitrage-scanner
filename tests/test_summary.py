"""Testes da entrega canonica (ebay_summary.py, padrao COMC) sobre um JSON sintetico."""
import json

import pytest

import ebay_summary
from src import report


def row(**kw):
    base = {
        "card": "Charizard", "set": "Base Set", "number": "4",
        "language": "EN", "group": "3", "pokemon": "Charizard", "pokemon_rank": 1,
        "grade": "PSA 9", "grade_label": "PSA 9", "condition": "", "listing_type": "PSA 9",
        "price": 2200.0, "shipping": 4.5, "fair_value": 3175.04,
        "discount_pct": 30.71, "roi_pct": 44.32, "spread_usd": 975.04, "margin_pct": 44.32,
        "ref_kind": "pricecharting", "ref_source": "pricecharting-sales",
        "ref_label": "vendas PSA 9 (n=6, 2026-04..2026-08)", "ref_n_sales": 6,
        "ref_liquidity": "ok", "ref_window_days": 180, "ref_column_price": 3100.0,
        "ref_url": "https://www.pricecharting.com/game/pokemon-base-set/charizard-4",
        "pc_url": "https://www.pricecharting.com/game/pokemon-base-set/charizard-4",
        "tcg_market": None, "tcg_url": "",
        "ebay_median": 0.0, "liquidity_per_month": 30.0, "tier": "A", "trend": 39.13,
        "score": 80.0, "trust_score": 85.0,
        "seller_feedback": 1200, "seller_feedback_pct": 99.8,
        "protections": ["AG"], "verdict": "OPORTUNIDADE", "reasons": [], "flags": [],
        "url": "https://www.ebay.com/itm/111", "item_id": "111",
        "title": "Charizard 4/102 PSA 9",
    }
    base.update(kw)
    return base


def payload(**meta_extra):
    rows = [
        row(),  # OPORTUNIDADE slab, 30,71%
        row(card="Umbreon VMAX", number="215", set="Evolving Skies", pokemon="Umbreon",
            pokemon_rank=4, grade="RAW", condition="NM", listing_type="Raw NM",
            price=300.0, fair_value=450.0, discount_pct=33.33, roi_pct=50.0,
            spread_usd=150.0, margin_pct=50.0, ref_kind="tcgplayer",
            ref_source="tcgplayer", ref_label="TCG market", ref_n_sales=None,
            ref_liquidity="", ref_column_price=None, tcg_market=450.0,
            tcg_url="https://www.tcgplayer.com/product/999",
            pc_url="https://www.pricecharting.com/game/pokemon-evolving-skies/umbreon-vmax-215",
            ref_url="https://www.pricecharting.com/game/pokemon-evolving-skies/umbreon-vmax-215",
            verdict="REVISAR", reasons=["ref-desalinhada(1.6x)"],
            flags=["REF DESALINHADA: preco justo e 1.6x a mediana | conferir"],
            url="https://www.ebay.com/itm/222", item_id="222"),
        row(card="Pikachu", number="25", grade="RAW", condition="LP", listing_type="Raw LP",
            price=50.0, fair_value=120.0, discount_pct=58.33, roi_pct=140.0,
            spread_usd=70.0, margin_pct=140.0, ref_source="pricecharting-sales-lp",
            ref_label="vendas LP (n=4, 2026-06..2026-08)", ref_n_sales=4,
            ref_liquidity="low", verdict="SUSPEITO",
            reasons=[], flags=["MARGEM: 140% acima do normal"],
            url="https://www.ebay.com/itm/333", item_id="333"),
        row(card="Blastoise", number="2", grade="PSA 10", listing_type="PSA 10",
            price=500.0, fair_value=700.0, discount_pct=28.57, roi_pct=40.0,
            spread_usd=200.0, margin_pct=40.0, verdict="REJEITADO",
            flags=["FRAUDE PROVAVEL: titulo anuncia PSA 10 mas condicao diz UNGRADED"],
            url="https://www.ebay.com/itm/444", item_id="444"),
        # Diagnostico: 12% e 17% (nao sao oportunidade no modo --sensitivity)
        row(card="Gengar", number="94", pokemon="Gengar", pokemon_rank=3,
            price=88.0, fair_value=100.0, discount_pct=12.0, roi_pct=13.64,
            spread_usd=12.0, margin_pct=13.64, ref_n_sales=2, ref_liquidity="thin",
            verdict="REVISAR", reasons=["vendas<3(n=2)"],
            url="https://www.ebay.com/itm/555", item_id="555"),
        row(card="Mewtwo", number="10", pokemon="Mewtwo", pokemon_rank=6,
            price=83.0, fair_value=100.0, discount_pct=17.0, roi_pct=20.48,
            spread_usd=17.0, margin_pct=20.48, verdict="OPORTUNIDADE",
            url="https://www.ebay.com/itm/666", item_id="666"),
    ]
    meta = {"timestamp": "2026-09-03T12:00:00+00:00",
            "watchlist_count": 6, "group": "3",
            "include_raw": True, "trusted_mode": False, "aborted": False,
            "config": {"min_discount_percent": 10, "min_price_usd": 5.0,
                       "graded_allow": ["PSA 10", "PSA 9"]},
            "funnel": {"seen": 120, "skip_not_fixed_price": 7, "slab_no_reference": 3}}
    meta.update(meta_extra)
    return {"meta": meta, "rows": rows}


# ── modo padrao (4 buckets) ─────────────────────────────────────────────────────

def test_all_four_sections_always_present():
    md = ebay_summary.build_markdown(payload())
    for title in ("## 🟢 OPORTUNIDADE", "## ⚠️ REVISAR (validar manualmente)",
                  "## 🚨 SUSPEITO (margem alta demais — validar)",
                  "## ⛔ REJEITADO"):
        assert title in md


def test_empty_bucket_renders_placeholder_not_dropped():
    p = payload()
    p["rows"] = [row()]
    md = ebay_summary.build_markdown(p)
    assert "## ⛔ REJEITADO" in md
    assert "_Nenhuma linha neste bucket._" in md


def test_all_rows_present_including_rejected_with_reason():
    md = ebay_summary.build_markdown(payload())
    for name in ("Charizard 4", "Umbreon VMAX 215", "Pikachu 25", "Blastoise 2",
                 "Gengar 94", "Mewtwo 10"):
        assert name in md
    assert "FRAUDE PROVAVEL" in md


def test_comc_columns_header():
    md = ebay_summary.build_markdown(payload())
    assert ("| # | Desconto% | ROI bruto% | eBay$ | Ref$ | Spread$ | Pokémon | Carta | Set "
            "| Tipo | Ref | Vend | Status | Links | Flags |") in md
    assert "| # | Carta | Tipo | eBay$ | Motivo | Links |" in md


def test_every_row_has_both_links_reference_is_pricecharting_page():
    md = ebay_summary.build_markdown(payload())
    # raw com margem TCG: link [referência] = pagina PriceCharting (decisao do operador)
    assert ("[oferta](https://www.ebay.com/itm/222) · "
            "[referência](https://www.pricecharting.com/game/pokemon-evolving-skies/"
            "umbreon-vmax-215)") in md
    assert ("[oferta](https://www.ebay.com/itm/111) · "
            "[referência](https://www.pricecharting.com/game/pokemon-base-set/"
            "charizard-4)") in md
    # rejeitado tambem carrega os dois links
    rej = md.split("## ⛔ REJEITADO")[1]
    assert "[oferta](https://www.ebay.com/itm/444)" in rej and "[referência](" in rej


def test_missing_pc_url_falls_back_to_tcg_link():
    p = payload()
    p["rows"] = [row(grade="RAW", listing_type="Raw NM", ref_source="tcgplayer",
                     pc_url="", ref_url="", tcg_url="https://www.tcgplayer.com/product/1")]
    md = ebay_summary.build_markdown(p)
    assert ("[oferta](https://www.ebay.com/itm/111) · "
            "[TCG](https://www.tcgplayer.com/product/1)") in md


def test_missing_url_shows_only_existing_link():
    p = payload()
    p["rows"] = [row(pc_url="", ref_url="", tcg_url="")]
    md = ebay_summary.build_markdown(p)
    assert "[oferta](https://www.ebay.com/itm/111)" in md
    assert "[referência](" not in md
    assert "· \n" not in md


def test_urls_percent_encoded():
    p = payload()
    p["rows"] = [row(url="https://www.ebay.com/itm/Charizard (Holo) 4/102")]
    md = ebay_summary.build_markdown(p)
    assert "[oferta](https://www.ebay.com/itm/Charizard%20%28Holo%29%204/102)" in md


def test_status_cell_has_verdict_reasons_and_notes():
    md = ebay_summary.build_markdown(payload())
    assert "| REVISAR · ref-desalinhada(1.6x) |" in md
    assert "| REVISAR · vendas<3(n=2) |" in md
    assert "| SUSPEITO · baixa-liquidez(365d) |" in md


def test_ref_and_tipo_columns():
    md = ebay_summary.build_markdown(payload())
    assert "| PSA 9 | PC vendas PSA 9 (n=6, 2026-04..2026-08) |" in md
    assert "| Raw NM | TCG market |" in md
    assert "| Raw LP | PC vendas LP (n=4, 2026-06..2026-08) |" in md


def test_ranking_roi_then_discount_then_spread_then_pokemon():
    p = payload()
    p["rows"] = [
        row(card="A", roi_pct=10.0, discount_pct=9.0, spread_usd=1.0, pokemon_rank=5,
            item_id="a", url="https://www.ebay.com/itm/a"),
        row(card="B", roi_pct=10.0, discount_pct=9.0, spread_usd=1.0, pokemon_rank=1,
            item_id="b", url="https://www.ebay.com/itm/b"),
        row(card="C", roi_pct=30.0, discount_pct=5.0, spread_usd=0.5, pokemon_rank=9,
            item_id="c", url="https://www.ebay.com/itm/c"),
    ]
    md = ebay_summary.build_markdown(p)
    assert md.index("| C 4") < md.index("| B 4") < md.index("| A 4")


def test_flags_and_pipe_escaped():
    md = ebay_summary.build_markdown(payload())
    assert "| Links | Flags |" in md
    assert "mediana \\| conferir" in md


def test_header_params_counts_coverage_and_funnel():
    md = ebay_summary.build_markdown(payload())
    assert "# Scan eBay — 2026-09-03" in md
    assert "Watchlist: 6 carta(s) · grupo `3`" in md
    assert "desconto mínimo 10% · piso US$5.0 · só preço fixo · só item nos EUA" in md
    assert "slabs aceitos: PSA 10, PSA 9" in md
    assert "2 OPORTUNIDADE · 2 REVISAR · 1 SUSPEITO · 1 REJEITADO" in md
    assert ("Cobertura de referência: 4 slabs (mediana de vendas PC) · "
            "1 raw NM c/ TCGplayer market · 1 raw LP (vendas LP PC) · "
            "0 raw só PriceCharting (fallback rotulado) · 0 sem referência") in md
    assert ("Funil: Anúncios analisados (após dedupe): 120 · "
            "Ignorados: leilão (só preço fixo): 7") in md
    assert "sem referência: 3" in md


def test_aborted_run_is_flagged_in_header():
    md = ebay_summary.build_markdown(payload(aborted=True))
    assert "RUN ABORTADO" in md


def test_unknown_verdict_goes_to_review_never_dropped():
    p = payload()
    p["rows"] = [row(verdict="???", card="Zapdos")]
    md = ebay_summary.build_markdown(p)
    assert "Zapdos" in md.split("## ⚠️ REVISAR")[1].split("## ")[0]


# ── modo --sensitivity ───────────────────────────────────────────────────────────

def test_parse_sensitivity():
    assert ebay_summary.parse_sensitivity("10,15,20") == [10, 15, 20]
    assert ebay_summary.sensitivity_bands([10, 15, 20]) == [(20, None), (15, 20), (10, 15)]
    for bad in ("20,15", "0,10", "a,b", ""):
        with pytest.raises(Exception):
            ebay_summary.parse_sensitivity(bad)


def test_sensitivity_sections_and_counts():
    md = ebay_summary.build_markdown(payload(), sensitivity=[10, 15, 20])
    assert "## 🟢 ≥20% — candidato comercial (sujeito às demais validações)" in md
    assert "## ⚠️ ≥20% — REVISAR / SUSPEITO (validar manualmente)" in md
    assert "## 🔬 Diagnóstico 15–19,99% — NÃO é oportunidade" in md
    assert "## 🔬 Diagnóstico 10–14,99% — NÃO é oportunidade" in md
    assert "## ⛔ REJEITADO (todas as faixas)" in md
    # contagens acumuladas: >=20: 1 OK (Charizard) + 2 rev (Umbreon, Pikachu)
    assert "| ≥20% | 1 | 2 | 3 |" in md
    assert "| ≥15% | 2 | 2 | 4 |" in md
    assert "| ≥10% | 2 | 3 | 5 |" in md
    # linhas nas faixas certas
    band20 = md.split("## 🟢 ≥20%")[1].split("## ⚠️ ≥20%")[0]
    assert "Charizard 4" in band20 and "Mewtwo 10" not in band20
    band15 = md.split("## 🔬 Diagnóstico 15–19,99%")[1].split("## ")[0]
    assert "Mewtwo 10" in band15
    band10 = md.split("## 🔬 Diagnóstico 10–14,99%")[1].split("## ")[0]
    assert "Gengar 94" in band10
    rej = md.split("## ⛔ REJEITADO")[1]
    assert "Blastoise 2" in rej
    assert "limiar operacional 20%" in md


def test_sensitivity_warns_when_scan_min_above_lowest_band():
    p = payload()
    p["meta"]["config"]["min_discount_percent"] = 15
    md = ebay_summary.build_markdown(p, sensitivity=[10, 15, 20])
    assert "faixas abaixo de 15% ficam vazias por construção" in md


def test_cli_writes_file_and_prints(tmp_path, capsys):
    scan = tmp_path / "scan.json"
    out = tmp_path / "out.md"
    scan.write_text(json.dumps(payload()), encoding="utf-8")
    ebay_summary.main([str(scan), "-o", str(out), "--sensitivity", "10,15,20"])
    body = out.read_text(encoding="utf-8")
    assert "## 🟢 ≥20%" in body
    captured = capsys.readouterr()
    assert "## 🟢 ≥20%" in captured.out


def test_legacy_json_without_new_fields_still_renders():
    # JSON gravado antes do padrao COMC: so margin_pct/ref_kind/ref_url.
    legacy = {"card": "Charizard", "set": "Base Set", "number": "4", "grade": "PSA 10",
              "price": 900.0, "fair_value": 1200.0, "margin_pct": 33.3,
              "ref_kind": "pricecharting",
              "ref_url": "https://www.pricecharting.com/game/pokemon-base-set/charizard-4",
              "verdict": "OPORTUNIDADE", "flags": [], "url": "https://www.ebay.com/itm/9"}
    md = ebay_summary.build_markdown({"meta": {"timestamp": "2026-07-06"}, "rows": [legacy]})
    assert "Charizard 4" in md
    assert "[referência](https://www.pricecharting.com/game/pokemon-base-set/charizard-4)" in md
    assert "| 33.30 |" in md  # ROI bruto = margin_pct antigo


def test_console_and_delivery_share_links_helper():
    assert report.links_cell("u", "r", ref_label="TCG",
                             keep_placeholders=False) == "[oferta](u) · [TCG](r)"
    assert report.links_cell("", "", keep_placeholders=True) == "— · —"
    assert report.links_cell("u", "", keep_placeholders=False) == "[oferta](u)"
