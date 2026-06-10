from src import title_parser as tp
from src.models import WatchCard, Listing


def L(title, **kw):
    defaults = dict(item_id="1", title=title, price=100.0, shipping=0.0,
                    currency="USD", buying_option="FIXED_PRICE", condition="",
                    seller_feedback_pct=99.5, seller_feedback_score=500, url="")
    defaults.update(kw)
    return Listing(**defaults)


# --- grade ------------------------------------------------------------------

def test_psa10():
    assert tp.detect_grade("Charizard Base Set 4/102 PSA 10 GEM MINT") == "PSA 10"

def test_psa9_not_95():
    assert tp.detect_grade("Umbreon VMAX PSA 9 Alt Art") == "PSA 9"

def test_psa_9_5_rejected_as_out_of_scope():
    # PSA 9.5 nao existe no escopo; nao pode casar como PSA 9
    assert tp.detect_grade("Card PSA 9.5") is None

def test_bgs_95():
    assert tp.detect_grade("Lugia BGS 9.5 Quad+") == "BGS 9.5"

def test_cgc10():
    assert tp.detect_grade("Pikachu CGC 10 Pristine") == "CGC 10"

def test_psa8_out_of_scope():
    assert tp.detect_grade("Charizard PSA 8") is None

def test_sgc_out_of_scope():
    assert tp.detect_grade("Charizard SGC 10") is None

def test_no_grade_is_raw():
    assert tp.detect_grade("Charizard 4/102 Base Set Holo NM") == "RAW"


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
