"""Offline, synthetic regression coverage for the pre-eBay curation queue."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import preselect
from src import preselection, scanner
from src.models import FairValue, WatchCard
from src.slab_strategy import policy_config, reference_sales
from src.grading import Grade


CARD = WatchCard('Examplemon', 'Example Set', '1/100', 'EN', 'https://example.com/card')
TITLE = 'Examplemon 1/100 Example Set English PSA 10'


def refs(price=150, count=12, title=TITLE):
    today = datetime.now(timezone.utc).date()
    return SimpleNamespace(available=True, url=CARD.pc_url, _sales=[
        {'source': 'ebay', 'sale_id': str(1000 + i), 'title': title, 'price': price,
         'date': (today - timedelta(days=2 + 4 * i)).isoformat()} for i in range(count)])


def assess(pool=None, cfg=None, card=CARD):
    return preselection.assess_card(card, pool if pool is not None else refs(), cfg or policy_config())


def loader(card, cfg, **kwargs):
    return FairValue(), refs()


@pytest.mark.parametrize('price', [30, 500, 650, 1500])
def test_market_price_above_purchase_budget_is_not_a_rejection(price):
    row, = assess(refs(price))
    assert row['status'] == 'CANDIDATA'
    assert row['evidence']['price'] == price
    assert row['thesis_status'] == row['entry_status'] == 'not_assessed'
    assert row['purchase_recommendation'] is False


def test_same_production_matcher_and_count_before_sample_cap():
    pool = refs(count=15)
    row, = assess(pool)
    assert row['evidence'] == reference_sales(CARD, pool, Grade('PSA', 10), frozenset(), policy_config()['slab_strategy'])
    assert row['evidence']['sales_90d'] == 15
    assert row['evidence']['n_used'] == 10


@pytest.mark.parametrize('title', [TITLE.replace('PSA 10', 'PSA 9'),
    TITLE.replace('English', 'Japanese'), TITLE.replace('1/100', '2/100'),
    TITLE + ' Best Offer', TITLE + ' lot of 2', TITLE.replace('Example Set', 'Other Set')])
def test_wrong_grade_language_identity_and_uncertain_prices_never_qualify(title):
    assert all(r['status'] == 'REVISAR' for r in assess(refs(title=title)))


def test_variants_are_not_pooled_to_pass_liquidity():
    pool = refs(count=6)
    pool._sales += [dict(s, sale_id=str(int(s['sale_id']) + 100), title=TITLE + ' 1st Edition')
                    for s in refs(count=6)._sales]
    rows = assess(pool)
    assert len(rows) == 2
    assert all(r['evidence']['sales_90d'] == 6 and r['status'] == 'REVISAR' for r in rows)


def test_missing_thesis_does_not_prevent_curation_but_never_infers_favorable():
    assert assess()[0]['thesis_status'] == 'not_assessed'


def test_dispersion_and_low_frequency_remain_visible():
    pool = refs()
    pool._sales[0]['price'] = 1000
    assert 'precos-dispersos' in assess(pool)[0]['reasons']
    assert 'poucas-vendas-em-90d' in assess(refs(count=8))[0]['reasons']
    recent = refs()
    date = datetime.now(timezone.utc).date().replace(day=1).isoformat()
    for sale in recent._sales:
        sale['date'] = date
    assert 'recorrencia-insuficiente' in assess(recent)[0]['reasons']


def test_missing_data_is_review_not_zero_market_price():
    row, = assess(SimpleNamespace(available=False))
    assert row['evidence'] is None
    assert row['reasons'] == ['fonte-indisponivel']


def test_dynamic_selection_can_exceed_one_hundred_and_calls_no_ebay(monkeypatch):
    def forbidden():
        raise AssertionError('preselection must not construct eBay client')
    monkeypatch.setattr(scanner, 'EbayClient', forbidden)
    cards = [replace(CARD, number=f'{i}/200') for i in range(1, 106)]
    def unique_loader(card, cfg, **kwargs):
        return FairValue(), refs(title=TITLE.replace('1/100', card.number))
    payload = preselection.collect(cards, policy_config(), loader=unique_loader, log=lambda _: None)
    assert payload['meta']['candidate_cards'] == 105
    assert not payload['meta']['incomplete']


def test_budget_only_defers_cards_and_preserves_offsets():
    payload = preselection.collect([CARD] * 7, policy_config(), max_cards=2, offset=3, loader=loader, log=lambda _: None)
    cov = payload['meta']['selection']
    assert cov['cards_scheduled'] == cov['cards_completed'] == 2
    assert cov['cards_deferred'] == 5 and cov['scope_limited']
    assert not payload['meta']['incomplete']


def test_fresh_cache_for_every_execution_and_no_private_theses_in_metadata():
    paths = []
    cfg = policy_config({'pc_cache_dir': 'old-cache', 'thesis_profiles': {'PRIVATE': 'secret'}})
    def observe(card, config, **kwargs):
        assert Path(config['pc_cache_dir']).is_dir()
        paths.append(config['pc_cache_dir'])
        return loader(card, config, **kwargs)
    for _ in range(2):
        result = preselection.collect([CARD], cfg, loader=observe, log=lambda _: None)
        assert 'secret' not in json.dumps(result)
    assert paths[0] != paths[1] and not any(Path(p).exists() for p in paths)
    assert cfg['pc_cache_dir'] == 'old-cache'


def test_breaker_stops_collection_and_reports_unattempted_and_failed():
    def failed(card, cfg, *, breaker, **kwargs):
        breaker.record_error()
        return FairValue(), SimpleNamespace(available=False)
    result = preselection.collect([CARD] * 10, policy_config(), loader=failed, log=lambda _: None)
    assert result['meta']['incomplete'] and result['meta']['source_breaker_open']
    assert result['meta']['failed_offsets'] == list(range(5))
    assert result['meta']['selection']['cards_attempted'] == 5
    assert result['meta']['selection']['cards_completed'] == 0
    assert len(result['rows']) == 5 and result['cards'] == []


def test_processing_error_retained_without_leaking_exception(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE SECRET')
    result = preselection.collect([CARD], policy_config(), loader=fail, log=lambda _: None)
    assert result['meta']['incomplete']
    assert result['rows'][0]['error_type'] == 'RuntimeError'
    assert 'PRIVATE SECRET' not in json.dumps(result)


def test_out_of_scope_does_not_fetch_or_count_as_source_failure():
    def forbidden(*args, **kwargs):
        raise AssertionError('must not fetch')
    result = preselection.collect([replace(CARD, language='KO')], policy_config(), loader=forbidden, log=lambda _: None)
    assert result['rows'][0]['status'] == 'FORA_DO_ESCOPO'
    assert not result['meta']['incomplete'] and result['cards'] == []


def test_subset_roundtrip_keeps_collision_guard(tmp_path):
    original = [replace(CARD), replace(CARD, set_name='Example Set 2')]
    scanner._annotate_colliding_editions(original)
    result = preselection.collect(original[:1], policy_config(), loader=loader, log=lambda _: None)
    path = tmp_path / 'candidates.json'
    path.write_text(json.dumps(result), encoding='utf-8')
    card, = scanner.load_watchlist(path)
    assert card.colliding_editions == ('Example Set 2',)
    assert card == original[0]


@pytest.mark.parametrize('value', [None, 'Other Set', [12], ['']])
def test_malformed_collision_metadata_fails_loudly(tmp_path, value):
    entry = preselection.watch_entry(CARD)
    entry['colliding_editions'] = value
    path = tmp_path / 'w.json'
    path.write_text(json.dumps({'cards': [entry]}), encoding='utf-8')
    with pytest.raises(ValueError, match='colliding_editions'):
        scanner.load_watchlist(path)


def test_report_keeps_all_rows_missing_values_links_and_scope():
    result = preselection.collect([CARD, replace(CARD, language='KO')], policy_config(), loader=loader, log=lambda _: None)
    text = preselection.render(result)
    assert '[$150.00](https://example.com/card)' in text
    assert 'FORA_DO_ESCOPO' in text and 'n/d' in text
    assert len([line for line in text.splitlines() if line.startswith('|')]) == 4


def test_cli_exports_private_consumable_file_without_overwriting(tmp_path, monkeypatch, capsys):
    root = tmp_path
    monkeypatch.setattr(preselect, '__file__', str(root / 'preselect.py'))
    monkeypatch.setattr(preselect, '_load_config', lambda _: policy_config())
    monkeypatch.setattr(scanner, 'load_watchlist', lambda _: [CARD])
    monkeypatch.setattr(scanner, 'load_card_page', loader)
    target = root / 'results' / 'run.json'
    assert preselect.main(['--out', str(target), '--max-cards', '5']) == 0
    payload = json.loads(target.read_text())
    assert payload['meta']['candidate_cards'] == 1
    with pytest.raises(SystemExit):
        preselect.main(['--out', str(target)])
    assert json.loads(target.read_text()) == payload
    with pytest.raises(SystemExit):
        preselect.main(['--out', str(root / 'public.json')])


def test_legacy_mode_not_silently_reinterpreted():
    cfg = policy_config()
    cfg['slab_strategy']['economics']['gate_mode'] = 'gross_margin'
    with pytest.raises(ValueError, match='longterm'):
        preselection.collect([], cfg)


def test_cli_partial_run_is_nonzero_and_keeps_review_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(preselect, '__file__', str(tmp_path / 'preselect.py'))
    monkeypatch.setattr(preselect, '_load_config', lambda _: policy_config())
    monkeypatch.setattr(scanner, 'load_watchlist', lambda _: [CARD])
    monkeypatch.setattr(scanner, 'load_card_page', lambda *a, **k: (FairValue(), SimpleNamespace(available=False)))
    target = tmp_path / 'results' / 'partial.json'
    assert preselect.main(['--out', str(target)]) == 1
    payload = json.loads(target.read_text())
    assert payload['meta']['incomplete'] and payload['cards'] == []
    assert payload['rows'][0]['status'] == 'REVISAR'
    assert 'n/d' in capsys.readouterr().out


def test_export_does_not_inject_old_prices_into_downstream_scan(tmp_path, monkeypatch):
    payload = preselection.collect([CARD], policy_config(), loader=loader, log=lambda _: None)
    payload['rows'][0]['evidence']['price'] = 999999
    path = tmp_path / 'candidates.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    card, = scanner.load_watchlist(path)
    calls = []
    class EmptyEbay:
        calls = fetched = dedup_dropped = parse_dropped = 0
        def search(self, *args, **kwargs):
            return []
    def fresh(card, *args, **kwargs):
        calls.append(card)
        return FairValue(prices={'PSA 10': 75}), refs(price=75)
    monkeypatch.setattr(scanner, 'load_card_page', fresh)
    fair, _ = scanner.scan_card(card, EmptyEbay(), policy_config(), log=lambda _: None)
    assert calls == [card] and fair.prices['PSA 10'] == 75


def test_report_prints_nd_not_none_for_missing_dispersion():
    # Sales of the wrong grade: median and dispersion are absent, never 'None' in the table.
    result = preselection.collect(
        [CARD], policy_config(),
        loader=lambda card, cfg, **kwargs: (FairValue(), refs(title=TITLE.replace('PSA 10', 'PSA 9'))),
        log=lambda _: None)
    text = preselection.render(result)
    row = [line for line in text.splitlines() if line.startswith('| Examplemon')][0]
    assert '| None |' not in row and 'None' not in row
    assert row.split('|')[6].strip() == 'n/d'
