"""Synthetic private-profile and three-axis regressions; no live sources."""
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import yaml

from src import investment


TODAY = date(2026, 9, 11)


def profile(**overrides):
    result = {"name": "Examplemon", "set": "Example Set", "number": "001",
              "language": "EN", "grade": "PSA 10", "variants": [],
              "invalidation": "Demand disappears or new supply overtakes demand.",
              "signals": {name: {"direction": "supportive",
                                  "source": f"https://example.com/evidence/{name}",
                                  "as_of": TODAY.isoformat(),
                                  "reason": "Synthetic documented observation."}
                          for name in investment.SIGNALS}}
    result.update(overrides)
    return result


def setup():
    item = SimpleNamespace(card=SimpleNamespace(name="Examplemon", set_name="Example Set",
                                                number="001", language="EN"),
                           grade="PSA 10", reasons=[], verdict="APROVAR",
                           strategy={"variant": [], "rejection_reasons": [],
                                     "review_reasons": [],
                                     "resale_evidence": {"price_exact": "150",
                                                          "sales_90d": 9,
                                                          "active_months_90d": 2},
                                     "economic_gate": {"mode": "longterm", "threshold": 20,
                                                       "gross_margin_percent_exact": "50",
                                                       "margin_pass": True},
                                     "investment_total_exact": "112.50",
                                     "net_sale_proceeds_exact": "128.25"})
    key = investment.identity_key("Examplemon", "Example Set", "001", "EN")
    config = {"investment": dict(investment.DEFAULTS), "thesis_profiles": {key: profile()}}
    return item, config


def result(item, config):
    return investment.assess(item, config, today=TODAY)


def current_profile(config):
    return next(iter(config["thesis_profiles"].values()))


def test_three_confirmed_axes_classify_without_recommending_or_mutating():
    item, config = setup()
    original_item, original_config = deepcopy(item), deepcopy(config)
    assessed = result(item, config)
    assert assessed["classification"] == "OPORTUNIDADE"
    assert assessed["thesis"]["status"] == "favorable"
    assert assessed["thesis"]["independently_verified_by_scanner"] is False
    assert assessed["evidence"]["observed_sales_per_month"] == 3
    assert assessed["entry"]["min_margin_percent"] == 20
    assert assessed["automatic_purchase"] is False
    assert item == original_item and config == original_config


def test_apply_changes_only_verdict_reasons_and_assessment():
    item, config = setup()
    item.reasons = ["existing-explanation"]
    original = deepcopy(item)
    assert investment.apply(item, config, TODAY) is item
    assert item.verdict == "OPORTUNIDADE"
    assert item.reasons[0] == "existing-explanation"
    assert item.card == original.card and item.grade == original.grade
    assessment = item.strategy.pop("investment_assessment")
    assert item.strategy == original.strategy
    assert assessment["classification"] == item.verdict


@pytest.mark.parametrize("margin,passed", [("20", False), ("19.99999", False), ("20", True)])
def test_exact_twenty_percent_is_monitoring_not_opportunity(margin, passed):
    item, config = setup()
    item.strategy["economic_gate"].update(gross_margin_percent_exact=margin, margin_pass=passed)
    assert result(item, config)["classification"] == "MONITORAR"


def test_exact_unrounded_value_above_twenty_is_eligible():
    item, config = setup()
    item.strategy["economic_gate"].update(gross_margin_percent_exact="20.00001",
                                         gross_margin_percent=20)
    assert result(item, config)["classification"] == "OPORTUNIDADE"


@pytest.mark.parametrize("proceeds", ["112.50", "112.499999"])
def test_nonpositive_net_safety_margin_monitors_even_with_large_gross_margin(proceeds):
    item, config = setup()
    item.strategy["net_sale_proceeds_exact"] = proceeds
    assert result(item, config)["classification"] == "MONITORAR"


@pytest.mark.parametrize("key", ["investment_total_exact", "net_sale_proceeds_exact"])
def test_missing_exact_costs_never_approve(key):
    item, config = setup()
    del item.strategy[key]
    assert result(item, config)["classification"] == "REVISAR"


@pytest.mark.parametrize("threshold", [None, 15, 43, True])
def test_twenty_percent_is_explicit_and_not_silently_overridden(threshold):
    item, config = setup()
    item.strategy["economic_gate"]["threshold"] = threshold
    assert result(item, config)["entry"]["status"] == "unconfirmed"


@pytest.mark.parametrize("signal", investment.SIGNALS)
def test_missing_component_is_not_renormalized(signal):
    item, config = setup()
    del current_profile(config)["signals"][signal]
    assessment = result(item, config)
    assert assessment["classification"] == "REVISAR"
    assert assessment["thesis"]["coverage"] == "3/4"


@pytest.mark.parametrize("age,expected", [(180, "OPORTUNIDADE"), (181, "REVISAR"), (-1, "REVISAR")])
def test_profile_freshness_boundary_and_future_date(age, expected):
    item, config = setup()
    current_profile(config)["signals"]["supply"]["as_of"] = (TODAY - timedelta(days=age)).isoformat()
    assert result(item, config)["classification"] == expected


def test_missing_profile_never_borrows_legacy_score_or_price_proxy():
    item, config = setup()
    config["thesis_profiles"] = {}
    item.longterm_profile = 100
    item.longterm_tier = "LP1"
    item.longterm_signals = {"heavy_reprint": False, "psa10_col": 9999,
                             "months_of_supply": 0.1, "age_years": 25}
    assessed = result(item, config)
    assert assessed["classification"] == "REVISAR"
    assert assessed["thesis"]["coverage"] == "0/4"


@pytest.mark.parametrize("field,value", [("language", "JP"), ("number", "002"),
                                          ("set_name", "Other Set")])
def test_exact_identity_cannot_borrow_another_profile(field, value):
    item, config = setup()
    setattr(item.card, field, value)
    assert result(item, config)["thesis"]["status"] == "unconfirmed"


def test_variant_profile_never_applies_to_unspecified_printing():
    item, config = setup()
    item.strategy["variant"] = ["reverse"]
    assert result(item, config)["classification"] == "REVISAR"


def test_identity_key_is_collision_safe_and_variant_order_independent():
    key = investment.identity_key
    assert key("A|B", "C", "1", "EN") != key("A", "B|C", "1", "EN")
    assert key("A", "B", "1", "EN", variants=["a", "b"]) == key("A", "B", "1", "EN", variants=["b", "a"])


@pytest.mark.parametrize("directions,expected", [
    ({"resilience": "neutral"}, "OPORTUNIDADE"),
    ({"demand": "neutral"}, "MONITORAR"),
    ({"collectibility": "neutral", "supply": "neutral"}, "MONITORAR"),
    ({"supply": "adverse"}, "MONITORAR"),
    ({"demand": "adverse"}, "REJEITAR"),
    ({"supply": "adverse", "resilience": "adverse"}, "REJEITAR"),
])
def test_positive_convergence_requires_demand_and_no_adverse_signal(directions, expected):
    item, config = setup()
    for name, direction in directions.items():
        current_profile(config)["signals"][name]["direction"] = direction
    assert result(item, config)["classification"] == expected


@pytest.mark.parametrize("field,value", [("sales_90d", 8), ("sales_90d", None),
                                          ("sales_90d", True), ("active_months_90d", 1),
                                          ("active_months_90d", None), ("price_exact", None)])
def test_insufficient_exact_recent_evidence_never_approves(field, value):
    item, config = setup()
    item.strategy["resale_evidence"][field] = value
    assert result(item, config)["classification"] == "REVISAR"


def test_liquidity_reads_all_sales_count_not_truncated_median_sample():
    item, config = setup()
    item.strategy["resale_evidence"].update(sales_90d=30, n_used=3,
                                            sales=[{"price": 150}] * 3)
    assessment = result(item, config)
    assert assessment["evidence"]["observed_sales_per_month"] == 10
    assert assessment["classification"] == "OPORTUNIDADE"


def test_quote_only_reference_does_not_replace_sales_evidence():
    item, config = setup()
    item.strategy["resale_evidence"] = {}
    item.fair_value, item.median_ask = 150, 150
    assert result(item, config)["classification"] == "REVISAR"


def test_structural_rejection_takes_precedence_and_is_preserved():
    item, config = setup()
    item.strategy["rejection_reasons"] = ["titulo-certificado-condicao-ungraded"]
    config["thesis_profiles"] = {}
    assessed = result(item, config)
    assert assessed["classification"] == "REJEITAR"
    assert "titulo-certificado-condicao-ungraded" in assessed["reasons"]


def test_suspicious_margin_requires_review_not_fraud_assertion():
    item, config = setup()
    item.strategy["review_reasons"] = ["retorno-elevado-conferir-identidade"]
    assessed = result(item, config)
    assert assessed["classification"] == "REVISAR"
    assert assessed["evidence"]["policy_reviews"] == item.strategy["review_reasons"]
    assert "fraud" not in str(assessed).lower()


def test_non_psa10_is_outside_investment_scope():
    item, config = setup()
    item.grade = "PSA 9"
    assert result(item, config)["classification"] == "REJEITAR"


def write_profiles(tmp_path, cards=None, version=1):
    path = tmp_path / "private-theses.yaml"
    path.write_text(yaml.safe_dump({"version": version, "cards": [profile()] if cards is None else cards}), encoding="utf-8")
    return path


def test_loader_reads_explicit_file_and_normalizes_yaml_dates(tmp_path):
    p = profile()
    p["signals"]["supply"]["as_of"] = TODAY
    loaded = investment.load_profiles(write_profiles(tmp_path, [p]))
    assert len(loaded) == 1
    assert next(iter(loaded.values()))["signals"]["supply"]["as_of"] == TODAY.isoformat()
    item, config = setup()
    config["thesis_profiles"] = loaded
    assert result(item, config)["classification"] == "OPORTUNIDADE"


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("variants"), lambda p: p.update(variants=["*"]),
    lambda p: p.update(variants=["reverse", "reverse"]),
    lambda p: p.update(grade="PSA 9"), lambda p: p.update(invalidation=""),
    lambda p: p["signals"].pop("supply"),
    lambda p: p["signals"]["demand"].update(direction="optimistic"),
    lambda p: p["signals"]["demand"].update(direction=["supportive"]),
    lambda p: p["signals"]["demand"].update(source="http://example.com"),
    lambda p: p["signals"]["demand"].update(source="https://invalid host/path"),
    lambda p: p["signals"]["demand"].update(source="https://user:secret@example.com"),
    lambda p: p["signals"]["demand"].update(as_of="not-a-date"),
    lambda p: p["signals"]["demand"].update(reason=""),
])
def test_malformed_profiles_fail_without_echoing_private_targets(tmp_path, mutate):
    p = profile()
    mutate(p)
    with pytest.raises(ValueError) as caught:
        investment.load_profiles(write_profiles(tmp_path, [p]))
    assert "Examplemon" not in str(caught.value)
    assert "secret" not in str(caught.value)


def test_duplicate_exact_identity_fails_loudly(tmp_path):
    with pytest.raises(ValueError, match="Duplicate thesis identity"):
        investment.load_profiles(write_profiles(tmp_path, [profile(), profile()]))


def test_malformed_runtime_signal_stays_unconfirmed():
    item, config = setup()
    current_profile(config)["signals"]["demand"]["direction"] = ["supportive"]
    assert result(item, config)["classification"] == "REVISAR"


def test_same_card_in_distinct_languages_is_not_a_duplicate(tmp_path):
    assert len(investment.load_profiles(write_profiles(tmp_path, [profile(), profile(language="JP")]))) == 2


@pytest.mark.parametrize("version", [None, 2, True, "1"])
def test_invalid_schema_version_fails(tmp_path, version):
    with pytest.raises(ValueError):
        investment.load_profiles(write_profiles(tmp_path, version=version))


def test_missing_requested_file_is_not_silently_ignored(tmp_path):
    with pytest.raises(FileNotFoundError):
        investment.load_profiles(tmp_path / "not-created.yaml")


def test_invalid_yaml_does_not_leak_private_contents(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("private-target: [broken\n", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        investment.load_profiles(path)
    assert "private-target" not in str(caught.value)


@pytest.mark.parametrize("setting", investment.DEFAULTS)
def test_invalid_classifier_settings_fail_instead_of_loosening(setting):
    item, config = setup()
    config["investment"][setting] = 0
    with pytest.raises(ValueError):
        result(item, config)
