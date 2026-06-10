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


def test_rejected_below_threshold_is_dropped():
    # raw sem NM e margem negativa: nao vira linha nenhuma (nem REJEITADO)
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo", 400.0), FAIR)
    assert o is None


def test_grade_vs_condition_fraud():
    # caso real 2026-06-10: "PSA 10" no titulo, condicao eBay = Ungraded
    o = scorer.evaluate(
        CARD,
        L("Charizard 4/102 Base Set Holo PSA 10", 1800.0,
          condition="Ungraded - Like New or better", seller_feedback_score=0),
        FAIR,
    )
    assert o is not None
    assert o.verdict == "REJEITADO"
    assert any("FRAUDE" in f for f in o.risk_flags)


def test_graded_condition_consistent_ok():
    o = scorer.evaluate(
        CARD, L("Charizard 4/102 Base Set PSA 9", 2200.0, condition="Graded"),
        FAIR,
    )
    assert o is not None
    assert not any("FRAUDE" in f for f in o.risk_flags)


def test_raw_with_ungraded_condition_ok():
    # raw legitimo: condicao "Ungraded" nao pode disparar o check de 'Graded'
    o = scorer.evaluate(
        CARD,
        L("Charizard 4/102 Base Set Holo NM", 200.0,
          condition="Ungraded - Near Mint or better"),
        FAIR,
    )
    assert o is not None
    assert not any("identidade" in f for f in o.risk_flags)


# --- modo confiavel + trust score ---------------------------------------------

def test_trust_score_layers():
    weak = L("t", 100.0, seller_feedback_score=0, seller_feedback_pct=0.0)
    strong = L("t", 100.0, seller_feedback_score=5000, seller_feedback_pct=99.9)
    armored = L("t", 100.0, seller_feedback_score=5000, seller_feedback_pct=99.9,
                authenticity_guarantee=True, top_rated=True)
    assert scorer.trust_score(weak) <= 15
    assert scorer.trust_score(strong) >= 80
    assert scorer.trust_score(armored) == 100.0


def test_trusted_mode_filters_new_seller():
    cfg = {"trusted_mode": True}
    o = scorer.evaluate(
        CARD, L("Charizard 4 Base Set PSA 9", 2200.0, seller_feedback_score=3),
        FAIR, cfg)
    assert o is None


def test_trusted_mode_filters_huge_margin():
    # margem 1343% (Celebrations-like) some no modo confiavel
    cfg = {"trusted_mode": True}
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 9", 220.0), FAIR, cfg)
    assert o is None


def test_trusted_mode_keeps_good_seller_healthy_margin():
    cfg = {"trusted_mode": True}
    o = scorer.evaluate(
        CARD,
        L("Charizard 4 Base Set PSA 9", 2200.0,
          seller_feedback_score=850, seller_feedback_pct=99.7, top_rated=True),
        FAIR, cfg)
    assert o is not None
    assert o.verdict == "OPORTUNIDADE"
    assert o.trust_score >= 75


def test_trusted_mode_drops_rejected_rows():
    cfg = {"trusted_mode": True}
    o = scorer.evaluate(
        CARD,
        L("Charizard 4/102 Base Set Holo", 200.0,   # raw sem NM -> rejeitado
          seller_feedback_score=850, seller_feedback_pct=99.7),
        FAIR, cfg)
    assert o is None


# --- localizacao US-only (entrega na COMC, Algona WA) ---------------------------

def test_non_us_listing_dropped():
    o = scorer.evaluate(
        CARD, L("Charizard 4 Base Set PSA 9", 2200.0, country="JP"), FAIR)
    assert o is None


def test_us_listing_kept():
    o = scorer.evaluate(
        CARD, L("Charizard 4 Base Set PSA 9", 2200.0, country="US"), FAIR)
    assert o is not None
