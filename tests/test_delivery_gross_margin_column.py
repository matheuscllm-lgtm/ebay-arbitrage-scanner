"""A tabela de entrega tem de MOSTRAR o número que decide o veredito.

Com `gate_mode: gross_margin` quem aprova ou reprova é a MARGEM BRUTA, mas a tabela
saía com `Desconto %`, `Margem líquida %` e `ROI líquido %` e nenhuma coluna de margem
bruta: o operador lia a decisão sem conseguir ver a conta que a produziu. Mesma classe
de problema que a auditoria de honestidade do PR #33 já tinha atacado.

`Desconto %` continua na tabela: ela é informação útil e é o número dos modos legados.
"""
from src import report, slab_report
from src.slab_strategy import evaluate, policy_config
from tests.test_slab_strategy import CARD, listing, sales, refs

HEADER_CELL = "Margem bruta %"


def _render(price):
    cfg = policy_config()
    opp = evaluate(CARD, listing(price=price), config=cfg, refs=refs(sales()))
    return slab_report.render(report.scan_payload([opp], 1, cfg)), opp


def test_header_carries_the_gross_margin_column_right_after_discount():
    text, _ = _render(50)
    header = next(l for l in text.splitlines() if l.startswith("| Carta"))
    cells = [c.strip() for c in header.strip("|").split("|")]
    assert HEADER_CELL in cells, f"cabeçalho sem margem bruta: {cells}"
    assert cells.index(HEADER_CELL) == cells.index("Desconto %") + 1
    # A coluna informativa continua imediatamente antes de Links (invariante do PR-C).
    assert cells[-2:] == ["Longo prazo", "Links"]


def test_separator_row_matches_the_header_width():
    text, _ = _render(50)
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("| Carta"))
    assert lines[i].count("|") == lines[i + 1].count("|")


def test_data_row_matches_the_header_width():
    text, _ = _render(50)
    lines = text.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("| Carta"))
    data = lines[i + 2]
    assert data.startswith("| [")
    assert data.count("|") == lines[i].count("|")


def test_gross_margin_value_is_the_one_the_gate_compared():
    """O valor na tabela tem de ser o MESMO que o gate usou, não uma segunda conta."""
    text, opp = _render(50)
    gate = (opp.strategy or {}).get("economic_gate") or {}
    assert gate.get("mode") == "gross_margin", gate
    shown = f"{gate['gross_margin_percent']:.2f}".rstrip("0").rstrip(".")
    row = next(l for l in text.splitlines() if l.startswith("| ["))
    assert shown in row, f"margem bruta {shown} não aparece na linha: {row}"


def test_legend_defines_gross_margin():
    text, _ = _render(50)
    assert "Margem bruta = (comparação − compra)/compra" in text
