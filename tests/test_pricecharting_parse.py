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
    assert fv.prices["PSA 9"] == 3175.04
    assert fv.prices["PSA 10"] == 30085.73
    assert fv.prices["BGS 10"] == 39111.00
    assert fv.prices["CGC 10"] == 7605.63


def test_trend_deltas():
    fv = fair()
    assert fv.deltas["RAW"] == -0.62
    assert fv.deltas["PSA 9"] == 39.13


def test_volume_liquidity():
    fv = fair()
    # raw do Charizard base vende ~2/semana ou mais -> >= 4/mes
    assert fv.sales_per_month.get("RAW", 0) >= 4
    # PSA 10 e raro: ~1/mes
    assert 0 < fv.sales_per_month.get("PSA 10", 0) <= 3
