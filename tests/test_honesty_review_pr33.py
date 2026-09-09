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


# --- review 2: todo contador que o scanner incrementa tem rotulo (nunca "outros:") --

def _stats_keys_incremented_in_source():
    keys = set()
    for path in (ROOT / "src" / "scanner.py", ROOT / "src" / "scorer.py"):
        text = path.read_text(encoding="utf-8")
        keys |= set(re.findall(r"""stats\[['"]([a-z_]+)['"]\]""", text))
        keys |= set(re.findall(r"""_skip\(stats,\s*['"]([a-z_]+)['"]\)""", text))
    keys |= set(re.findall(r"""['"](rows_[a-z_]+)['"]""",
                           (ROOT / "src" / "scorer.py").read_text(encoding="utf-8")))
    assert {"seen", "item_details_fetched", "item_details_error", "ebay_budget_exhausted"} <= keys
    return keys


def test_every_scanner_counter_has_a_funnel_label():
    keys = _stats_keys_incremented_in_source()
    missing = keys - report._KNOWN_FUNNEL_KEYS
    assert not missing, f"contadores sem rotulo (cairiam em 'outros:'): {sorted(missing)}"


def test_policy_only_counters_are_labelled_in_both_vocabularies():
    counts = {"seen": 4, "item_details_fetched": 4, "item_details_error": 1, "ebay_budget_exhausted": 1}
    for lines in (report.funnel_lines(counts), report.policy_funnel_lines(counts)):
        joined = " · ".join(lines)
        assert "outros:" not in joined
        assert "get_item" in joined or "detalhe" in joined
        assert "run parcial" in joined


# --- review 3: linha Coleta declara --grades e --confiavel (o cabecalho legado ja declarava) --

def test_collection_line_states_grades_filter_and_trusted_flag():
    payload = _policy_payload()
    meta = payload["meta"]
    plain = slab_report.collection_line(meta)
    assert "--grades" not in plain and "--confiavel" not in plain
    meta["config"]["allowed_grades"] = ["PSA 10", "CGC 10 Pristine"]
    meta["trusted_mode"] = True
    line = slab_report.collection_line(meta)
    assert "notas do run: PSA 10 + CGC 10 Pristine (--grades)" in line
    assert "--confiavel" in line and "sem efeito na política" in line


# --- review 4: --confiavel com a politica ativa avisa que nao muda nada --

def test_confiavel_with_policy_prints_an_explicit_no_effect_warning(monkeypatch, tmp_path, capsys):
    assert _run_main(monkeypatch, tmp_path, Counter(seen=1, rows_opportunity=1), ["--confiavel"]) == 0
    out = capsys.readouterr().out
    # O AVISO proprio do main.py (a linha "Coleta:" tambem declara a flag, mas so no
    # relatorio; o aviso tem que existir mesmo sem linha nenhuma).
    assert "AVISO: --confiavel sem efeito na política vigente" in out


# --- review 5: timestamp da Coleta robusto (sem fuso / microssegundos / lixo) --

def test_collection_when_handles_naive_micro_and_garbage_timestamps():
    def when(stamp):
        return slab_report.collection_line({"timestamp": stamp}).split(" · ")[0]
    assert when("2026-09-09T07:25:58+00:00") == "2026-09-09 07:25 UTC"
    assert when("2026-09-09T07:25:58Z") == "2026-09-09 07:25 UTC"
    assert when("2026-09-09T07:25:58") == "2026-09-09 07:25 (fuso não informado)"
    assert when("2026-09-09T07:25:58.123456") == "2026-09-09 07:25 (fuso não informado)"
    assert when("2026-09-09T07:25:58-03:00") == "2026-09-09 07:25 -03:00"
    assert when("ontem") == "n/d"


# --- review 6: chaves do gate na Coleta seguem o gate_mode (all_minima tem outras chaves) --

def test_collection_line_lists_the_keys_of_the_active_gate_mode():
    payload = _policy_payload()
    meta = payload["meta"]
    eco = meta["config"]["slab_strategy"]["economics"]
    eco.update({"gate_mode": "all_minima", "min_net_margin_percent": 12, "min_net_roi_percent": 25,
                "min_discount_percent": None})
    meta["config"]["min_discount_percent"] = 33
    line = slab_report.collection_line(meta)
    assert "gate_mode: all_minima" in line
    assert "min_net_margin_percent: 12" in line and "min_net_roi_percent: 25" in line
    assert "min_discount_percent: 33" in line  # o de TOPO do config, que e o efetivo nesse modo
    assert "min_discount_percent: n/d" not in line
