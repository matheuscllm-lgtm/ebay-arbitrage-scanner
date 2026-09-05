import json
from collections import Counter
import main
from src import scanner, report, slab_report
from src.slab_strategy import evaluate, policy_config
from tests.test_slab_strategy import CARD, listing, sales, refs


def test_interrupted_scan_preserves_csv_as_well_as_json(monkeypatch, tmp_path, capsys):
    csv = tmp_path / 'last.csv'
    out = tmp_path / 'last.json'
    csv.write_text('previous complete csv', encoding='utf-8')
    out.write_text('previous complete json', encoding='utf-8')
    opp = evaluate(CARD, listing(price=50), config=policy_config(), refs=refs(sales()))
    monkeypatch.setattr(scanner, 'load_watchlist', lambda *a: [CARD])
    monkeypatch.setattr(scanner, 'run_scan', lambda **kw: ({}, [opp], False, Counter(seen=1, aborted=1), True))
    assert main.main(['--out',str(out),'--csv',str(csv)]) == 1
    assert csv.read_text() == 'previous complete csv'
    assert out.read_text() == 'previous complete json'
    assert (tmp_path/'last.aborted.csv').exists()
    assert json.loads((tmp_path/'last.aborted.json').read_text(encoding='utf-8'))['meta']['aborted']


def test_incomplete_banner_precedes_opportunities_and_shared_evidence_is_not_duplicated():
    c = policy_config()
    opp = evaluate(CARD, listing(price=50), config=c, refs=refs(sales()))
    payload = report.scan_payload([opp], 1, c, aborted=True)
    text = slab_report.render(payload)
    assert text.index('EXECUÇÃO ABORTADA') < text.index('| Carta')
    assert text.count('https://www.ebay.com/itm/100)') == 1
    assert 'mesma amostra PSA' in text
    saved = payload['meta']['config']
    assert saved['max_ebay_calls'] == 500 and saved['trusted_min_feedback'] == 50


def test_missing_resale_is_not_reported_as_missing_fee_configuration():
    opp = evaluate(CARD, listing(price=50), config=policy_config(), refs=refs())
    assert 'armazenamento-sem-base-de-revenda' in opp.reasons
    assert 'custos-COMC-indefinidos' not in opp.reasons
    assert opp.verdict == 'REVISAR'
