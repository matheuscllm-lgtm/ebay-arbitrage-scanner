"""Regression cases from the final review. Prices here are synthetic, never live evidence."""
from dataclasses import replace
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
import main
from src import scanner, report, ebay_api
from src.models import FairValue
from src.slab_strategy import evaluate, policy_config, reference_sales, identity_matches, language
from src.policy_validation import PolicyError, pending_config
from src.grading import Grade
from tests.test_slab_strategy import CARD, listing, sales, refs, cfg


def current_config():
    c = policy_config()
    p = c['slab_strategy']
    p['costs'].update(comc_processing_usd=0, comc_storage_usd=0,
                      selling_fee_percent=0, cashout_fee_percent=0)
    p['evidence']['max_dispersion_percent'] = 30
    return c


def test_delegated_defaults_are_complete_and_do_not_stack_bgs_premiums():
    c = policy_config()
    assert pending_config(c) == []
    assert c['slab_strategy']['graders']['BGS']['combine_9_5_premium'] is False
    o = evaluate(CARD, listing('BGS 9.5', price=105.01), config=c,
                 refs=refs(sales('PSA 9'), sales('BGS 9.5', 200, start=200)))
    assert o.strategy['comparison_cap'] == 105
    assert o.verdict == 'REJEITAR' and 'preco-acima-do-limite-BGS' in o.reasons


@pytest.mark.parametrize('low,verdict', [(80, 'APROVAR'), (79.99, 'REVISAR')])
def test_default_dispersion_boundary_and_full_comc_costs(low, verdict):
    pool = sales()
    for sale, price in zip(pool, (low, 100, 110)):
        sale['price'] = price
    o = evaluate(CARD, listing(price=50), config=policy_config(), refs=refs(pool))
    assert o.verdict == verdict
    assert o.strategy['profit_estimate'] > 0
    assert o.strategy['costs']['comc_storage_usd'] > 0


@pytest.mark.parametrize('price,reference,expected', [
    (950, 1000, 'REJEITAR'),       # exactly $40 profit, <30% discount
    (949.99, 1000, 'APROVAR'),     # profit route alone; legacy 20% must not reject
    (70, 100, 'REJEITAR'),         # exactly 30% discount; profit only $20
    (69.99, 100, 'APROVAR'),       # discount route alone
    (89.99, 100, 'REJEITAR'),      # neither route
])
def test_profit_or_discount_strict_boundaries(price, reference, expected):
    o = evaluate(CARD, listing(price=price), config=current_config(), refs=refs(sales(price=reference)))
    assert o.verdict == expected
    assert o.strategy['investment_total'] == price + 10


def test_discount_cannot_approve_loss_or_missing_costs():
    c = current_config()
    pool = refs(sales(), sales('TAG 10', 50, start=200))
    o = evaluate(CARD, listing('TAG 10', price=60), config=c, refs=pool)
    assert o.verdict == 'REJEITAR' and 'lucro-nao-positivo' in o.reasons
    c['slab_strategy']['costs']['cashout_fee_percent'] = None
    o = evaluate(CARD, listing(price=60), config=c, refs=refs(sales()))
    assert o.verdict == 'REVISAR' and o.strategy['profit_estimate'] is None


@pytest.mark.parametrize('grade,price,ref,resale,cap,expected', [
    ('CGC 10', 40, 100, 100, 40, 'APROVAR'),
    ('CGC 10', 40.01, 100, 100, 40, 'REJEITAR'),
    ('CGC 9.5', 42, 100, 120, 42, 'APROVAR'),
    ('CGC 9.5', 42.01, 100, 120, 42, 'REJEITAR'),
    ('BGS 10', 105, 100, 200, 105, 'APROVAR'),
    ('BGS 10', 105.01, 100, 200, 105, 'REJEITAR'),
    ('TAG 10', 100, 100, 200, 100, 'APROVAR'),
    ('TAG 10', 100.01, 100, 200, 100, 'REJEITAR'),
])
def test_grader_caps_independent_of_profit(grade, price, ref, resale, cap, expected):
    psa_grade = 'PSA 9' if '9.5' in grade else 'PSA 10'
    o = evaluate(CARD, listing(grade, price=price), config=current_config(),
                 refs=refs(sales(psa_grade, ref), sales(grade, resale, start=200)))
    assert o.strategy['comparison_cap'] == cap
    assert o.verdict == expected


@pytest.mark.parametrize('grade', ['SGC 10', 'ACE 10', 'PSA 9.5'])
def test_out_of_scope_is_rejected_even_without_config(grade):
    assert evaluate(CARD, listing(grade), refs=refs()).verdict == 'REJEITAR'


@pytest.mark.parametrize('title', ['Chinese', 'Chinese English', 'Simplified Chinese Traditional Chinese'])
def test_chinese_region_is_required(title):
    assert language(title) is None


def test_regions_never_mix():
    c = replace(CARD, language='ZH-HANS')
    o = evaluate(c, listing(price=60, title='Charizard Base Set 4/102 Simplified Chinese PSA 10'),
                 config=current_config(), refs=refs(sales(lang='Traditional Chinese')))
    assert o.verdict == 'REVISAR' and o.strategy['psa_reference_original'] is None


@pytest.mark.parametrize('title', ['Mewtwo Base Set #4 English PSA 10', 'Mew ex Base Set #4 English PSA 10'])
def test_name_and_suffix_not_substrings(title):
    assert not identity_matches(replace(CARD, name='Mew', number='4'), title)


def test_prefixed_denominator_and_conflicting_fraction():
    c = replace(CARD, number='SV49/SV94')
    assert not identity_matches(c, 'Charizard Base Set SV49/SV95 English PSA 10')
    assert not identity_matches(CARD, 'Charizard Base Set 4/102 and 4/25 English PSA 10')


def test_median_preserves_subcent_precision_for_decisions():
    pool = sales(n=4)
    for row, price in zip(pool, ['100.00', '100.00', '100.01', '100.01']):
        row['price'] = price
    ref = reference_sales(CARD, refs(pool), Grade('PSA', 10), frozenset(), current_config()['slab_strategy'])
    assert ref['price_exact'] == '100.005'
    c = current_config()
    c['slab_strategy']['economics']['min_profit_usd'] = 999
    # Exact discount is above 30%; rounding the median first would reject.
    o = evaluate(CARD, listing(price=70), config=c, refs=refs(pool))
    assert o.verdict == 'APROVAR'


@pytest.mark.parametrize('bad', ['PSA 10 OC', 'PSA 10 potential', 'PSA 10 Offer Accepted'])
def test_unverified_sale_price_or_grade_excluded(bad):
    o = evaluate(CARD, listing(price=60), config=current_config(), refs=refs(sales(bad)))
    assert o.verdict == 'REVISAR'
    assert o.strategy['psa_evidence']['excluded_counts']['oferta-lote-ou-certificacao-incerta'] == 3


@pytest.mark.parametrize('grade', ['BGS 10 Black Label', 'CGC 10 Pristine'])
def test_special_category_requires_its_own_rule(grade):
    o = evaluate(CARD, listing(grade, price=35), config=current_config(), refs=refs(sales(), sales(grade, 100, start=200)))
    assert o.verdict == 'REVISAR' and 'categoria-especial-sem-regra' in o.reasons


@pytest.mark.parametrize('section,key,value', [
    ('costs', 'coverage_confirmed', 'false'),
    ('costs', 'cashout_fee_percent', float('nan')),
    ('costs', 'selling_fee_percent', -1),
    ('evidence', 'windows_days', []),
    ('evidence', 'windows_days', [365, 180]),
    ('evidence', 'min_sales', 0),
    ('evidence', 'median_sample_limit', 2),
    ('economics', 'gate_mode', 'typo'),
])
def test_bad_configuration_stops_before_any_scan(section, key, value):
    c = current_config(); c['slab_strategy'][section][key] = value
    with pytest.raises(PolicyError):
        policy_config(c)


def test_missing_config_file_does_not_silently_use_defaults(tmp_path):
    with pytest.raises(ValueError, match='não encontrada'):
        main._load_config(tmp_path/'typo.yaml')


def test_atomic_report_preserves_previous_on_nonfinite(tmp_path):
    path = tmp_path/'scan.json'; path.write_text('previous')
    with pytest.raises(ValueError):
        report.write_json({'bad': float('nan')}, str(path))
    assert path.read_text() == 'previous'


def test_live_parser_unknown_fields_do_not_become_currency_or_free_shipping():
    items = ebay_api.parse_search_payload({'itemSummaries': [
        {'itemId': '1', 'price': {'value': 'NaN'}},
        {'itemId': '2', 'price': {'value': '100', 'currency': 'USD'}},
    ]})
    assert len(items) == 2 and items[0].price is None
    assert items[0].currency == '' and items[0].shipping is None
    assert items[0].buying_option == ''


def test_production_search_uses_graded_filter(monkeypatch):
    def search(query, **kw):
        assert kw['graded_only'] is True
        return []
    scanner.scan_card(CARD, SimpleNamespace(calls=0, search=search), current_config(),
                      refs=refs(), fair=FairValue(), log=lambda *a: None)


def test_source_page_without_tables_is_a_failure(monkeypatch):
    from collections import Counter
    monkeypatch.setattr(scanner.pc_sales, 'fetch_page', lambda *a, **kw: '<html>maintenance</html>')
    stats = Counter()
    _, result = scanner.load_card_page(CARD, stats=stats, log=lambda *a: None)
    assert not result.available and stats['pc_error'] == 1
