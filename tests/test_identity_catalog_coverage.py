"""Identity protections must survive a reduced scan selection."""
import json
from pathlib import Path

from src import scanner, slab_strategy
from src.models import WatchCard


def test_original_stays_protected_without_reprint_in_watchlist():
    card = WatchCard('Charizard', 'Base Set', '004/102', 'EN', '', year=1999)
    cards = [card]
    scanner._annotate_colliding_editions(cards)
    assert len(cards) == 1
    assert 'Celebrations: Classic Collection' in card.colliding_editions
    assert slab_strategy.edition_conflict(
        card, 'Charizard Base Set 4/102 English PSA 9') == 'edicao-ambigua'


def test_catalog_protects_card_outside_iconic_pokemon_selection():
    card = WatchCard('Cleffa', 'Neo Genesis', '20/111', 'EN', '', year=2000)
    scanner._annotate_colliding_editions([card])
    assert 'Celebrations: Classic Collection' in card.colliding_editions


def test_english_catalog_does_not_assign_english_reprint_to_japanese_card():
    card = WatchCard('Cleffa', 'Neo Genesis', '20', 'JP', '', year=2000)
    scanner._annotate_colliding_editions([card])
    assert not card.colliding_editions


def test_all_production_cards_accept_canonical_and_discovery_set_labels():
    failures = []
    for card in scanner.load_watchlist():
        for label in {card.set_name, slab_strategy.set_label(card.set_name)}:
            title = f'{card.year} Pokemon {card.name} {card.number} {label} English PSA 10'
            if not slab_strategy.identity_matches(card, title):
                failures.append(title)
    assert not failures, failures


def test_modern_base_label_does_not_accept_a_different_expansion():
    card = WatchCard('Umbreon GX', 'SM Base Set', '154', 'EN', '', year=2017)
    assert not slab_strategy.identity_matches(
        card, '2017 Umbreon GX 154 SM Base Set Guardians Rising English PSA 10')


def test_unrelated_tag_team_is_not_in_classic_collection():
    card = WatchCard('Reshiram & Charizard GX', 'Unbroken Bonds', '20', 'EN', '', year=2019)
    scanner._annotate_colliding_editions([card])
    assert 'Celebrations: Classic Collection' not in card.colliding_editions


def test_complete_catalog_is_metadata_only_and_every_entry_protects_independently():
    catalog = json.loads(Path('src/catalog/celebrations_classic_identity.json').read_text())
    assert len(catalog['cards']) == 25
    assert len({e['product_id'] for e in catalog['cards']}) == 25
    for entry in catalog['cards']:
        assert set(entry) == {'name', 'source_name', 'number', 'product_id'}
        card = WatchCard(entry['name'], 'Original edition', entry['number'], 'EN', '')
        scanner._annotate_colliding_editions([card])
        assert catalog['set'] in card.colliding_editions
