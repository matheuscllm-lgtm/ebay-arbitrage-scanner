from src import scorer
from src.models import WatchCard, Listing, FairValue


CARD = WatchCard(name="Charizard", set_name="Base Set", number="4",
                 language="EN", pc_url="")

FAIR = FairValue(
    prices={"RAW": 338.42, "PSA 9": 3175.04, "PSA 10": 30085.73,
            "GRADE 8": 1199.03},
    deltas={"RAW": -0.62, "PSA 9": 39.13, "PSA 10": 0.0},
    sales_per_month={"RAW": 60.0, "PSA 9": 30.0, "PSA 10": 1.0},
)


def L(title, price, **kw):
    defaults = dict(item_id="1", title=title, price=price, shipping=4.5,
                    currency="USD", buying_option="FIXED_PRICE", condition="",
                    seller_feedback_pct=99.8, seller_feedback_score=1200, url="u")
    defaults.update(kw)
    return Listing(**defaults)


def test_psa9_good_margin_is_opportunity():
    # PSA 9 justo $3175; anuncio $2200 -> margem 44%
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 9", 2200.0), FAIR)
    assert o is not None
    assert o.grade == "PSA 9"
    assert 40 < o.gross_margin_pct < 50
    assert o.verdict == "OPORTUNIDADE"
    assert o.liquidity_tier == "A"


def test_below_threshold_not_reported():
    # margem ~13% < 30% -> None
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 9", 2800.0), FAIR)
    assert o is None


def test_too_good_is_suspicious():
    # PSA 10 justo $30k; anuncio $5k -> margem 500% -> SUSPEITO
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 10", 5000.0), FAIR)
    assert o is not None
    assert o.verdict == "SUSPEITO"


def test_raw_without_nm_rejected():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo", 200.0), FAIR)
    assert o is not None
    assert o.verdict == "REJEITADO"
    assert any("CONDICAO" in f for f in o.risk_flags)


def test_raw_nm_has_grading_spread():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 200.0), FAIR)
    assert o is not None
    assert o.spread_psa10_pct > 8000  # PSA10 ~89x o raw
    assert o.spread_psa9_pct > 800


def test_below_price_floor_ignored():
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 9", 9.0), FAIR)
    assert o is None


def test_out_of_scope_grade_rejected():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 8", 500.0), FAIR)
    # PSA 8 tem preco justo (GRADE 8) mas grade fora do escopo -> rejeitado
    assert o is None or o.verdict == "REJEITADO"


def test_wrong_card_ignored():
    o = scorer.evaluate(CARD, L("Blastoise 2/102 Base Set PSA 9", 1000.0), FAIR)
    assert o is None


def test_auction_is_review_not_opportunity():
    o = scorer.evaluate(
        CARD,
        L("Charizard 4/102 Base Set PSA 9", 2200.0, buying_option="AUCTION"),
        FAIR,
    )
    assert o is not None
    assert o.verdict == "REVISAR"
    assert any("LEILAO" in f for f in o.risk_flags)


def test_low_liquidity_flagged():
    fair = FairValue(prices={"PSA 9": 3175.04}, deltas={},
                     sales_per_month={"PSA 9": 0.5})
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 9", 2200.0), fair)
    assert o is not None
    assert o.liquidity_tier == "D"
    assert o.verdict == "REVISAR"
