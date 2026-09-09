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
                   "gate_mode: gross_margin", "min_gross_margin_percent: 43",
                   "docs/EBAY_PSA.md", "slab_report"):
        assert needle in text, f"skill sem {needle!r}"
    # O gate vigente usa SO margem bruta: a skill nao pode voltar a vender o modo
    # antigo como regra em vigor (ele so sobrevive como modo legado, dito assim).
    assert "gate_mode: profit_or_discount" not in text


def test_skill_and_docs_declare_the_gate_mode_the_config_actually_has():
    """Guarda de drift do GATE: o texto operacional tem de nomear o `gate_mode` que
    esta de fato no config.yaml, e o limiar que aquele modo usa. Trocar o modo no
    config sem atualizar skill/doc passa a quebrar aqui."""
    import yaml
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    eco = cfg["slab_strategy"]["economics"]
    mode = eco["gate_mode"]
    threshold_key = {"gross_margin": "min_gross_margin_percent",
                     "profit_or_discount": "min_discount_percent"}[mode]
    threshold = eco[threshold_key]
    assert isinstance(threshold, int), (
        f"convencao do repo: percentual INTEIRO; {threshold_key}={threshold!r}")
    for path in (SKILL, ROOT / "docs" / "EBAY_PSA.md"):
        text = path.read_text(encoding="utf-8")
        assert f"gate_mode: {mode}" in text, f"{path.name} nao nomeia o gate vigente"
        assert f"{threshold_key}: {threshold}" in text, f"{path.name} sem o limiar vigente"


def test_longterm_docs_use_the_real_fragility_flag_count():
    """Guarda de drift da COLUNA: toda contagem de flags de fragilidade escrita no
    texto operacional tem de bater com `len(longterm.FRAGILITY_FLAGS)`. Cobre as tres
    formas em que ela aparece: a celula de cobertura (`4/5·9/11`), a cobertura solta
    entre parenteses (`0 (3/11)`) e a contagem por extenso ("9 das 11 flags", "3 dos 11
    testes"). Acrescentar ou remover uma flag sem mexer nas docs quebra aqui."""
    from src import longterm
    n = len(longterm.FRAGILITY_FLAGS)
    cell = re.compile(r"·\s*(\d+)/(\d+)")          # 4/5·9/11 -> denominador da fragilidade
    paren = re.compile(r"\((\d+)/(\d+)\)")              # 0 (3/11)
    spelled = re.compile(r"d[oa]s (\d+) (?:flags|fontes|testes)")
    for name in ("docs/LONGO_PRAZO.md", "README.md",
                 ".claude/skills/scan-ebay/SKILL.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        found = ([int(d) for _, d in cell.findall(text)]
                 + [int(d) for _, d in paren.findall(text)]
                 + [int(d) for d in spelled.findall(text)])
        assert found, f"{name} sem nenhuma contagem de fragilidade para conferir"
        wrong = [d for d in found if d != n]
        assert not wrong, f"{name} com contagem desatualizada: {wrong} (real: {n})"
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
