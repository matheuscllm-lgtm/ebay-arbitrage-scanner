"""Offline scheduling tests: catalog size never becomes an eligibility target."""

import pytest

from src.selection import select_batch


def test_default_schedules_all_candidates_even_above_one_hundred():
    cards = list(range(137))
    batch, meta = select_batch(cards)
    assert batch == cards
    assert batch is not cards
    assert meta["cards_in_scope"] == meta["cards_scheduled"] == 137
    assert meta["cards_deferred"] == 0
    assert meta["cards_attempted"] == meta["cards_completed"] == 0
    assert meta["scheduled_end_offset"] == 137
    assert meta["scope_limited"] is False


def test_small_catalog_is_not_padded_to_a_target():
    batch, meta = select_batch(["candidate-a", "candidate-b"], max_cards=100)
    assert batch == ["candidate-a", "candidate-b"]
    assert meta["cards_scheduled"] == 2
    assert meta["cards_deferred"] == 0
    assert meta["max_cards"] == 100
    assert meta["scope_limited"] is False


def test_batch_is_deterministic_preserves_order_and_does_not_mutate_catalog():
    cards = ["d", "b", "a", "c", "e"]
    batch, meta = select_batch(cards, max_cards=2, offset=1)
    assert batch == ["b", "a"]
    assert cards == ["d", "b", "a", "c", "e"]
    assert (batch, meta) == select_batch(cards, max_cards=2, offset=1)
    assert meta == {
        "cards_in_scope": 5,
        "cards_scheduled": 2,
        "cards_deferred": 3,
        "cards_before_batch": 1,
        "cards_after_batch": 2,
        "cards_attempted": 0,
        "cards_completed": 0,
        "card_offset": 1,
        "max_cards": 2,
        "scheduled_end_offset": 3,
        "scope_limited": True,
    }


def test_last_batch_keeps_prior_cards_outside_current_coverage():
    batch, meta = select_batch(range(7), max_cards=3, offset=6)
    assert batch == [6]
    assert meta["cards_before_batch"] == 6
    assert meta["cards_after_batch"] == 0
    assert meta["cards_deferred"] == 6
    assert meta["scope_limited"] is True
    assert meta["scheduled_end_offset"] == 7


def test_offset_without_limit_schedules_remaining_catalog():
    batch, meta = select_batch(range(5), offset=2)
    assert batch == [2, 3, 4]
    assert meta["max_cards"] is None
    assert meta["cards_deferred"] == 2
    assert meta["cards_scheduled"] == 3


def test_empty_scope_stays_empty_without_network_or_invented_eligibility():
    batch, meta = select_batch([], max_cards=20)
    assert batch == []
    assert meta["cards_in_scope"] == meta["cards_scheduled"] == 0
    assert meta["cards_deferred"] == 0
    assert meta["scope_limited"] is False


def test_exact_end_offset_is_explicit_empty_batch_not_successful_collection():
    batch, meta = select_batch([1, 2], offset=2)
    assert batch == []
    assert meta["cards_scheduled"] == meta["cards_completed"] == 0
    assert meta["cards_deferred"] == 2
    assert meta["scope_limited"] is True
    assert meta["scheduled_end_offset"] == 2


@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.0, 1.5, "2", [], {}])
def test_rejects_invalid_max_cards(invalid):
    with pytest.raises(ValueError, match="max_cards must be a positive integer"):
        select_batch([1, 2], max_cards=invalid)


@pytest.mark.parametrize("invalid", [-1, True, False, 0.0, 1.0, "0", None, [], {}])
def test_rejects_invalid_offset(invalid):
    with pytest.raises(ValueError, match="card_offset must be a non-negative integer"):
        select_batch([1, 2], offset=invalid)


def test_rejects_offset_beyond_scope_instead_of_silent_empty_success():
    with pytest.raises(ValueError, match="exceeds cards in the selected scope"):
        select_batch([1, 2], offset=3)


def test_schedule_accepts_iterable_but_never_inspects_or_scores_candidates():
    cards = [{"missing_thesis": True}, {"score": 0}, {"score": 100}]
    batch, meta = select_batch(iter(cards), max_cards=2)
    assert batch == cards[:2]
    assert meta["cards_in_scope"] == 3
    assert "eligible" not in meta
