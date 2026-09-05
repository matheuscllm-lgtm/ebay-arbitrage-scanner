from collections import Counter
from dataclasses import replace
import urllib.error
import pytest
from src import ebay_api, scanner
from src.slab_strategy import policy_config
from tests.test_slab_strategy import CARD


def test_exhausted_budget_does_not_even_request_token(monkeypatch):
    client = ebay_api.EbayClient('id', 'secret')
    client.max_calls = client.calls = 1
    monkeypatch.setattr(client, '_get_token', lambda: pytest.fail('token requested'))
    with pytest.raises(ebay_api.EbayBudgetExceeded):
        client.get_item('v1|123|0')


def test_retry_cannot_exceed_budget(monkeypatch):
    client = ebay_api.EbayClient('id', 'secret')
    client.max_calls = 1
    monkeypatch.setattr(client, '_get_token', lambda: 'synthetic-token')
    def fail(*a, **kw):
        raise urllib.error.URLError('synthetic timeout')
    monkeypatch.setattr(ebay_api.urllib.request, 'urlopen', fail)
    monkeypatch.setattr(ebay_api.time, 'sleep', lambda *a: pytest.fail('retry after exhaustion'))
    with pytest.raises(ebay_api.EbayBudgetExceeded):
        client.get_item('v1|123|0')
    assert client.calls == 1


def test_scan_stops_on_budget_and_preserves_previous_cards(monkeypatch):
    client = ebay_api.EbayClient('id', 'secret')
    monkeypatch.setattr(scanner, 'EbayClient', lambda: client)
    cards = [CARD, replace(CARD, name='Blastoise'), replace(CARD, name='Venusaur')]
    monkeypatch.setattr(scanner, 'load_watchlist', lambda *a: cards)
    visited = []
    def scan(card, ebay, config, **kw):
        visited.append(card.name)
        if len(visited) == 2:
            raise ebay_api.EbayBudgetExceeded('exhausted')
        return object(), ['completed-card-result']
    monkeypatch.setattr(scanner, 'scan_card', scan)
    _, rows, _, stats, aborted = scanner.run_scan(config=policy_config(), log=lambda *a: None)
    assert rows == ['completed-card-result']
    assert len(visited) == 2 and aborted
    assert stats['ebay_budget_exhausted'] == 1
