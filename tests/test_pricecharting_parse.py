import os

from src import pricecharting

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "pc_charizard_base.html")


def fair():
    with open(FIXTURE, encoding="utf-8") as f:
        return pricecharting.parse_product_page(f.read(), source_url="fixture")


def test_grades_extracted():
    fv = fair()
    assert fv.prices["RAW"] == 338.42
    # A pagina rotula a coluna como "Grade 9" -- bucket GENERICO (mistura
    # certificadoras: PSA, BGS, CGC...). Chamar isso de "PSA 9" e rotulo
    # enganoso (auditoria de honestidade, Fase 1); `src/pc_sales.py` ja le
    # a mesma coluna como GRADE 9.
    assert fv.prices["GRADE 9"] == 3175.04
    assert "PSA 9" not in fv.prices
    assert fv.prices["PSA 10"] == 30085.73
    assert fv.prices["BGS 10"] == 39111.00
    assert fv.prices["CGC 10"] == 7605.63


def test_trend_deltas():
    fv = fair()
    assert fv.deltas["RAW"] == -0.62
    assert fv.deltas["GRADE 9"] == 39.13
    assert "PSA 9" not in fv.deltas


def test_volume_liquidity():
    fv = fair()
    # raw do Charizard base vende ~2/semana ou mais -> >= 4/mes
    assert fv.sales_per_month.get("RAW", 0) >= 4
    # PSA 10 e raro: ~1/mes
    assert 0 < fv.sales_per_month.get("PSA 10", 0) <= 3
    # volume do bucket generico tambem sai com o rotulo honesto
    assert "PSA 9" not in fv.sales_per_month


def test_same_column_keys_as_pc_sales_parser():
    """As duas leituras da mesma pagina (colunas informativas em `pricecharting`
    e colunas de sanidade em `pc_sales.parse_grade_prices`) tem de usar as
    MESMAS chaves para as mesmas colunas -- senao a mesma coluna ganha dois nomes."""
    from src import pc_sales
    assert pricecharting.FULL_TABLE_GRADE_BY_LABEL["Grade 9"] == pc_sales.FULL_TABLE_GRADE_BY_LABEL["Grade 9"]
    assert pricecharting.MAIN_TABLE_GRADE_BY_ID["graded_price"] == pc_sales.MAIN_TABLE_GRADE_BY_ID["graded_price"]
