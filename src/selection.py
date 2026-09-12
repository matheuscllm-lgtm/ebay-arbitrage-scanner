"""Bounded scan scheduling, deliberately independent from card eligibility.

The watchlist is a discovery catalog, not a quota of approved investments. A
batch preserves its caller's order (after group filtering); ``max_cards`` only
limits work for this execution. No price, score or investment status is inferred.
Offsets refer to this exact catalog order and must not be reused after changing
the watchlist or group. A later batch always needs a fresh market collection.
"""


def _integer(value, name, *, minimum):
    # bool subclasses int; accepting it would silently schedule zero/one card.
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"{name} must be a {qualifier} integer")
    return value


def validate_batch_options(max_cards=None, offset=0):
    """Validate configuration/CLI values without reading a catalog or network."""
    _integer(offset, "card_offset", minimum=0)
    if max_cards is not None:
        _integer(max_cards, "max_cards", minimum=1)


def select_batch(cards, max_cards=None, offset=0):
    """Return ``(scheduled_cards, metadata)`` without inventing eligibility.

    ``cards_in_scope`` is the input catalog after any explicit group filter.
    ``cards_deferred`` includes every card outside this batch, including those
    before the offset: a previous batch's collection is not fresh evidence for
    this run. An offset equal to scope size yields an explicit empty batch;
    offsets beyond it are rejected to catch accidental scope/order changes.

    ``cards_attempted`` and ``cards_completed`` start at zero and are updated by
    the runner, not inferred from scheduling or from the number of result rows.
    Completion means the card's processing returned successfully; a source/item
    error can still make overall coverage partial and must be reported separately.
    """
    validate_batch_options(max_cards, offset)
    catalog = list(cards)
    total = len(catalog)
    if offset > total:
        raise ValueError("card_offset exceeds cards in the selected scope")
    stop = total if max_cards is None else min(total, offset + max_cards)
    scheduled = catalog[offset:stop]
    metadata = {
        "cards_in_scope": total,
        "cards_scheduled": len(scheduled),
        "cards_deferred": total - len(scheduled),
        "cards_before_batch": offset,
        "cards_after_batch": total - stop,
        "cards_attempted": 0,
        "cards_completed": 0,
        "card_offset": offset,
        "max_cards": max_cards,
        "scheduled_end_offset": stop,
        "scope_limited": len(scheduled) != total,
    }
    return scheduled, metadata
