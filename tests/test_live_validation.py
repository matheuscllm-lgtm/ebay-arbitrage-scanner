from pathlib import Path
import json
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace

import pytest
import validate_live as live
from tests.test_slab_strategy import CARD, listing, cfg, refs, sales
from src.slab_strategy import evaluate


def setup(monkeypatch, present=True):
    monkeypatch.setattr(live, 'EbayClient', lambda: SimpleNamespace(configured=present))
    monkeypatch.setattr(live.scanner, 'load_watchlist', lambda *a: [CARD])
    monkeypatch.setattr(live.scanner, 'filter_group', lambda cards, group: cards)


def test_missing_secrets_no_network_or_values(monkeypatch, tmp_path, capsys):
    setup(monkeypatch, False)
    monkeypatch.setenv('EBAY_DEV_ID','NEVER_PRINT_ME')
    monkeypatch.setattr(live.scanner,'run_scan',lambda **kw: pytest.fail('network attempted'))
    assert live.validate(out_dir=tmp_path)==1
    assert 'NEVER_PRINT_ME' not in capsys.readouterr().out
    assert json.loads((tmp_path/'validation.json').read_text())['credentials_present'] is False


@pytest.mark.parametrize('stats,aborted,with_sales,code,status',[
    ({'seen':1,'ebay_calls':1},False,True,0,'success'),
    ({'seen':1,'ebay_calls':1},False,False,2,'partial'),
    ({'seen':1,'pc_error':1},False,False,1,'blocked'),
    ({'aborted':1},True,False,1,'blocked'),
    ({'seen':0},False,False,1,'blocked'),
])
def test_live_result_never_claims_success_without_both_sources(monkeypatch,tmp_path,stats,aborted,with_sales,code,status):
    setup(monkeypatch)
    def run(**kw):
        import yaml
        entries=yaml.safe_load(Path(kw['watchlist_path']).read_text())['cards']
        assert len(entries)==1 and entries[0]['set']==CARD.set_name
        assert kw['config']['max_pages']==1
        assert kw['config']['grade_query_suffixes'] is False
        o=evaluate(CARD,listing(),config=cfg(),refs=refs(sales() if with_sales else []))
        return {},[o],False,Counter(stats),aborted
    monkeypatch.setattr(live.scanner,'run_scan',run)
    assert live.validate(out_dir=tmp_path)==code
    summary=json.loads((tmp_path/'validation.json').read_text())
    assert summary['status']==status
    if status == 'partial':
        assert summary['execution_status'] == 'completed'
        assert summary['evidence_status'] == 'insufficient_sample'
    assert (tmp_path/'scan.json').exists()
    assert (tmp_path/'report.md').exists()


def test_workflow_never_collects_or_uploads_market_results():
    import yaml
    workflow=yaml.safe_load(Path('.github/workflows/validate-ebay.yml').read_text())
    trigger=workflow.get('on', workflow.get(True))
    assert set(trigger) == {'workflow_dispatch'}
    assert 'schedule' not in trigger
    text=Path('.github/workflows/validate-ebay.yml').read_text()
    # Só a verificação mínima de credenciais (booleanos no log); nunca scan, relatório,
    # artifact ou job summary (DELIVERY_CHAT.md).
    for banned in ('upload-artifact', 'GITHUB_STEP_SUMMARY', 'main.py', 'ebay_summary',
                   'validate_live', 'results/'):
        assert banned not in text
    steps=workflow['jobs']['auth-check']['steps']
    with_env=[s for s in steps if 'env' in s]
    assert len(with_env) == 1
    assert with_env[0]['run'].strip() == 'python ebay_auth_check.py'
    assert set(with_env[0]['env']) == {'EBAY_CLIENT_ID', 'EBAY_CLIENT_SECRET'}


@pytest.mark.parametrize('grade', [8, 9, 10])
def test_catalog_year_narrows_discovery_without_altering_card(monkeypatch, tmp_path, grade):
    setup(monkeypatch)
    card = replace(CARD, year=1999)
    monkeypatch.setattr(live.scanner, 'load_watchlist', lambda *a: [card])
    def run(**kw):
        import yaml
        entry = yaml.safe_load(Path(kw['watchlist_path']).read_text())['cards'][0]
        assert entry['ebay_query'].endswith(f'1999 English PSA {grade}')
        assert entry['set'] == card.set_name and entry['pc_url'] == card.pc_url
        return {}, [], False, Counter(seen=1), False
    monkeypatch.setattr(live.scanner, 'run_scan', run)
    assert live.validate(out_dir=tmp_path, psa_grade=grade) == 2
    summary = json.loads((tmp_path/'validation.json').read_text())
    assert summary['queries'][0].endswith(f'1999 English PSA {grade}')
