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



# Modo legado p/ testar a logica de raw (escopo atual e graded-only,
# mas a maquinaria de raw fica testada caso o flag seja revertido).
CFG_RAW = {"graded_only": False}

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
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo", 200.0), FAIR, CFG_RAW)
    assert o is not None
    assert o.verdict == "REJEITADO"
    assert any("CONDICAO" in f for f in o.risk_flags)


def test_raw_nm_has_grading_spread():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 200.0), FAIR, CFG_RAW)
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
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo", 400.0), FAIR, CFG_RAW)
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
        FAIR, CFG_RAW,
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
        FAIR, dict(cfg, graded_only=False))
    assert o is None


def test_trusted_mode_threshold_boundary():
    # Trava o limiar EXATO do modo confiavel: >= 50 avaliacoes E >= 98.0%.
    # (A doc/ajuda ja divergiu para 100/99 no passado; este teste fixa o valor
    # canonico do config p/ que um drift futuro quebre o CI em vez de passar.)
    cfg = {"trusted_mode": True}
    title = "Charizard 4 Base Set PSA 9"  # margem ~44% (saudavel: 30 < m < 60)

    on_edge = scorer.evaluate(
        CARD, L(title, 2200.0, seller_feedback_score=50, seller_feedback_pct=98.0),
        FAIR, cfg)
    assert on_edge is not None, "vendedor exatamente em 50/98.0 deve passar"

    too_few = scorer.evaluate(
        CARD, L(title, 2200.0, seller_feedback_score=49, seller_feedback_pct=98.0),
        FAIR, cfg)
    assert too_few is None, "49 avaliacoes (< 50) deve ser filtrado"

    low_pct = scorer.evaluate(
        CARD, L(title, 2200.0, seller_feedback_score=50, seller_feedback_pct=97.9),
        FAIR, cfg)
    assert low_pct is None, "97.9% (< 98.0) deve ser filtrado"


# --- localizacao US-only (entrega na COMC, Algona WA) ---------------------------

def test_non_us_listing_dropped():
    o = scorer.evaluate(
        CARD, L("Charizard 4 Base Set PSA 9", 2200.0, country="JP"), FAIR)
    assert o is None


def test_us_listing_kept():
    o = scorer.evaluate(
        CARD, L("Charizard 4 Base Set PSA 9", 2200.0, country="US"), FAIR)
    assert o is not None


# --- escopo graded-only (decisao do operador 2026-06-10) -----------------------

def test_graded_only_drops_raw_by_default():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 100.0), FAIR)
    assert o is None


def test_graded_only_keeps_slabs():
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 9", 2200.0), FAIR)
    assert o is not None
    assert o.grade == "PSA 9"


# --- BGS 9.5 / CGC 9.5 -> bucket generico "GRADE 9.5" do PriceCharting --------
# Regressao: o PriceCharting nao tem coluna separada para BGS 9.5 / CGC 9.5,
# so o rotulo generico "Grade 9.5" (chave "GRADE 9.5"). Antes do fix,
# fair.price("BGS 9.5") -> None e a oferta sumia silenciosamente de TODO scan.

FAIR_95 = FairValue(
    prices={"RAW": 338.42, "PSA 9": 3175.04, "PSA 10": 30085.73,
            "GRADE 9.5": 8000.0},
    deltas={"GRADE 9.5": 12.0},
    sales_per_month={"GRADE 9.5": 5.0},
)


def test_bgs_95_uses_generic_grade_95_bucket():
    # Antes do fix: retornava None (some do scan). Agora vira Opportunity.
    # BGS 9.5 justo $8000 (bucket generico); anuncio $4000 -> margem 100%.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set BGS 9.5", 4000.0),
                        FAIR_95)
    assert o is not None
    # A grade REAL exibida continua sendo BGS 9.5 (so o lookup usa o bucket).
    assert o.grade == "BGS 9.5"
    assert o.fair_value == 8000.0
    assert 90 < o.gross_margin_pct < 110
    # Honestidade: nota de que a referencia 9.5 e o bucket generico.
    assert any("bucket generico" in f for f in o.risk_flags)
    # Liquidez/tendencia tambem saem do bucket generico.
    assert o.liquidity_per_month == 5.0
    assert o.trend_delta == 12.0


def test_cgc_95_uses_generic_grade_95_bucket():
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set CGC 9.5", 4000.0),
                        FAIR_95)
    assert o is not None
    assert o.grade == "CGC 9.5"
    assert o.fair_value == 8000.0
    assert any("bucket generico" in f for f in o.risk_flags)


def test_grade_95_without_bucket_still_skipped():
    # Nunca fabricar preco: se "GRADE 9.5" tambem nao existe, mantem o skip.
    fair_no_95 = FairValue(prices={"RAW": 338.42, "PSA 9": 3175.04})
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set BGS 9.5", 4000.0),
                        fair_no_95)
    assert o is None


# --- referencia TCGplayer (tcgcsv) — raw usa TCG como principal (2026-07) ------

from src.tcg_reference import TcgReference  # noqa: E402


def TCG(market=400.0):
    return TcgReference(market_usd=market,
                        product_url="https://www.tcgplayer.com/product/123",
                        group_name="Base Set", sub_type="Holofoil")


def test_raw_uses_tcg_market_as_primary_ref():
    # PC RAW = 338.42; TCG market = 400 -> margem calculada sobre o TCG.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 260.0),
                        FAIR, CFG_RAW, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.ref_kind == "tcgplayer"
    assert o.fair_value == 400.0
    assert o.tcg_market == 400.0
    assert o.tcg_url == "https://www.tcgplayer.com/product/123"
    # PC 338.42 vs TCG 400: divergencia 15% < 40% -> sem flag, segue limpo.
    assert not any("DIVERGENTE" in f for f in o.risk_flags)
    assert o.verdict == "OPORTUNIDADE"


def test_raw_pc_tcg_divergence_flags_and_demotes():
    # PC RAW 700 vs TCG 400 -> divergencia 75% > 40% -> flag + max REVISAR.
    fair = FairValue(prices={"RAW": 700.0, "PSA 9": 3175.04},
                     sales_per_month={"RAW": 60.0})
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 280.0),
                        fair, CFG_RAW, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.ref_kind == "tcgplayer"
    assert o.fair_value == 400.0  # margem sobre o TCG, nao sobre o PC
    assert any("REF RAW DIVERGENTE (PC vs TCG)" in f for f in o.risk_flags)
    assert o.verdict == "REVISAR"


def test_raw_fallback_without_tcg_is_labeled_not_demoted():
    # Sem TCG market: raw segue no PriceCharting, com flag HONESTA visivel.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 230.0),
                        FAIR, CFG_RAW)  # tcg_ref=None
    assert o is not None
    assert o.ref_kind == "pricecharting"
    assert o.fair_value == FAIR.price("RAW")
    assert o.tcg_market is None and o.tcg_url == ""
    assert any("REF: PriceCharting (sem TCG)" in f for f in o.risk_flags)
    # Flag informativa: nao rebaixa o veredito nem zera o score.
    assert o.verdict == "OPORTUNIDADE"
    assert o.score > 0


def test_graded_ref_below_raw_tcg_flags_and_demotes():
    # Justo PSA 9 = 3175 abaixo do market raw TCG 5000 -> ref graded stale.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 9", 2200.0),
                        FAIR, tcg_ref=TCG(5000.0))
    assert o is not None
    assert o.ref_kind == "pricecharting"  # graded segue PriceCharting
    assert o.fair_value == FAIR.price("PSA 9")
    assert any("REF GRADED < RAW TCG" in f for f in o.risk_flags)
    assert o.verdict == "REVISAR"


def test_graded_with_sane_tcg_stays_opportunity():
    # Market raw TCG (400) < justo PSA 9 (3175): sem flag, comportamento igual.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 9", 2200.0),
                        FAIR, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.verdict == "OPORTUNIDADE"
    assert not any(f.startswith("REF") for f in o.risk_flags)
    assert o.tcg_market == 400.0  # registrado pra auditoria mesmo sem flag


def test_raw_without_pc_price_still_works_with_tcg():
    # PriceCharting sem Ungraded, mas TCG tem market: raw ainda e avaliavel.
    fair = FairValue(prices={"PSA 9": 3175.04}, sales_per_month={})
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 260.0),
                        fair, CFG_RAW, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.fair_value == 400.0
    assert o.ref_kind == "tcgplayer"
