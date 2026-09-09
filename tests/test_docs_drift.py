"""Guarda contra "drift" de documentacao: texto operacional (skill, docstring, --help)
descrevendo um modo que o codigo ja nao tem.

Auditoria de honestidade, Fase 1 (2026-09-09), classe (iii) rotulo enganoso: a skill
`scan-ebay` e a docstring de `main.py` ainda ofereciam `--include-raw` (rejeitado desde a
politica 2026-09-05.4), `--min-price 5 --min-discount 10` como "modo diagnostico" e
`min_discount_percent: 20` (historico pre-#29; o config diz 30), e descreviam a entrega
com os baldes do motor legado (OPORTUNIDADE/SUSPEITO). Estes testes fixam que o texto
operacional so usa flags que a CLI aceita e descreve a politica por chave de config.
"""
import re
from collections import Counter
from pathlib import Path

import main
import ebay_summary
from src import report, scanner
from tests.test_slab_strategy import CARD

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "scan-ebay" / "SKILL.md"


def _cli_flags(path):
    return set(re.findall(r"""add_argument\(\s*['"](--[a-z][a-z-]*)""", path.read_text(encoding="utf-8")))


def test_skill_uses_only_flags_the_cli_accepts_and_no_removed_modes():
    text = SKILL.read_text(encoding="utf-8")
    known = _cli_flags(ROOT / "main.py") | _cli_flags(ROOT / "ebay_summary.py")
    used = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", text))
    assert used <= known, f"flags na skill que a CLI nao aceita: {sorted(used - known)}"
    # `--include-raw` so existe no parser para ser REJEITADO (ap.error): a skill nao pode
    # oferece-lo como modo. `--min-price 5` e `min_discount_percent: 20` sao o historico
    # pre-#29 -- o config vigente diz 30 e a regra efetiva esta em `slab_strategy.economics`.
    assert "--include-raw" not in text
    assert "--min-price 5" not in text
    assert "min_discount_percent: 20" not in text and "--min-discount 20" not in text
    # baldes do motor legado nao sao a entrega vigente
    assert "SUSPEITO" not in text and "OPORTUNIDADE" not in text
    for needle in ("APROVAR", "REJEITAR", "REVISAR", "DELIVERY_CHAT.md",
                   "gate_mode: profit_or_discount", "min_discount_percent: 30",
                   "docs/EBAY_PSA.md", "slab_report"):
        assert needle in text, f"skill sem {needle!r}"


def test_main_docstring_and_help_do_not_advertise_the_removed_diagnostic_mode(capsys):
    doc = main.__doc__
    for stale in ("--min-price 5", "--min-discount 10", "--include-raw"):
        assert stale not in doc, stale
    try:
        main.main(["--help"])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "so tem efeito com --include-raw" not in out
    assert "diagnostico: 5" not in out and "diagnostico: 10" not in out


def test_main_no_longer_passes_the_rejected_include_raw_flag_to_the_payload(monkeypatch, tmp_path):
    captured = {}
    real = report.scan_payload

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(report, "scan_payload", spy)
    monkeypatch.setattr(scanner, "load_watchlist", lambda *a, **k: [CARD])
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: ({}, [], False, Counter(seen=0), False))
    assert main.main(["--out", str(tmp_path / "o.json"), "--csv", str(tmp_path / "o.csv")]) == 0
    assert "include_raw" not in captured
    assert (tmp_path / "o.json").exists()


def test_summary_docstring_says_where_the_policy_table_comes_from():
    doc = ebay_summary.__doc__
    assert "slab_report" in doc
    assert "legado" in doc  # --sensitivity e os 4 baldes valem so para JSON legado
