"""Report and suspicion checks must use the same resale return as the gate."""
from decimal import Decimal

import pytest

from src import report, slab_report
from src.slab_strategy import evaluate
from tests.test_gross_margin_base import gm, cgc_refs
from tests.test_slab_strategy import CARD, listing, refs, sales


@pytest.mark.parametrize('grade', ['PSA 10', 'CGC 10 Gem', 'TAG 10', 'BGS 10'])
def test_extreme_resale_return_flags_every_grader(grade):
    pool = refs(sales(grade='PSA 10', price=800, start=100),
                sales(grade=grade, price=800, start=200))
    o = evaluate(CARD, listing(grade=grade, price=100), config=gm(), refs=pool)
    assert o.strategy['economic_gate']['margin_pass'] is True
    assert 'retorno-elevado-conferir-identidade' in o.reasons
    assert o.verdict == 'REVISAR'


def test_high_psa_comparison_is_not_high_cgc_resale_return():
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=200), config=gm(),
                 refs=cgc_refs(psa_price=2000, cgc_price=400))
    assert o.strategy['economic_gate']['gross_margin_percent'] == 100
    assert 'retorno-elevado-conferir-identidade' not in o.reasons


def test_no_resale_never_falls_back_to_psa_in_report_or_json():
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=100), config=gm(),
                 refs=refs(sales(grade='PSA 10', price=800)))
    row = report.opportunity_row(o)
    assert row['margin_pct'] is None
    assert report.gross_margin_value(row) is None


def test_old_policy_payload_with_no_gate_does_not_publish_comparison_return():
    assert report.gross_margin_value({'strategy': {'resale_estimate': None},
                                     'margin_pct': 700}) is None
    assert report.gross_margin_value({'margin_pct': 700}) == 700


def test_rejected_candidate_keeps_a_calculated_return():
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=350), config=gm(), refs=cgc_refs())
    row = report.opportunity_row(o)
    assert o.verdict == 'REJEITAR'
    assert report.gross_margin_value(row) == pytest.approx(14.29)
    assert row['margin_pct'] == pytest.approx(100 / 7)


def test_strict_ceiling_cannot_equal_the_rejected_boundary():
    o = evaluate(CARD, listing(price=100), config=gm(), refs=refs(sales(price=143)))
    assert o.strategy['economic_gate']['margin_pass'] is False
    assert o.strategy['comparison_cap'] == 99.99


def test_suspicion_uses_exact_value_before_display_rounding():
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=100), config=gm(),
                 refs=cgc_refs(psa_price=1000, cgc_price=250.00001))
    assert o.strategy['economic_gate']['gross_margin_percent'] == 150
    assert Decimal(o.strategy['economic_gate']['gross_margin_percent_exact']) > 150
    assert 'retorno-elevado-conferir-identidade' in o.reasons


def test_rendered_cell_stays_pending_for_old_mixed_base_payload():
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=100), config=gm(),
                 refs=refs(sales(grade='PSA 10', price=800)))
    payload = report.scan_payload([o], 1, gm())
    payload['rows'][0]['margin_pct'] = 700  # Old artifact's misleading fallback.
    text = slab_report.render(payload)
    header = next(line for line in text.splitlines() if line.startswith('| Carta'))
    row = next(line for line in text.splitlines() if line.startswith('| ['))
    col = [s.strip() for s in header.split('|')].index('Margem bruta %')
    assert row.split('|')[col].strip() == 'pendente'
