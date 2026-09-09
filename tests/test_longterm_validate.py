"""`longterm_validate.py` -- validacao minima da coluna "Longo prazo" (teste sintetico de
mecanica, no padrao de outlook/validate.py). Escrito ANTES do script (Fase 2, TDD):
enquanto o arquivo nao existe, cada teste falha com ModuleNotFoundError.

O que o script faz sobre o JSON de um scan:
- AGREGA por chave (carta, numero, nota) ANTES de qualquer estatistica: 11 anuncios do
  mesmo item contam 1 (senao seria pseudo-replicacao = contar o mesmo item varias vezes
  e inflar a estatistica). Mediana de `fair_value` e do premio de nota por chave.
- Exige n >= 30 chaves; abaixo disso imprime "n insuficiente (k cartas)" e NAO inventa
  rho (Spearman, correlacao de postos: mede se "nota maior" acompanha "preco maior").
- Com n >= 30: rho de B1, B2, B3, B5 e do PERFIL-sem-B4 contra (a) `fair_value` e (b) o
  premio PSA 10 / RAW; B4 EXCLUIDO (e derivado de preco -- seria circular). Rotulos:
  rho > 0.1 OK, -0.1..0.1 fraco, <= -0.1 invertido.
- Snapshot datado em CSV (insumo de um backtest futuro, so com >= 2 snapshots).
- Frases obrigatorias: "calibracao transversal nao e prova de valorizacao futura"
  (valorizacao = subida de preco ao longo do tempo) e "rho calculado sobre chaves
  (carta, numero, nota), nao sobre anuncios".
"""
import csv
import json
from pathlib import Path


def _lv():
    import longterm_validate
    return longterm_validate


def _row(card, number, grade, fair_value, rank, rarity="Rare Holo", era="vintage",
         year=1999, trend=None, psa10=None, raw=None, tier="LP2", profile=60.0,
         fragility=20.0, price=100.0, heavy=False, trend_source=None, ref_source="ref_*",
         strategy=None):
    row = {"card": card, "number": number, "grade": grade, "price": price,
           "fair_value": fair_value, "longterm_profile": profile,
           "longterm_fragility": fragility, "longterm_tier": tier,
           "longterm_coverage": "4/5·9/11", "longterm_reasons": [],
           "longterm_signals": {"pokemon_rank": rank, "rarity_raw": rarity, "era": era,
                                "year": year, "age_years": (2026 - year) if year else None,
                                "heavy_reprint": heavy, "trend_12m_pct": trend,
                                "trend_source": trend_source, "psa10_col": psa10,
                                "raw_col": raw, "ref_source": ref_source},
           "trend_12m_pct": trend, "trend_source": trend_source or ""}
    if strategy is not None:
        row["strategy"] = strategy
    return row


def _universe(n=30):
    """n chaves distintas em que rank melhor (menor) acompanha fair_value maior e o
    premio PSA 10/RAW cresce com o preco -- mecanica sintetica, nao mercado."""
    rows = []
    for i in range(n):
        fv = 1000.0 - i * 20
        rows.append(_row(f"C{i}", str(i), "PSA 10", fair_value=fv, rank=i + 1,
                         rarity=("Special Illustration Rare" if i < 10 else "Rare Holo"),
                         year=1999 + i // 3, trend=30.0 - i, psa10=fv * 3, raw=fv,
                         tier=("LP1" if i < 5 else "LP2" if i < 20 else "n/d"),
                         profile=(90.0 - i if i < 20 else None)))
    return rows


def test_18_aggregates_by_card_number_grade_and_refuses_rho_below_30_keys():
    lv = _lv()
    same = [_row("Clefairy", "5", "PSA 10", fair_value=100.0 + i, rank=30, price=90.0 + i)
            for i in range(11)]
    others = [_row(f"Card{i}", str(i), "PSA 9", 50.0, rank=i + 1) for i in range(11)]
    keys = lv.aggregate_by_key(same + others)
    assert len(keys) == 12
    k = keys[("Clefairy", "5", "PSA 10")]
    assert k["n_listings"] == 11 and k["fair_value"] == 105.0  # mediana, nao 11 linhas
    assert keys[("Card0", "0", "PSA 9")]["n_listings"] == 1
    text = lv.calibration_report(same + others)
    assert "n insuficiente (12 cartas)" in text
    assert "| B1" not in text and "ρ =" not in text  # nenhum rho inventado
    assert "ρ calculado sobre chaves (carta, número, nota), não sobre anúncios" in text
    assert "calibração transversal não é prova de valorização futura" in text
    # cobertura por sinal continua reportada (qual campo faltou), mesmo com n < 30
    assert "trend_12m_pct" in text and "psa10_col" in text


def test_18b_synthetic_mechanics_spearman_labels_and_b4_excluded():
    lv = _lv()
    assert lv.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert lv.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert lv.spearman([1, 1], [1, 2]) != lv.spearman([1, 1], [1, 2])  # NaN: sem variancia
    assert lv.flag(0.5) == "✅" and lv.flag(0.0) == "⚠️ fraco" and lv.flag(-0.5) == "❌ invertido"
    # 2o anuncio da MESMA chave (C0, 0, PSA 10): conta 1 chave, 31 anuncios
    rows = _universe(30) + [_row("C0", "0", "PSA 10", 990.0, rank=1, psa10=2970.0,
                                 raw=990.0, tier="LP1", profile=90.0)]
    text = lv.calibration_report(rows)
    assert "n = 30 chaves" in text and "31 anúncios" in text
    for comp in ("B1", "B2", "B3", "B5", "PERFIL-sem-B4"):
        assert f"| {comp}" in text, comp
    assert "| B4" not in text and "B4 excluído" in text and "circular" in text
    b1 = next(ln for ln in text.splitlines() if ln.startswith("| B1"))
    assert "✅" in b1  # rank melhor <-> preco maior na mecanica sintetica
    assert "LP1" in text and "n/d" in text  # distribuicao de classes
    assert "5 LP1" in text and "15 LP2" in text and "10 n/d" in text
    assert "LP1 = 16.7%" in text  # sanidade: LP1 > 30% das chaves exige explicacao
    assert "0% de LP1 é esperado no caminho slab_strategy" not in text  # so quando ha strategy
    assert "ρ calculado sobre chaves (carta, número, nota), não sobre anúncios" in text
    assert "calibração transversal não é prova de valorização futura" in text


def test_18c_policy_rows_declare_the_lp2_star_ceiling_and_lp1_share_sanity():
    lv = _lv()
    rows = [_row(f"P{i}", str(i), "PSA 10", 500.0 - i, rank=i + 1, tier="LP2*",
                 ref_source="psa_evidence", strategy={"policy_version": "x"})
            for i in range(30)]
    text = lv.calibration_report(rows)
    assert "0% de LP1 é esperado no caminho slab_strategy" in text
    assert "30 LP2" in text  # LP2* conta como LP2 na distribuicao
    many_lp1 = [_row(f"Q{i}", str(i), "PSA 10", 500.0 - i, rank=i + 1, tier="LP1")
                for i in range(30)]
    text2 = lv.calibration_report(many_lp1)
    assert "LP1 = 100.0%" in text2 and "acima de 30%" in text2  # sanidade disparou


def test_18d_snapshot_csv_and_cli(tmp_path, capsys):
    lv = _lv()
    rows = _universe(30)
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"meta": {"timestamp": "2026-09-09T10:00:00+00:00"},
                                "rows": rows}), encoding="utf-8")
    snap_dir = tmp_path / "snapshots"
    path = lv.write_snapshot(rows, snap_dir, day="2026-09-09")
    assert Path(path).name == "longterm_2026-09-09.csv"
    with open(path, encoding="utf-8", newline="") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 30
    assert set(data[0]) >= {"date", "card", "number", "grade", "price", "fair_value",
                            "perfil", "fragilidade", "classe", "coberturas", "fontes"}
    assert data[0]["date"] == "2026-09-09" and data[0]["classe"] == "LP1"
    assert data[25]["perfil"] == "n/d"  # None nunca vira 0 nem string vazia
    assert lv.main([str(scan), "--snapshot-dir", str(snap_dir)]) == 0
    out = capsys.readouterr().out
    assert "n = 30 chaves" in out and "| B1" in out
    assert "longterm_2026-09-09.csv" in out
