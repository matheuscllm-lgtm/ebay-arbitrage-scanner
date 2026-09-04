from src import title_parser as tp
from src.models import WatchCard, Listing


def L(title, **kw):
    defaults = dict(item_id="1", title=title, price=100.0, shipping=0.0,
                    currency="USD", buying_option="FIXED_PRICE", condition="",
                    seller_feedback_pct=99.5, seller_feedback_score=500, url="")
    defaults.update(kw)
    return Listing(**defaults)


# --- grade (leitura em src/grading.py; aqui so a ponte) -----------------------

def test_psa10():
    assert tp.detect_grade("Charizard Base Set 4/102 PSA 10 GEM MINT") == "PSA 10"

def test_psa9_not_95():
    assert tp.detect_grade("Umbreon VMAX PSA 9 Alt Art") == "PSA 9"

def test_psa_9_5_rejected_as_out_of_scope():
    # PSA 9.5 nao existe; nao pode casar como PSA 9
    assert tp.detect_grade("Card PSA 9.5") is None

def test_bgs_95():
    assert tp.detect_grade("Lugia BGS 9.5 Quad+") == "BGS 9.5"

def test_cgc10_pristine_vs_gem():
    assert tp.detect_grade("Pikachu CGC 10 Pristine") == "CGC 10 PRISTINE"
    assert tp.detect_grade("Pikachu CGC 10") == "CGC 10 GEM"

def test_bgs10_black_label():
    assert tp.detect_grade("Charizard BGS 10 Black Label") == "BGS 10 BLACK"
    assert tp.detect_grade("Black Kyurem BGS 10") == "BGS 10"

def test_psa8_sgc_tag_now_in_scope():
    assert tp.detect_grade("Charizard PSA 8") == "PSA 8"
    assert tp.detect_grade("Charizard SGC 10") == "SGC 10"
    assert tp.detect_grade("Charizard TAG 9.5") == "TAG 9.5"

def test_out_of_allowlist_is_none():
    assert tp.detect_grade("Charizard PSA 7") is None
    assert tp.detect_grade("Charizard ACE 10") is None

def test_no_grade_is_raw():
    assert tp.detect_grade("Charizard 4/102 Base Set Holo NM") == "RAW"

def test_known_grades_is_the_allowlist():
    assert "PSA 8" in tp.KNOWN_GRADES and "TAG 10" in tp.KNOWN_GRADES


# --- condicao NM (invariante dura) -------------------------------------------

def test_nm_ok():
    assert tp.is_nm_acceptable("Charizard Holo NM 4/102")

def test_near_mint_ok():
    assert tp.is_nm_acceptable("Charizard Near Mint Base Set")

def test_nm_lp_combo_rejected():
    # 'NM/LP' tem sinal de condicao inferior -> rejeita (match conservador)
    assert not tp.is_nm_acceptable("Charizard NM/LP Base Set")

def test_played_rejected():
    assert not tp.is_nm_acceptable("Charizard Heavily Played")

def test_no_condition_rejected():
    assert not tp.is_nm_acceptable("Charizard 4/102 Base Set Holo")

def test_condition_from_ebay_field():
    assert tp.is_nm_acceptable("Charizard 4/102", "Near Mint or Better")


# --- condicao LP explicita (so entao busca a referencia LP) -------------------

def test_lp_explicit_in_title():
    assert tp.is_lp("Charizard 4/102 Base Set Holo LP")
    assert tp.is_lp("Charizard 4/102 Lightly Played")

def test_lp_from_ebay_condition_field():
    assert tp.is_lp("Charizard 4/102 Base Set Holo", "Ungraded - Lightly Played (Excellent)")

def test_nm_lp_combo_is_not_lp():
    assert not tp.is_lp("Charizard NM/LP Base Set")
    assert not tp.is_lp("Charizard Near Mint LP")

def test_lp_with_worse_condition_is_not_lp():
    assert not tp.is_lp("Charizard LP/MP Base Set")
    assert not tp.is_lp("Charizard Lightly Played crease")

def test_no_condition_is_not_lp():
    assert not tp.is_lp("Charizard 4/102 Base Set Holo")


# --- idioma ------------------------------------------------------------------

def test_japanese():
    assert tp.detect_language("Charizard Japanese Base Set") == "JP"

def test_korean_out_of_scope():
    assert tp.detect_language("Charizard Korean Base Set") == "OTHER"

def test_default_en():
    assert tp.detect_language("Charizard Base Set") == "EN"


# --- risco ---------------------------------------------------------------------

def test_proxy_flag():
    flags = tp.risk_flags("Charizard PROXY custom card")
    assert any(f.startswith("REJEITAR") for f in flags)

def test_lot_flag():
    flags = tp.risk_flags("Pokemon card lot 50x charizard")
    assert any(f.startswith("LOTE") for f in flags)

def test_auction_flag():
    flags = tp.risk_flags("Charizard PSA 10", L("t", buying_option="AUCTION"))
    assert any("LEILAO" in f for f in flags)

def test_low_feedback_seller():
    flags = tp.risk_flags("Charizard PSA 10", L("t", seller_feedback_score=3))
    assert any("VENDEDOR" in f for f in flags)

def test_clean_listing_no_flags():
    assert tp.risk_flags("Charizard PSA 10 Base Set", L("t")) == []


# --- identidade da carta -------------------------------------------------------

CARD = WatchCard(name="Umbreon VMAX", set_name="Evolving Skies", number="215",
                 language="EN", pc_url="")

def test_match_with_number():
    assert tp.card_matches_title(CARD, "Umbreon VMAX 215/203 Evolving Skies PSA 10")

def test_no_match_wrong_number():
    assert not tp.card_matches_title(CARD, "Umbreon VMAX 095/203 Evolving Skies")

def test_no_match_wrong_card():
    assert not tp.card_matches_title(CARD, "Espeon VMAX 270/203 PSA 10")


# --- exclude_keywords (falso positivo Celebrations, achado no 1o scan real) ---

ZARD = WatchCard(name="Charizard", set_name="Base Set", number="4",
                 language="EN", pc_url="",
                 exclude_keywords=["celebrations", "classic collection",
                                   "classic coll"])

def test_celebrations_reprint_excluded():
    assert not tp.card_matches_title(
        ZARD, "Charizard PSA 9 Celebrations Classic 4/102 Holo Base Set 2021")

def test_original_still_matches():
    assert tp.card_matches_title(
        ZARD, "1999 Pokemon Base Set Charizard 4/102 Holo PSA 9")

def test_poker_card_rejected():
    flags = tp.risk_flags("1996 Charizard #006 Playing Poker Green Back 4 Clubs")
    assert any(f.startswith("REJEITAR") for f in flags)

def test_accessory_case_rejected():
    flags = tp.risk_flags("POKEMON TCG EXTENDED ART ACRYLIC CASE CARD UMBREON VMAX 215")
    assert any(f.startswith("REJEITAR") for f in flags)

def test_ambiguous_grade_detected():
    assert tp.grade_is_ambiguous(
        "Charizard 4/102 Holo BGS 8.5 NM-MINT FRESH GRADE PSA 9", "PSA 9")

def test_clean_grade_not_ambiguous():
    assert not tp.grade_is_ambiguous("Charizard 4/102 Holo PSA 9", "PSA 9")


def test_gold_foil_and_plated_fakes_rejected():
    # Caso REAL (smoke 2026-09-03): "Charizard 120HP Gold Foil card 4/102 Near
    # Mint" a US$65 saia como raw NM com ROI 463% -- e carta de metal/falsa.
    for title in ("Pokemon Charizard 120HP Gold Foil card 4/102 Near Mint",
                  "Charizard 4/102 24k gold plated card", "Charizard gold foil NM"):
        assert any(f.startswith("REJEITAR") for f in tp.risk_flags(title)), title
    assert tp.risk_flags("Charizard 4/102 Base Set Holo NM") == []


def test_card_number_never_matches_the_grade():
    # Review Codex 2026-09-03: carta nº 10 casava "Mewtwo VSTAR PSA 10".
    mewtwo = WatchCard(name="Mewtwo VSTAR", set_name="Pokemon GO", number="10",
                       language="EN", pc_url="")
    assert not tp.card_matches_title(mewtwo, "Mewtwo VSTAR PSA 10 Pokemon GO")
    assert not tp.card_matches_title(mewtwo, "Mewtwo VSTAR CGC 10 Pristine")
    assert tp.card_matches_title(mewtwo, "Mewtwo VSTAR 010/078 Pokemon GO PSA 10")
    assert tp.card_matches_title(mewtwo, "Mewtwo VSTAR #10 PSA 9")
    nine = WatchCard(name="Blastoise", set_name="Base Set", number="9", language="EN", pc_url="")
    assert not tp.card_matches_title(nine, "Blastoise 2/102 PSA 9")


def test_reject_jumbo_oversized_and_metal_foil():
    # Diagnostico 2026-09-04: um jumbo (carta grande, produto diferente) chegou a
    # OPORTUNIDADE medido contra a referencia da carta normal; e "Gold Metal Foil"
    # (carta de metal, falsa) escapou porque so havia "gold foil"/"metal card".
    for t in ("Dragonite EX 72/108 Jumbo - Oversized XY Evolutions Promos Holo NM",
              "Jumbo Oversized Charizard EX Promo Card 11/106 Flashfire 2014 NM",
              "Charizard GX Gold Metal Foil Secret Rare 150/147 Burning Shadows NM",
              "Pokemon Gold Metal Card Lugia Neo Genesis 9/111"):
        assert tp._REJECT_KEYWORDS.search(t), t
    # carta de verdade nao pode ser rejeitada por essas palavras
    for t in ("Charizard 4/102 Base Set Holo NM", "Umbreon VMAX 215/203 Evolving Skies",
              "Metagross ex 141/165 151 NM"):
        assert not tp._REJECT_KEYWORDS.search(t), t
