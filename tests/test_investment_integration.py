"""Production path with synthetic cards/sales; collectors are never contacted."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
import yaml

import main
import build_watchlist
from src import investment, report, scanner, slab_report
from src.models import FairValue, Listing, WatchCard
from src.policy_validation import PolicyError, validate_config
from src.slab_strategy import evaluate, policy_config


CARD = WatchCard('Examplemon', 'Example Set', '1/100', 'EN', 'https://example.com/card')
TITLE = 'Examplemon 1/100 Example Set English PSA 10'


def config():
    cfg = policy_config()
    cfg['slab_strategy']['costs'].update(comc_storage_usd=0, storage_horizon_days=None)
    today = datetime.now(timezone.utc).date()
    profile = {'name': CARD.name, 'set': CARD.set_name, 'number': CARD.number,
               'language': CARD.language, 'grade': 'PSA 10', 'variants': [],
               'invalidation': 'Synthetic thesis invalidates when demand weakens.',
               'signals': {key: {'direction': 'supportive', 'source': f'https://example.com/{key}',
                                 'as_of': today.isoformat(), 'reason': 'Synthetic documented observation.'}
                           for key in investment.SIGNALS}}
    cfg['thesis_profiles'] = {investment.identity_key(CARD.name, CARD.set_name, CARD.number, CARD.language): profile}
    return cfg


def listing(price=100, **changes):
    item = Listing('999', TITLE, price, 5, 'USD', 'FIXED_PRICE', 'Graded',
                   99.9, 1000, 'https://example.com/listing', country='US')
    return replace(item, **changes)


def sales(price=150, count=12):
    today = datetime.now(timezone.utc).date()
    rows = [{'source': 'ebay', 'sale_id': str(1000 + i), 'title': TITLE, 'price': price,
             'date': (today - timedelta(days=2 + i * 4)).isoformat()}
            for i in range(count)]
    return SimpleNamespace(available=True, _sales=rows)


def evaluate_synthetic(price=100, reference=150, cfg=None, **changes):
    return evaluate(CARD, listing(price, **changes), config=cfg or config(), refs=sales(reference))


def test_real_evaluation_requires_three_axes_not_legacy_lp_or_price_column():
    cfg = config()
    opp = evaluate_synthetic(cfg=cfg)
    assert opp.verdict == 'OPORTUNIDADE'
    assert opp.strategy['investment_assessment']['automatic_purchase'] is False
    assert opp.strategy['economic_gate']['threshold'] == 20
    cfg.pop('thesis_profiles')
    opp = evaluate(CARD, listing(), config=cfg, refs=sales(),
                   fair=FairValue(prices={'PSA 10': 99999}, sales_per_month={'PSA 10': 999}))
    assert opp.verdict == 'REVISAR'
    assert opp.strategy['investment_assessment']['thesis']['status'] == 'unconfirmed'


@pytest.mark.parametrize('reference,verdict', [('120', 'MONITORAR'), ('120.00001', 'MONITORAR'), ('150', 'OPORTUNIDADE')])
def test_gross_floor_never_overrides_net_entry_costs(reference, verdict):
    # At just over 20% the gross test can pass while current net proceeds fail.
    opp = evaluate_synthetic(reference=Decimal(reference))
    assert opp.verdict == verdict
    assert not opp.strategy['rejection_reasons']


def test_exact_twenty_floor_and_cent_ceiling_with_zero_configured_fees():
    cfg = config()
    cfg['slab_strategy']['costs'].update(per_slab_usd=0, comc_processing_usd=0,
                                        selling_fee_percent=0, cashout_fee_percent=0)
    on = evaluate_synthetic(reference=120, cfg=cfg, shipping=0)
    above = evaluate_synthetic(reference=Decimal('120.00001'), cfg=cfg, shipping=0)
    assert on.verdict == 'MONITORAR'
    assert above.verdict == 'OPORTUNIDADE'
    assert on.strategy['entry_item_cap'] == 99.99
    assert above.strategy['entry_item_cap'] == 100


def test_ceiling_respects_both_net_safety_and_gross_gate_at_exact_cents():
    opp = evaluate_synthetic()
    cap = opp.strategy['entry_item_cap']
    assert cap == 115.74  # 150*.95*.90 - 10 - 2.50, strictly positive net
    assert evaluate_synthetic(price=cap).verdict == 'OPORTUNIDADE'
    assert evaluate_synthetic(price=cap + .01).verdict == 'MONITORAR'


def test_counts_use_all_strict_sales_not_ten_price_comparables():
    pool = sales(count=15)
    pool._sales += [dict(pool._sales[0]), dict(pool._sales[1], sale_id='5000', title=TITLE.replace('English', 'Japanese'))]
    opp = evaluate(CARD, listing(), config=config(), refs=pool)
    ev = opp.strategy['resale_evidence']
    assert ev['sales_90d'] == 15 and ev['n_used'] == 10
    assert ev['active_months_90d'] >= 2
    assert opp.strategy['investment_assessment']['evidence']['observed_sales_per_month'] == 5


@pytest.mark.parametrize('changes,reason', [
    ({'price': 501}, 'preco-acima-do-orcamento-por-carta'),
    ({'title': TITLE.replace('PSA 10', 'PSA 9')}, 'longo-prazo-apenas-PSA-10'),
    ({'condition': 'Ungraded'}, 'titulo-certificado-condicao-ungraded'),
    ({'buying_option': 'AUCTION'}, 'somente-preco-fixo'),
])
def test_structural_veto_survives_a_favorable_thesis(changes, reason):
    opp = evaluate(CARD, listing(**changes), config=config(), refs=sales())
    assert opp.verdict == 'REJEITAR'
    assert reason in opp.reasons


def test_cost_unknown_or_shipping_over_reserve_never_qualifies():
    cfg = config()
    cfg['slab_strategy']['costs']['coverage_confirmed'] = False
    assert evaluate_synthetic(cfg=cfg).verdict == 'REVISAR'
    opp = evaluate_synthetic(shipping=40)
    assert opp.verdict == 'REVISAR'
    assert 'frete-observado-excede-reserva-de-envio-impostos' in opp.reasons


def test_non_usd_amount_is_not_compared_to_usd_item_budget():
    opp = evaluate_synthetic(price=600, currency='CAD')
    assert opp.verdict == 'REVISAR'
    assert 'moeda-nao-USD-sem-conversao' in opp.reasons
    assert 'preco-acima-do-orcamento-por-carta' not in opp.reasons


def test_conflicting_grades_require_review_not_proven_rejection():
    opp = evaluate_synthetic(title=TITLE + ' BGS 9.5')
    assert opp.verdict == 'REVISAR'
    assert 'investment-grade-unconfirmed' in opp.reasons


def test_classifier_fault_keeps_line_visible_and_never_leaves_provisional_approval(monkeypatch):
    def broken(*args):
        raise RuntimeError('do not emit private internals')
    monkeypatch.setattr(investment, 'apply', broken)
    opp = evaluate_synthetic()
    assert opp.verdict == 'REVISAR'
    assert opp.strategy['investment_assessment']['error'] == 'RuntimeError'
    assert 'do not emit' not in str(opp.strategy)


def test_report_has_axes_explicit_twenty_and_no_private_profile_metadata():
    cfg = config()
    opp = evaluate_synthetic(cfg=cfg)
    payload = report.scan_payload([opp], 1, cfg)
    assert 'thesis_profiles' not in payload['meta']['config']
    text = slab_report.render(payload)
    assert '| Decisão | Tese | Entrada | Evidência | Longo prazo | Links |' in text
    assert '20%' in text and '1 OPORTUNIDADE' in text
    lines = text.splitlines()
    head = next(i for i, line in enumerate(lines) if line.startswith('| Carta'))
    assert lines[head].count('|') == lines[head+1].count('|') == lines[head+2].count('|')
    assert 'Teto condicional do item' in text


def test_favorable_but_expensive_listing_stays_visible_in_monitoring_funnel():
    opp = evaluate_synthetic(price=140)
    assert opp.verdict == 'MONITORAR'
    assert 'MONITORAR' in slab_report.render(report.scan_payload([opp], 1, config(), funnel=Counter(rows_monitor=1)))
    assert 'Linhas MONITORAR: 1' in ' '.join(report.policy_funnel_lines(Counter(rows_monitor=1), mode='longterm'))


def test_limited_batch_banner_is_not_an_aborted_scan():
    payload = report.scan_payload([], 200, config(), funnel=Counter(
        selection_cards_in_scope=200, selection_cards_scheduled=25,
        selection_cards_deferred=175, selection_scope_limited=1))
    text = slab_report.render(payload)
    assert 'LOTE LIMITADO' in text and '175 fora deste lote, não rejeitadas' in text
    assert 'EXECUÇÃO ABORTADA' not in text


def test_default_discovery_has_no_per_set_price_cap():
    assert build_watchlist.DEFAULT_CAP == 0
    assert scanner.query_suffixes(config()) == [' PSA 10']


@pytest.mark.parametrize('threshold', [None, 15, 19, 21, 43])
def test_longterm_entry_floor_cannot_drift_from_twenty(threshold):
    cfg = config()
    cfg['slab_strategy']['economics']['min_gross_margin_percent'] = threshold
    with pytest.raises(PolicyError):
        validate_config(cfg)


def test_private_thesis_file_loads_without_network_or_leaking_profile(tmp_path, capsys):
    profiles = list(config()['thesis_profiles'].values())
    path = tmp_path / 'theses.private.yaml'
    path.write_text(yaml.safe_dump({'version': 1, 'cards': profiles}), encoding='utf-8')
    assert main.main(['--check-config', '--thesis-file', str(path)]) == 0
    output = capsys.readouterr().out
    assert '20%' in output and CARD.name not in output


@pytest.mark.parametrize('args', [['--grades', 'PSA 9'], ['--min-gross-margin', '15']])
def test_invalid_longterm_overrides_fail_before_collecting(monkeypatch, args):
    monkeypatch.setattr(scanner, 'run_scan', lambda **kw: pytest.fail('must not collect'))
    with pytest.raises(SystemExit):
        main.main(args)


def test_legacy_gross_only_mode_is_still_available():
    cfg = config()
    cfg['slab_strategy']['economics']['gate_mode'] = 'gross_margin'
    cfg.pop('thesis_profiles')
    opp = evaluate_synthetic(cfg=cfg)
    assert opp.verdict == 'APROVAR'
    assert 'investment_assessment' not in opp.strategy


def test_check_config_reports_thesis_watchlist_coverage_without_identities(tmp_path, capsys):
    matched = deepcopy(next(iter(config()['thesis_profiles'].values())))
    unmatched = deepcopy(matched)
    unmatched['set'] = 'Example'   # exact identity required; this one matches no card
    theses = tmp_path / 'theses.private.yaml'
    theses.write_text(yaml.safe_dump({'version': 1, 'cards': [matched, unmatched]}), encoding='utf-8')
    watchlist = tmp_path / 'watchlist.private.yaml'
    watchlist.write_text(yaml.safe_dump({'cards': [{
        'name': CARD.name, 'set': CARD.set_name, 'number': CARD.number,
        'language': CARD.language, 'pc_url': CARD.pc_url}]}), encoding='utf-8')
    assert main.main(['--check-config', '--thesis-file', str(theses), '--watchlist', str(watchlist)]) == 0
    output = capsys.readouterr().out
    assert 'Teses: 2 carregadas · 1 com carta na watchlist · 1 sem carta correspondente' in output
    assert 'REVISAR: 1 tese(s) sem carta correspondente' in output
    assert CARD.name not in output and 'Example' not in output
