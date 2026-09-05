from dataclasses import replace
import pytest
from src.slab_strategy import identity_matches, discovery_query, evaluate, policy_config
from tests.test_slab_strategy import CARD, listing, sales, refs


@pytest.mark.parametrize('set_name,title,expected', [
    ('SV10: Destined Rivals', 'Team Rockets Mewtwo ex #231 Destined Rivals English PSA 10', True),
    ('SV10: Destined Rivals', 'Team Rocket’s Mewtwo ex #231 Destined Rivals English PSA 10', True),
    ('SV10: Destined Rivals', 'Team Rockets Mewtwo ex #232 Destined Rivals English PSA 10', False),
    ('SV10: Destined Rivals', 'Team Rockets Mewtwo ex #231 Temporal Forces English PSA 10', False),
    ('SWSH09: Brilliant Stars', 'Team Rockets Mewtwo ex #231 Brilliant Stars Trainer Gallery English PSA 10', False),
    ('Hidden Fates: Shiny Vault', 'Team Rockets Mewtwo ex #231 Hidden Fates English PSA 10', False),
])
def test_codes_typography_and_distinct_subsets(set_name, title, expected):
    card = replace(CARD, name="Team Rocket's Mewtwo ex", set_name=set_name, number='231')
    assert identity_matches(card, title) is expected


def test_normalization_cannot_strip_card_suffix_or_merge_base_sets():
    card = replace(CARD, name='Mew', number='4')
    assert not identity_matches(card, 'Mewtwo #4 Base Set English PSA 10')
    assert not identity_matches(card, 'Mew ex #4 Base Set English PSA 10')
    assert not identity_matches(card, 'Mew #4 Base Set 2 English PSA 10')
    assert not identity_matches(card, 'Mew #4 Sword & Shield Base Set English PSA 10')


def test_lvx_typography_is_same_card():
    card = replace(CARD, name='Dialga LV.X', number='105', set_name='Great Encounters')
    assert identity_matches(card, 'Dialga LVX #105 Great Encounters English PSA 8')
    assert not identity_matches(replace(card, name='Dialga'), 'Dialga LV.X #105 Great Encounters English PSA 8')


def test_production_evidence_accepts_label_without_catalog_code():
    card = replace(CARD, set_name='SV05: Temporal Forces', name='Gengar ex', number='193')
    title = 'Gengar ex #193 Temporal Forces English PSA 10'
    pool = sales(price=200)
    for sale in pool:
        sale['title'] = title
    o = evaluate(card, listing(price=50, title=title, item_aspects={'Set':['Temporal Forces']}),
                 config=policy_config(), refs=refs(pool))
    assert o.verdict == 'APROVAR'
    assert o.strategy['psa_evidence']['n_used'] == 3
    assert discovery_query(card) == 'pokemon Gengar ex 193 Temporal Forces'
