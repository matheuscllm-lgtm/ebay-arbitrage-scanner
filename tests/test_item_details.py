from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
import pytest

from src import scanner, ebay_api
from src.models import FairValue
from src.slab_strategy import listing_language, evaluate
from src.ebay_api import EbayApiError
from tests.test_slab_strategy import CARD, listing, refs, sales
from tests.test_policy_review import current_config


@pytest.mark.parametrize('title,values,code', [
    ('Charizard Base Set #4 PSA 10', ['English'], 'EN'),
    ('Charizard Base Set #4 Japanese PSA 10', ['English'], None),
    ('Charizard Base Set #4 PSA 10', ['Japanese'], 'JP'),
    ('Charizard Base Set #4 PSA 10', ['English', 'Japanese'], None),
    ('Charizard Base Set #4 PSA 10', ['Chinese'], None),
    ('Charizard Base Set #4 PSA 10', [], None),
    ('Charizard Base Set #4 English Japanese PSA 10', ['English'], None),
])
def test_explicit_aspect_without_guessing_or_overriding_conflicts(title, values, code):
    assert listing_language(listing(title=title, item_aspects={'Language': values}))[0] == code


def test_hydration_production_budget_and_evidence():
    class Ebay:
        calls = 0
        def search(self, *args, **kw):
            self.calls += 1
            return [listing(item_id=str(n), price=60, title='Charizard Base Set #4 PSA 10') for n in range(3)]
        def get_item(self, item_id):
            self.calls += 1
            return {'itemId': item_id, 'localizedAspects': [{'name': 'Language', 'value': 'English'}]}, 'https://api.ebay.com/item/'+item_id
    stats = Counter(); c = current_config(); c['max_item_details_per_card'] = 2
    _, rows = scanner.scan_card(CARD, Ebay(), c, refs=refs(sales()), fair=FairValue(), stats=stats, log=lambda *a: None)
    assert stats['ebay_calls'] == 3 and stats['item_details_fetched'] == 2
    assert [r.verdict for r in rows] == ['APROVAR', 'APROVAR', 'REVISAR']
    assert rows[0].strategy['language_source'] == 'ebay-getItem-localizedAspects.Language'
    assert rows[2].strategy['listing_language'] is None


def test_details_failure_preserves_candidate_and_counts_call():
    class Ebay:
        calls = 0
        def search(self, *a, **kw):
            self.calls += 1
            return [listing(title='Charizard Base Set #4 PSA 10')]
        def get_item(self, item_id):
            self.calls += 1
            raise EbayApiError('gone')
    stats = Counter()
    _, rows = scanner.scan_card(CARD, Ebay(), current_config(), refs=refs(sales()), fair=FairValue(), stats=stats, log=lambda *a: None)
    assert len(rows) == 1 and rows[0].verdict == 'REVISAR'
    assert 'detalhes-do-anuncio-indisponiveis' in rows[0].reasons
    assert stats['item_details_error'] == 1 and stats['ebay_calls'] == 2


@pytest.mark.parametrize('aspect,value', [('Set', 'Base Set 2'), ('Card Number', '5'), ('Professional Grader', 'CGC'), ('Grade', '9')])
def test_structured_conflicts_never_approve(aspect, value):
    item = listing(price=60, item_aspects={aspect: [value]})
    o = evaluate(CARD, item, config=current_config(), refs=refs(sales()))
    assert o.verdict == 'REVISAR'


def test_get_item_id_is_validated_and_encoded(monkeypatch):
    c = ebay_api.EbayClient('id', 'secret')
    def request(url):
        assert 'v1%7C123%7C0' in url
        return {'itemId': 'different'}
    monkeypatch.setattr(c, '_request_search_json', request)
    with pytest.raises(EbayApiError, match='different'):
        c.get_item('v1|123|0')
