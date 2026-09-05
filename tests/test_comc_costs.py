from datetime import date
from decimal import Decimal

import pytest
from src.comc_costs import estimate_storage
from src.slab_strategy import policy_config, evaluate
from tests.test_slab_strategy import CARD, listing, refs, sales


def costs():
    return policy_config()['slab_strategy']['costs']


def test_120_days_security_has_no_free_period():
    value, info = estimate_storage(costs(), Decimal('100'), today=date(2026, 9, 5))
    assert info['storage_billing_dates'] == ['2027-01-01']
    assert Decimal(info['storage_exact']) == Decimal('0.01')
    assert Decimal(info['security_exact']) == Decimal('0.1224')  # (100 + buyer markup 2) * .00001 * 120
    assert value == Decimal('0.1324')


def test_90_days_no_storage_but_security_charged():
    c = costs(); c['storage_horizon_days'] = 90
    value, info = estimate_storage(c, Decimal('100'), today=date(2026, 9, 5))
    assert info['storage_billing_dates'] == []
    assert value == Decimal('0.0918')


@pytest.mark.parametrize('ask,security', [('48', '0'), ('48.01', '0.060012')])
def test_security_threshold_uses_list_price(ask, security):
    _, info = estimate_storage(costs(), Decimal(ask), today=date(2026, 9, 5))
    assert Decimal(info['security_exact']) == Decimal(security)


def test_missing_horizon_is_not_free_storage():
    c = costs(); c['storage_horizon_days'] = None
    value, _ = estimate_storage(c, Decimal('100'))
    assert value is None


def test_real_policy_costs_are_all_counted_once():
    c = policy_config(); c['slab_strategy']['evidence']['max_dispersion_percent'] = 30
    o = evaluate(CARD, listing(price=60, shipping=8), config=c, refs=refs(sales()))
    assert o.verdict == 'APROVAR'
    assert o.strategy['net_sale_proceeds'] == 85.5
    storage = o.strategy['costs']['storage_forecast']
    investment = Decimal('60') + Decimal('10') + Decimal('2.50') + Decimal(storage['storage_exact']) + Decimal(storage['security_exact'])
    assert o.strategy['profit_estimate'] == float((Decimal('85.5') - investment).quantize(Decimal('.01')))
    assert o.strategy['costs']['listing_shipping_observed_usd'] == 8
    assert o.strategy['costs']['cashout_fee_usd'] == 9.5
