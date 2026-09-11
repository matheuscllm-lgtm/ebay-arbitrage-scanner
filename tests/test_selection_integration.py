"""Batch controls integrated with the runner/CLI; all collectors are mocked."""

import json
from dataclasses import replace

import pytest

import main
from src import report, scanner
from src.ebay_api import EbayBudgetExceeded
from src.models import FairValue, Listing, Opportunity, WatchCard
from src.slab_strategy import policy_config


class OfflineClient:
    configured = True


def offline_runner(monkeypatch, count=5):
    template = WatchCard(name="Synthetic", set_name="Fixture", number="1",
                         language="EN", pc_url="https://example.com/fixture")
    cards = [replace(template, name=f"Synthetic-{i}", number=str(i), group="3")
             for i in range(count)]
    monkeypatch.setattr(scanner, "load_watchlist", lambda *a: cards)
    monkeypatch.setattr(scanner, "EbayClient", OfflineClient)
    seen = []

    def scan(card, *a, **kw):
        seen.append(card.number)
        return FairValue(), []

    monkeypatch.setattr(scanner, "scan_card", scan)
    return cards, seen


def test_runner_schedules_batch_after_group_filter_and_counts_coverage(monkeypatch):
    cards, seen = offline_runner(monkeypatch)
    cards[0] = replace(cards[0], group="4")
    cfg = policy_config({"max_cards": 2, "card_offset": 1})
    _, _, _, stats, aborted = scanner.run_scan(config=cfg, group="3", log=lambda *a: None)
    assert seen == ["2", "3"]
    assert not aborted
    assert stats["cards"] == stats["selection_cards_in_scope"] == 4
    assert stats["selection_cards_scheduled"] == 2
    assert stats["selection_cards_deferred"] == 2
    assert stats["selection_cards_attempted"] == stats["selection_cards_completed"] == 2
    assert stats["selection_cards_not_attempted_in_batch"] == 0
    assert stats["selection_cards_incomplete_in_batch"] == 0
    assert stats["selection_scheduled_end_offset"] == 3
    assert stats["selection_first_incomplete_offset"] == -1


def test_runner_without_limit_does_not_stop_at_one_hundred(monkeypatch):
    _, seen = offline_runner(monkeypatch, count=103)
    _, _, _, stats, aborted = scanner.run_scan(log=lambda *a: None)
    assert len(seen) == 103
    assert stats["selection_cards_scheduled"] == 103
    assert not aborted


def test_budget_interruption_keeps_scheduled_end_separate_from_incomplete_card(monkeypatch):
    offline_runner(monkeypatch)
    visited = []

    def scan(card, *a, **kw):
        visited.append(card.number)
        if len(visited) == 2:
            raise EbayBudgetExceeded("synthetic budget")
        return FairValue(), []

    monkeypatch.setattr(scanner, "scan_card", scan)
    _, _, _, stats, aborted = scanner.run_scan(
        config={"max_cards": 3, "card_offset": 1}, log=lambda *a: None)
    assert aborted
    assert stats["selection_cards_scheduled"] == 3
    assert stats["selection_cards_attempted"] == 2
    assert stats["selection_cards_completed"] == 1
    assert stats["selection_cards_not_attempted_in_batch"] == 1
    assert stats["selection_cards_incomplete_in_batch"] == 2
    assert stats["selection_scheduled_end_offset"] == 4
    assert stats["selection_first_incomplete_offset"] == 2


def test_returned_card_with_source_error_still_marks_overall_run_partial(monkeypatch):
    offline_runner(monkeypatch, count=1)

    def scan(card, *a, stats=None, **kw):
        stats["pc_error"] += 1
        return FairValue(), []

    monkeypatch.setattr(scanner, "scan_card", scan)
    _, _, _, stats, aborted = scanner.run_scan(log=lambda *a: None)
    assert aborted
    assert stats["selection_cards_completed"] == 1
    assert stats["selection_first_incomplete_offset"] == 0


@pytest.mark.parametrize("cfg", [
    {"max_cards": False}, {"max_cards": 0}, {"max_cards": 1.5},
    {"card_offset": True}, {"card_offset": -1}, {"card_offset": 6},
])
def test_invalid_batch_configuration_fails_before_client_creation(monkeypatch, cfg):
    offline_runner(monkeypatch)
    monkeypatch.setattr(scanner, "EbayClient", lambda: pytest.fail("client created"))
    with pytest.raises(ValueError):
        scanner.run_scan(config=cfg, log=lambda *a: None)


def test_empty_batch_does_not_contact_sources_or_create_client(monkeypatch):
    offline_runner(monkeypatch, count=2)
    monkeypatch.setattr(scanner, "EbayClient", lambda: pytest.fail("client created"))
    _, _, _, stats, aborted = scanner.run_scan(config={"card_offset": 2}, log=lambda *a: None)
    assert not aborted
    assert stats["selection_cards_scheduled"] == stats["selection_cards_attempted"] == 0
    assert stats["selection_cards_deferred"] == 2


def test_report_metadata_does_not_invent_coverage_for_legacy_payload():
    payload = report.scan_payload([], 3, policy_config(), funnel={"cards": 3})
    assert "selection" not in payload["meta"]


def test_report_metadata_exposes_typed_selection_without_false_eligibility(monkeypatch):
    offline_runner(monkeypatch)
    cfg = policy_config({"max_cards": 2, "card_offset": 1})
    _, _, _, stats, aborted = scanner.run_scan(config=cfg, log=lambda *a: None)
    selection = report.scan_payload([], 5, cfg, funnel=stats, aborted=aborted)["meta"]["selection"]
    assert selection["scope_limited"] is True
    assert selection["max_cards"] == 2
    assert selection["first_incomplete_offset"] is None
    assert selection["cards_deferred"] == 3
    assert "não um checkpoint" in selection["offset_note"]
    assert all("eligible" not in key for key in selection)


def test_cli_batch_preserves_last_complete_json(monkeypatch, tmp_path, capsys):
    _, seen = offline_runner(monkeypatch)
    out = tmp_path / "last.json"
    out.write_text("previous complete", encoding="utf-8")
    monkeypatch.setattr(main, "_load_config", lambda *a: policy_config())
    assert main.main(["--max-cards", "2", "--card-offset", "1", "--out", str(out)]) == 0
    assert seen == ["1", "2"]
    assert out.read_text(encoding="utf-8") == "previous complete"
    payload = json.loads((tmp_path / "last.batch.json").read_text(encoding="utf-8"))
    assert payload["meta"]["aborted"] is False
    assert payload["meta"]["selection"]["scope_limited"] is True
    assert payload["meta"]["selection"]["cards_scheduled"] == 2
    assert "LOTE LIMITADO" in capsys.readouterr().out


def test_cli_aborted_batch_uses_aborted_suffix_before_batch(monkeypatch, tmp_path):
    offline_runner(monkeypatch)
    out = tmp_path / "last.json"

    def scan(*a, **kw):
        raise EbayBudgetExceeded("synthetic")

    monkeypatch.setattr(scanner, "scan_card", scan)
    monkeypatch.setattr(main, "_load_config", lambda *a: policy_config())
    assert main.main(["--max-cards", "2", "--out", str(out)]) == 1
    assert not out.exists()
    assert (tmp_path / "last.aborted.json").exists()
    assert not (tmp_path / "last.batch.json").exists()


def test_cli_limited_batch_preserves_last_complete_csv(monkeypatch, tmp_path):
    cards, _ = offline_runner(monkeypatch)
    synthetic_listing = Listing(
        "synthetic", "Synthetic fixture PSA 10", 1, 0, "USD", "FIXED_PRICE",
        "Graded", 100, 100, "https://example.com/synthetic-listing")
    opp = Opportunity(cards[0], synthetic_listing, "PSA 10", 1, 0, 0, "D",
                      0, 0, 0, verdict="REVISAR")
    monkeypatch.setattr(scanner, "scan_card", lambda *a, **kw: (FairValue(), [opp]))
    monkeypatch.setattr(main, "_load_config", lambda *a: policy_config())
    csv = tmp_path / "last.csv"
    csv.write_text("previous complete csv", encoding="utf-8")
    assert main.main(["--max-cards", "1", "--csv", str(csv),
                      "--out", str(tmp_path / "last.json")]) == 0
    assert csv.read_text(encoding="utf-8") == "previous complete csv"
    assert (tmp_path / "last.batch.csv").exists()


@pytest.mark.parametrize("args", [["--max-cards", "0"], ["--card-offset", "-1"]])
def test_cli_invalid_batch_is_rejected_before_runner(monkeypatch, args):
    monkeypatch.setattr(main, "_load_config", lambda *a: policy_config())
    monkeypatch.setattr(scanner, "run_scan", lambda **kw: pytest.fail("runner called"))
    with pytest.raises(SystemExit) as exc:
        main.main(args)
    assert exc.value.code == 2
