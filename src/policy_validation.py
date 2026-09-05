"""Validate strategy shape before network access; null remains an explicit pending value."""
from decimal import Decimal, InvalidOperation


class PolicyError(ValueError):
    pass


def validate_config(config):
    def fail(path):
        raise PolicyError(f'Configuração inválida: {path}')

    def number(value, path, low=0, high=None, nullable=False):
        if value is None and nullable:
            return
        try:
            n = Decimal(str(value))
            if isinstance(value, bool) or not n.is_finite() or n < low or (high is not None and n > high):
                fail(path)
        except (InvalidOperation, ValueError, TypeError):
            fail(path)

    p = config.get('slab_strategy')
    if not isinstance(p, dict):
        fail('slab_strategy deve ser um objeto')
    for section in ('evidence', 'costs', 'economics', 'logistics', 'graders'):
        if not isinstance(p.get(section), dict):
            fail(f'slab_strategy.{section} deve ser um objeto')
    if not isinstance(p.get('version'), str) or not p['version']:
        fail('slab_strategy.version')
    if not isinstance(p.get('languages'), list) or not p['languages'] or not all(isinstance(x, str) for x in p['languages']):
        fail('slab_strategy.languages')
    e = p['evidence']
    for key in ('min_sales', 'median_sample_limit'):
        if type(e.get(key)) is not int or e[key] < 1:
            fail(f'evidence.{key}')
    if e['median_sample_limit'] < e['min_sales']:
        fail('evidence.median_sample_limit menor que min_sales')
    windows = e.get('windows_days')
    if not isinstance(windows, list) or not windows or any(type(x) is not int or x < 1 for x in windows) or sorted(set(windows)) != windows:
        fail('evidence.windows_days: lista crescente de dias positivos')
    number(e.get('max_dispersion_percent'), 'evidence.max_dispersion_percent', nullable=True)
    for grader, rule in p['graders'].items():
        if rule is None:
            continue
        if not isinstance(rule, dict) or not isinstance(rule.get('grades'), dict):
            fail(f'graders.{grader}')
        for grade, mapping in rule['grades'].items():
            if not isinstance(mapping, dict) or mapping.get('psa_grade') not in (8, 9, 10):
                fail(f'graders.{grader}.{grade}.psa_grade')
            number(mapping.get('factor'), f'graders.{grader}.{grade}.factor', low=Decimal('0.000001'))
        if grader == 'BGS':
            number(rule.get('max_premium_percent'), 'graders.BGS.max_premium_percent')
            if rule.get('combine_9_5_premium') is not None and type(rule['combine_9_5_premium']) is not bool:
                fail('graders.BGS.combine_9_5_premium')
        if grader in ('CGC', 'TAG'):
            number(rule.get('max_reference_percent'), f'graders.{grader}.max_reference_percent', nullable=True)
    c = p['costs']
    if type(c.get('coverage_confirmed')) is not bool:
        fail('costs.coverage_confirmed deve ser true ou false')
    if not isinstance(c.get('covers'), list):
        fail('costs.covers')
    for key in ('per_slab_usd', 'comc_processing_usd', 'comc_storage_usd'):
        number(c.get(key), f'costs.{key}', nullable=True)
    for key in ('selling_fee_percent', 'cashout_fee_percent'):
        number(c.get(key), f'costs.{key}', high=Decimal('99.999999'), nullable=True)
    if c.get('storage_horizon_days') is not None:
        if type(c['storage_horizon_days']) is not int or not 1 <= c['storage_horizon_days'] <= 36500:
            fail('costs.storage_horizon_days')
        if type(c.get('storage_free_days')) is not int or c['storage_free_days'] < 0:
            fail('costs.storage_free_days')
        for key in ('storage_monthly_usd', 'buyer_shipping_markup_usd', 'security_daily_fraction', 'security_threshold_usd'):
            number(c.get(key), f'costs.{key}')
    for key in ('min_profit_usd', 'min_net_margin_percent', 'min_net_roi_percent', 'min_discount_percent'):
        number(p['economics'].get(key), f'economics.{key}', nullable=True)
    mode = p['economics'].get('gate_mode', 'all_minima')
    if mode not in ('all_minima', 'profit_or_discount'):
        fail('economics.gate_mode')
    if mode == 'profit_or_discount' and p['economics'].get('require_positive_profit') is not True:
        fail('economics.require_positive_profit')
    for key, default in [('min_price_usd', 10), ('trusted_min_feedback', 50), ('suspicious_margin_percent', 60)]:
        number(config.get(key, default), key)
    number(config.get('trusted_min_feedback_pct', 98), 'trusted_min_feedback_pct', high=100)
    number(config.get('min_discount_percent', 20), 'min_discount_percent', low=-100, high=100)
    if type(config.get('max_pages', 3)) is not int or config.get('max_pages', 3) < 1:
        fail('max_pages')
    if type(config.get('max_ebay_calls', 500)) is not int or config.get('max_ebay_calls', 500) < 1:
        fail('max_ebay_calls')
    if type(config.get('max_item_details_per_card', 10)) is not int or config.get('max_item_details_per_card', 10) < 0:
        fail('max_item_details_per_card')
    return config


def pending_config(config):
    """Human-readable list, not a substitute for per-candidate evaluation."""
    validate_config(config)
    p = config['slab_strategy']
    pending = []
    for section, keys in {
        'costs': ('per_slab_usd', 'comc_processing_usd', 'comc_storage_usd', 'selling_fee_percent', 'cashout_fee_percent', 'fee_basis'),
        'economics': (('min_profit_usd', 'min_discount_percent') if p['economics'].get('gate_mode') == 'profit_or_discount' else ('min_profit_usd', 'min_net_margin_percent', 'min_net_roi_percent')),
        'evidence': ('max_dispersion_percent',),
    }.items():
        pending.extend(f'{section}.{key}' for key in keys if p[section].get(key) is None)
    if not p['costs']['coverage_confirmed']:
        pending.append('costs.coverage_confirmed: trechos de envio/impostos estimados')
    if p['costs'].get('storage_horizon_days') is not None:
        pending = [item for item in pending if item != 'costs.comc_storage_usd']
    if p['graders'].get('BGS', {}).get('combine_9_5_premium') is None:
        pending.append('graders.BGS.combine_9_5_premium (somente BGS 9,5)')
    return pending
