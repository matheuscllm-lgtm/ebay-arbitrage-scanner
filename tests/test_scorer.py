"""Scorer no padrao COMC: gate por Desconto%, slab = mediana de vendas EXATAS
(mesma certificadora+nota+variante), raw NM = TCGplayer market, raw LP = vendas
LP, so preco fixo, funil (`stats`) para tudo que nao vira linha."""
from collections import Counter

from src import scorer
from src.models import WatchCard, Listing, FairValue
from src.pc_sales import SalesRef
from src.tcg_reference import TcgReference

PC_URL = "https://www.pricecharting.com/game/pokemon-base-set/charizard-4"
CARD = WatchCard(name="Charizard", set_name="Base Set", number="4",
                 language="EN", pc_url=PC_URL, pokemon="Charizard", pokemon_rank=1)

# Colunas do PriceCharting: SO informacao (tendencia/volume) e fallback raw rotulado.
FAIR = FairValue(
    prices={"RAW": 338.42, "PSA 9": 3175.04, "PSA 10": 30085.73,
            "GRADE 8": 1199.03, "GRADE 9.5": 8000.0},
    deltas={"RAW": -0.62, "PSA 9": 39.13, "PSA 10": 0.0},
    sales_per_month={"RAW": 60.0, "PSA 9": 30.0, "PSA 10": 1.0},
    source_url=PC_URL,
)


def REF(price, n=5, liquidity="ok", window=180, what="PSA 9", column=None):
    return SalesRef(price=price, n_sales=n, window_days=window, liquidity=liquidity,
                    url=PC_URL, label=f"vendas {what} (n={n}, 2026-03..2026-08)",
                    column_price=column)


class FakeRefs:
    """Substitui scanner.CardRefs: mediana por chave de nota + LP."""

    def __init__(self, slab=None, lp=None, available=True, pc_url=PC_URL):
        self._slab = slab or {}
        self._lp = lp
        self.available = available
        self.pc_url = pc_url
        self.calls = []

    def slab(self, grade, variants=frozenset()):
        self.calls.append((grade.key, frozenset(variants)))
        return self._slab.get(grade.key)

    def lp(self, variants=frozenset()):
        self.calls.append(("LP", frozenset(variants)))
        return self._lp


def make_refs(**overrides):
    slab = {
        "PSA 9": REF(3175.04),
        "PSA 10": REF(30085.73, what="PSA 10"),
        "PSA 8": REF(1199.03, what="PSA 8"),
        "BGS 9.5": REF(8000.0, what="BGS 9.5"),
        "CGC 9.5": REF(7000.0, what="CGC 9.5"),
        "SGC 10": REF(20000.0, what="SGC 10"),
        "TAG 10": REF(25000.0, what="TAG 10"),
        "CGC 10 GEM": REF(9000.0, what="CGC 10 Gem Mint"),
        "CGC 10 PRISTINE": REF(40000.0, what="CGC 10 Pristine"),
    }
    slab.update(overrides.pop("slab", {}))
    return FakeRefs(slab=slab, lp=overrides.pop("lp", REF(250.0, n=4, what="LP")),
                    **overrides)


REFS = make_refs()


def L(title, price, **kw):
    defaults = dict(item_id="1", title=title, price=price, shipping=4.5,
                    currency="USD", buying_option="FIXED_PRICE", condition="",
                    seller_feedback_pct=99.8, seller_feedback_score=1200, url="u")
    defaults.update(kw)
    return Listing(**defaults)


def TCG(market=400.0):
    return TcgReference(market_usd=market,
                        product_url="https://www.tcgplayer.com/product/123",
                        group_name="Base Set", sub_type="Holofoil")


# Raw entra por run (--include-raw); nos testes: config explicito.
CFG_RAW = {"graded_only": False}


def ev(title, price, cfg=None, refs=REFS, fair=FAIR, tcg_ref=None, stats=None, **kw):
    return scorer.evaluate(CARD, L(title, price, **kw), fair, cfg, tcg_ref=tcg_ref,
                           refs=refs, stats=stats)


# --- gate por Desconto% e metricas ---------------------------------------------

def test_psa9_discount_above_gate_is_opportunity():
    # mediana PSA 9 $3175.04; anuncio $2200 -> desconto 30.71%, ROI 44.32%
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0)
    assert o is not None
    assert o.grade == "PSA 9" and o.listing_type == "PSA 9"
    assert o.fair_value == 3175.04
    assert o.discount_pct == 30.71 and o.gross_margin_pct == 44.32
    assert o.spread_usd == 975.04
    assert o.ref_source == "pricecharting-sales"
    assert o.ref_label.startswith("vendas PSA 9 (n=5")
    assert o.ref_n_sales == 5 and o.ref_liquidity == "ok"
    assert o.pc_url == PC_URL
    assert o.verdict == "OPORTUNIDADE"
    assert o.reasons == []


def test_below_discount_gate_not_reported_but_counted():
    # $2800 -> desconto 11.8% < 20 -> None (funil), nem linha rejeitada
    stats = Counter()
    assert ev("Charizard 4/102 Base Set PSA 9", 2800.0, stats=stats) is None
    assert stats["below_discount"] == 1
    # gate ajustavel por run: --min-discount 10 -> vira linha
    o = ev("Charizard 4/102 Base Set PSA 9", 2800.0, cfg={"min_discount_percent": 10})
    assert o is not None and o.discount_pct == 11.81


def test_roi_too_good_is_suspicious():
    # PSA 10 mediana $30k; anuncio $5k -> ROI 500% -> SUSPEITO
    o = ev("Charizard 4 Base Set PSA 10", 5000.0)
    assert o is not None
    assert o.verdict == "SUSPEITO"
    assert any("ROI bruto" in f for f in o.risk_flags)


def test_metrics_never_called_profit():
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0)
    assert not any("lucro" in f.lower() for f in o.risk_flags)


# --- triagem (funil) -------------------------------------------------------------

def test_auction_skipped_fixed_price_only():
    stats = Counter()
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, buying_option="AUCTION", stats=stats)
    assert o is None and stats["skip_not_fixed_price"] == 1


def test_auction_allowed_when_config_disables_fixed_price_only():
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, buying_option="AUCTION",
           cfg={"fixed_price_only": False})
    assert o is not None and o.verdict == "REVISAR"
    assert any("LEILAO" in f for f in o.risk_flags)


def test_below_price_floor_ignored():
    stats = Counter()
    assert ev("Charizard 4 Base Set PSA 9", 9.0, stats=stats) is None
    assert stats["skip_price_floor"] == 1


def test_wrong_card_ignored():
    stats = Counter()
    assert ev("Blastoise 2/102 Base Set PSA 9", 1000.0, stats=stats) is None
    assert stats["skip_no_match"] == 1


def test_non_us_listing_dropped_us_kept():
    stats = Counter()
    assert ev("Charizard 4 Base Set PSA 9", 2200.0, country="JP", stats=stats) is None
    assert stats["skip_country"] == 1
    assert ev("Charizard 4 Base Set PSA 9", 2200.0, country="US") is not None


def test_graded_only_drops_raw_by_default_and_keeps_slabs():
    stats = Counter()
    assert ev("Charizard 4/102 Base Set Holo NM", 100.0, stats=stats) is None
    assert stats["skip_raw"] == 1
    assert ev("Charizard 4 Base Set PSA 9", 2200.0).grade == "PSA 9"


def test_raw_without_nm_or_lp_is_skipped_not_row():
    stats = Counter()
    assert ev("Charizard 4/102 Base Set Holo", 200.0, cfg=CFG_RAW, stats=stats) is None
    assert stats["skip_condition"] == 1
    # "NM/LP" e ambiguo: nem NM nem LP
    assert ev("Charizard 4/102 Base Set Holo NM/LP", 200.0, cfg=CFG_RAW, stats=stats) is None
    assert stats["skip_condition"] == 2


def test_out_of_scope_and_unknown_grader_counted():
    stats = Counter()
    assert ev("Charizard 4/102 Base Set PSA 7", 500.0, stats=stats) is None
    assert ev("Charizard 4/102 Base Set ACE 10", 500.0, stats=stats) is None
    assert stats["skip_grade_out_of_scope"] == 2


def test_ambiguous_grade_counted_not_row():
    stats = Counter()
    o = ev("Charizard 4/102 Holo BGS 8.5 NM-MINT FRESH GRADE PSA 9", 1000.0, stats=stats)
    assert o is None and stats["skip_grade_ambiguous"] == 1


def test_allowed_grades_filter_silent():
    stats = Counter()
    cfg = {"allowed_grades": ["PSA 10"]}
    assert ev("Charizard 4/102 Base Set PSA 9", 2200.0, cfg=cfg, stats=stats) is None
    assert stats["skip_grade_filtered"] == 1
    assert ev("Charizard 4 Base Set PSA 10", 5000.0, cfg=cfg) is not None
    # RAW so entra na lista junto com --include-raw
    cfg_raw = {"allowed_grades": ["PSA 10"], "graded_only": False}
    assert ev("Charizard 4/102 Base Set Holo NM", 260.0, cfg=cfg_raw,
              tcg_ref=TCG(), stats=stats) is None
    assert stats["skip_grade_filtered"] == 2
    cfg_raw2 = {"allowed_grades": ["RAW", "PSA 10"], "graded_only": False}
    assert ev("Charizard 4/102 Base Set Holo NM", 260.0, cfg=cfg_raw2, tcg_ref=TCG()) is not None


# --- slabs: mediana de vendas EXATAS; coluna/bucket generico nunca -------------

def test_slab_without_comparable_sales_is_not_evaluated_even_with_column():
    # FAIR tem coluna "GRADE 9.5" e "PSA 9" -- irrelevante: sem vendas, sem linha.
    refs = FakeRefs(slab={})
    stats = Counter()
    assert ev("Charizard 4/102 Base Set BGS 9.5", 4000.0, refs=refs, stats=stats) is None
    assert ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs, stats=stats) is None
    assert stats["slab_no_reference"] == 2


def test_bgs_95_and_cgc_95_use_their_own_sales():
    o = ev("Charizard 4/102 Base Set BGS 9.5", 4000.0)
    assert o is not None and o.grade == "BGS 9.5" and o.fair_value == 8000.0
    o2 = ev("Charizard 4/102 Base Set CGC 9.5", 4000.0)
    assert o2 is not None and o2.grade == "CGC 9.5" and o2.fair_value == 7000.0
    assert not any("bucket" in f for f in o.risk_flags + o2.risk_flags)


def test_cgc10_gem_and_pristine_are_distinct_references():
    gem = ev("Charizard 4/102 Base Set CGC 10", 5000.0)
    assert gem.grade == "CGC 10 GEM" and gem.fair_value == 9000.0
    assert gem.listing_type == "CGC 10 Gem Mint"
    pristine = ev("Charizard 4/102 Base Set CGC 10 Pristine", 20000.0)
    assert pristine.grade == "CGC 10 PRISTINE" and pristine.fair_value == 40000.0


def test_expanded_graders_accepted():
    assert ev("Charizard 4/102 Base Set PSA 8", 700.0).grade == "PSA 8"
    assert ev("Charizard 4/102 Base Set SGC 10", 12000.0).grade == "SGC 10"
    assert ev("Charizard 4/102 Base Set TAG 10", 15000.0).grade == "TAG 10"


def test_thin_sales_is_review_with_reason():
    refs = make_refs(slab={"PSA 9": REF(3175.04, n=2, liquidity="thin", window=365)})
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs)
    assert o is not None
    assert o.verdict == "REVISAR"
    assert o.reasons == ["vendas<3(n=2)"]
    assert o.liquidity_tier == "D"


def test_low_liquidity_is_note_not_status():
    refs = make_refs(slab={"PSA 9": REF(3175.04, n=4, liquidity="low", window=365)})
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs)
    assert o.verdict == "OPORTUNIDADE" and o.ref_liquidity == "low"
    assert o.liquidity_tier == "C"


def test_column_far_from_sales_is_review():
    refs = make_refs(slab={"PSA 9": REF(3175.04, column=5000.0)})
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs)
    assert o.verdict == "REVISAR" and o.reasons == ["coluna÷vendas(5000.00)"]
    assert o.ref_column_price == 5000.0
    assert o.fair_value == 3175.04  # a coluna NUNCA e a referencia


def test_column_close_to_sales_no_reason():
    refs = make_refs(slab={"PSA 9": REF(3175.04, column=3300.0)})
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs)
    assert o.verdict == "OPORTUNIDADE" and o.reasons == []


def test_variants_of_listing_are_passed_to_reference():
    refs = make_refs()
    ev("Charizard 4/102 Base Set 1st Edition PSA 9", 2200.0, refs=refs)
    assert refs.calls[-1] == ("PSA 9", frozenset({"1st"}))


def test_refs_unavailable_skips_slab_but_raw_nm_still_works():
    refs = FakeRefs(available=False)
    stats = Counter()
    assert ev("Charizard 4/102 Base Set PSA 9", 2200.0, refs=refs, stats=stats) is None
    assert stats["ref_unavailable"] == 1
    o = ev("Charizard 4/102 Base Set Holo NM", 260.0, cfg=CFG_RAW, refs=refs, tcg_ref=TCG())
    assert o is not None and o.ref_source == "tcgplayer"


# --- fraude grade x condicao -----------------------------------------------------

def test_grade_vs_condition_fraud():
    o = ev("Charizard 4/102 Base Set Holo PSA 10", 1800.0,
           condition="Ungraded - Like New or better", seller_feedback_score=0)
    assert o is not None and o.verdict == "REJEITADO"
    assert any("FRAUDE" in f for f in o.risk_flags)


def test_graded_condition_consistent_ok():
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, condition="Graded")
    assert o is not None and not any("FRAUDE" in f for f in o.risk_flags)


def test_raw_with_ungraded_condition_ok():
    o = ev("Charizard 4/102 Base Set Holo NM", 260.0, cfg=CFG_RAW,
           condition="Ungraded - Near Mint or better", tcg_ref=TCG())
    assert o is not None and not any("identidade" in f for f in o.risk_flags)


# --- raw NM: TCGplayer market principal, PriceCharting cross-check -------------

def test_raw_uses_tcg_market_as_primary_ref():
    o = ev("Charizard 4/102 Base Set Holo NM", 260.0, cfg=CFG_RAW, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.ref_source == "tcgplayer" and o.ref_kind == "tcgplayer"
    assert o.fair_value == 400.0 and o.condition == "NM" and o.listing_type == "Raw NM"
    assert o.ref_label == "TCG market"
    assert o.tcg_url == "https://www.tcgplayer.com/product/123"
    assert o.discount_pct == 35.0
    assert not any("DIVERGENTE" in f for f in o.risk_flags)
    assert o.verdict == "OPORTUNIDADE"
    assert o.spread_psa10_pct > 8000


def test_raw_pc_tcg_divergence_flags_and_demotes():
    fair = FairValue(prices={"RAW": 700.0}, sales_per_month={"RAW": 60.0})
    o = ev("Charizard 4/102 Base Set Holo NM", 280.0, cfg=CFG_RAW, fair=fair,
           tcg_ref=TCG(400.0))
    assert o.fair_value == 400.0
    assert any("REF RAW DIVERGENTE (PC vs TCG)" in f for f in o.risk_flags)
    assert o.verdict == "REVISAR" and "ref-divergente" in o.reasons


def test_raw_fallback_without_tcg_is_labeled_not_demoted():
    o = ev("Charizard 4/102 Base Set Holo NM", 230.0, cfg=CFG_RAW)
    assert o.ref_source == "pricecharting" and o.ref_label == "PC Ungraded (sem TCG)"
    assert o.fair_value == FAIR.price("RAW")
    assert any("REF: PriceCharting (sem TCG)" in f for f in o.risk_flags)
    assert o.verdict == "OPORTUNIDADE" and o.score > 0


def test_raw_without_any_reference_is_counted():
    stats = Counter()
    fair = FairValue(prices={"PSA 9": 3175.04})
    assert ev("Charizard 4/102 Base Set Holo NM", 230.0, cfg=CFG_RAW, fair=fair,
              stats=stats) is None
    assert stats["raw_no_reference"] == 1


def test_graded_ref_below_raw_tcg_flags_and_demotes():
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, tcg_ref=TCG(5000.0))
    assert o.ref_source == "pricecharting-sales"
    assert any("REF GRADED < RAW TCG" in f for f in o.risk_flags)
    assert o.verdict == "REVISAR"


def test_graded_with_sane_tcg_stays_opportunity():
    o = ev("Charizard 4/102 Base Set PSA 9", 2200.0, tcg_ref=TCG(400.0))
    assert o.verdict == "OPORTUNIDADE"
    assert not any(f.startswith("REF") for f in o.risk_flags)
    assert o.tcg_market == 400.0


# --- raw LP: pre-filtro pela referencia NM, depois a SUA referencia (vendas LP) --

CFG_LP = {"graded_only": False, "min_discount_percent": 20}


def test_lp_uses_lp_sales_never_nm():
    # NM ref (TCG) = 400 -> teto 320; anuncio LP $150 passa; ref LP = 250 -> desconto 40%
    o = ev("Charizard 4/102 Base Set Holo LP", 150.0, cfg=CFG_LP, tcg_ref=TCG(400.0))
    assert o is not None
    assert o.condition == "LP" and o.listing_type == "Raw LP"
    assert o.fair_value == 250.0 and o.ref_source == "pricecharting-sales-lp"
    assert o.discount_pct == 40.0
    assert o.ref_label.startswith("vendas LP (n=4")


def test_lp_from_ebay_condition_field():
    o = ev("Charizard 4/102 Base Set Holo", 150.0, cfg=CFG_LP, tcg_ref=TCG(400.0),
           condition="Ungraded - Lightly Played (Excellent)")
    assert o is not None and o.condition == "LP"


def test_lp_prefilter_uses_nm_reference_as_ceiling():
    stats = Counter()
    # 330 > 400 x (1 - 0.20) = 320 -> eliminado sem consultar vendas LP
    refs = make_refs()
    assert ev("Charizard 4/102 Base Set Holo LP", 330.0, cfg=CFG_LP, refs=refs,
              tcg_ref=TCG(400.0), stats=stats) is None
    assert stats["lp_prefilter"] == 1
    assert ("LP", frozenset()) not in refs.calls


def test_lp_without_nm_reference_goes_straight_to_lp_sales():
    # Sem referencia NM nao ha teto para o pre-filtro: a comparacao final continua
    # sendo SO contra vendas LP (review Codex 2026-09-03).
    stats = Counter()
    fair = FairValue(prices={"PSA 9": 3175.04})
    o = ev("Charizard 4/102 Base Set Holo LP", 150.0, cfg=CFG_LP, fair=fair, stats=stats)
    assert o is not None and o.fair_value == 250.0 and o.ref_source == "pricecharting-sales-lp"
    assert stats["lp_no_nm_prefilter"] == 1


def test_price_zero_never_evaluated_even_with_floor_zero():
    stats = Counter()
    assert ev("Charizard 4/102 Base Set PSA 9", 0.0, cfg={"min_price_usd": 0}, stats=stats) is None
    assert stats["skip_price_floor"] == 1


def test_lp_without_three_lp_sales_counted():
    stats = Counter()
    refs = make_refs(lp=None)
    assert ev("Charizard 4/102 Base Set Holo LP", 150.0, cfg=CFG_LP, refs=refs,
              tcg_ref=TCG(400.0), stats=stats) is None
    assert stats["lp_no_reference"] == 1


def test_lp_disabled_by_config():
    stats = Counter()
    assert ev("Charizard 4/102 Base Set Holo LP", 150.0,
              cfg=dict(CFG_LP, lp_with_reference=False), tcg_ref=TCG(400.0),
              stats=stats) is None
    assert stats["skip_condition"] == 1


# --- modo confiavel + trust score ---------------------------------------------------

def test_trust_score_layers():
    weak = L("t", 100.0, seller_feedback_score=0, seller_feedback_pct=0.0)
    strong = L("t", 100.0, seller_feedback_score=5000, seller_feedback_pct=99.9)
    armored = L("t", 100.0, seller_feedback_score=5000, seller_feedback_pct=99.9,
                authenticity_guarantee=True, top_rated=True)
    assert scorer.trust_score(weak) <= 15
    assert scorer.trust_score(strong) >= 80
    assert scorer.trust_score(armored) == 100.0


def test_trusted_mode_filters_new_seller_and_huge_roi_and_rejected():
    cfg = {"trusted_mode": True}
    stats = Counter()
    assert ev("Charizard 4 Base Set PSA 9", 2200.0, cfg=cfg, seller_feedback_score=3,
              stats=stats) is None
    assert ev("Charizard 4 Base Set PSA 9", 220.0, cfg=cfg, stats=stats) is None  # ROI 1343%
    assert ev("Charizard 4/102 Base Set Holo PSA 10", 1800.0, cfg=cfg,
              condition="Ungraded", stats=stats) is None  # fraude = rejeitado
    assert stats["trusted_filtered"] == 3


def test_trusted_mode_keeps_good_seller_healthy_margin():
    o = ev("Charizard 4 Base Set PSA 9", 2200.0, cfg={"trusted_mode": True},
           seller_feedback_score=850, seller_feedback_pct=99.7, top_rated=True)
    assert o is not None and o.verdict == "OPORTUNIDADE" and o.trust_score >= 75


def test_trusted_mode_threshold_boundary():
    cfg = {"trusted_mode": True}
    title = "Charizard 4 Base Set PSA 9"
    assert ev(title, 2200.0, cfg=cfg, seller_feedback_score=50, seller_feedback_pct=98.0) is not None
    assert ev(title, 2200.0, cfg=cfg, seller_feedback_score=49, seller_feedback_pct=98.0) is None
    assert ev(title, 2200.0, cfg=cfg, seller_feedback_score=50, seller_feedback_pct=97.9) is None
