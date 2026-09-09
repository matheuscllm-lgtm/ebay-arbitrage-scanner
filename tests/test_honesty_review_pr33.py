"""Correcoes da revisao do PR #33 (auditoria de honestidade, Fase 1 -- 2026-09-09).

Cada teste aqui nasceu VERMELHO (falhando) antes da correcao correspondente.
Vocabulario: "console" = o que `main.py` imprime no terminal no fim do run;
"entrega canonica" = o .md gerado por `ebay_summary.py` a partir do JSON do scan;
"meta" = bloco de metadados do JSON (quando, o que e com qual regra a coleta rodou);
"funil" = contadores de quantos anuncios entraram/sairam em cada etapa.
"""
import re
from collections import Counter
from pathlib import Path

import main
import ebay_summary
from src import report, scanner, slab_report
from tests.test_honesty_fase1 import _policy_payload

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "scan-ebay" / "SKILL.md"


def _policy_opp(**cfg_extra):
    from src.slab_strategy import evaluate, policy_config
    from tests.test_slab_strategy import CARD as PCARD, listing, sales, refs
    c = policy_config()
    c.update(cfg_extra)
    return PCARD, evaluate(PCARD, listing(price=50), config=c, refs=refs(sales()))


def _run_main(monkeypatch, tmp_path, funnel, extra_args=()):
    card, opp = _policy_opp()
    monkeypatch.setattr(scanner, "load_watchlist", lambda *a, **k: [card])
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: ({}, [opp], False, funnel, False))
    return main.main(["--out", str(tmp_path / "o.json"), "--csv", str(tmp_path / "o.csv"),
                      *extra_args])


# --- review 1: console da politica usa o MESMO meta do JSON (nada de zero fabricado) --

def test_console_policy_report_uses_the_scan_meta(monkeypatch, tmp_path, capsys):
    assert _run_main(monkeypatch, tmp_path, Counter(seen=1, rows_opportunity=1, ebay_calls=2, cards=1)) == 0
    out = capsys.readouterr().out
    head = out.split("| Carta")[0]
    # Coleta: vem do meta real (grupo, cartas, versao da politica), nunca "n/d" por omissao.
    assert "1 carta(s)" in head and "2026-09-05.4" in head and "chamadas à Browse API: 2" in head
    assert "política `n/d`" not in head
    # Funil do relatorio: contador real (1), nunca o zero de um dict vazio.
    assert "Anúncios analisados (após dedupe): 1" in out
    assert "analisados (após dedupe): 0" not in out


def test_render_without_meta_never_fabricates_a_zero_funnel():
    text = slab_report.render({"rows": []})
    assert "analisados (após dedupe): 0" not in text
    assert "Funil da busca: n/d" in text
    assert "Coleta: n/d" in text and "None" not in text


def test_to_markdown_accepts_meta_and_threads_it_to_the_policy_report():
    payload = _policy_payload(group="7")
    card, opp = _policy_opp()
    text = report.to_markdown([opp], meta=payload["meta"])
    assert "grupo `7`" in text and "política `2026-09-05.4`" in text
