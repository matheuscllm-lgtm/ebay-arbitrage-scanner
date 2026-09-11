"""Three independent axes for long-term PSA 10 screening, never an order to buy.

Private, sourced thesis profiles are supplied explicitly by the operator. Existing
LP scores, raw price multiples, asking prices and price forecasts are not inputs.
Only ``apply`` mutates an Opportunity; ``assess`` is deterministic for a given day.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from urllib.parse import urlsplit

import yaml


SIGNALS = ("demand", "collectibility", "supply", "resilience")
DIRECTIONS = frozenset(("supportive", "neutral", "adverse"))
MIN_MARGIN_PERCENT = 20
DEFAULTS = {"min_sales_90d": 9, "min_active_months_90d": 2,
            "max_thesis_age_days": 180}


def identity_key(name, set_name, number, language, grade="PSA 10", variants=()):
    """Collision-safe exact identity; no language, edition or variant fallback."""
    return json.dumps([str(name).strip(), str(set_name).strip(), str(number).strip(),
                       str(language).strip(), str(grade).strip(),
                       sorted(str(v).strip() for v in variants)],
                      ensure_ascii=False, separators=(",", ":"))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _source(value):
    if not _text(value) or any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password)
    except ValueError:
        return False


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _valid_signal(signal):
    return (isinstance(signal, dict) and isinstance(signal.get("direction"), str)
            and signal["direction"] in DIRECTIONS
            and _source(signal.get("source")) and _day(signal.get("as_of")) is not None
            and _text(signal.get("reason")))


def load_profiles(path):
    """Load an explicit private YAML file, failing loudly without echoing its data.

Schema: ``version: 1``, ``cards: [...]``. Each card has name, set, number, language,
grade (PSA 10), an explicit variants list, invalidation, and all four sourced
signals. Freshness and future dates are evaluated by ``assess`` for its own day.
No file is generated and no prices are fetched or inferred.
"""
    with open(path, encoding="utf-8") as handle:
        try:
            document = yaml.safe_load(handle)
        except yaml.YAMLError:
            raise ValueError("Invalid thesis YAML; private contents omitted") from None
    if (not isinstance(document, dict) or type(document.get("version")) is not int
            or document["version"] != 1 or not isinstance(document.get("cards"), list)):
        raise ValueError("Invalid thesis document: version 1 and cards list required")
    profiles = {}
    for index, raw in enumerate(document["cards"]):
        field = f"cards[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid thesis field: {field}")
        for key in ("name", "set", "language", "invalidation"):
            if not _text(raw.get(key)):
                raise ValueError(f"Invalid thesis field: {field}.{key}")
        number = raw.get("number")
        if not (_text(number) or type(number) is int and number >= 0):
            raise ValueError(f"Invalid thesis field: {field}.number")
        if raw.get("grade") != "PSA 10":
            raise ValueError(f"Invalid thesis field: {field}.grade must be PSA 10")
        variants = raw.get("variants")
        if (not isinstance(variants, list) or any(not _text(v) or v.strip() == "*" for v in variants)
                or len({v.strip() for v in variants}) != len(variants)):
            raise ValueError(f"Invalid thesis field: {field}.variants must be an explicit unique list")
        signals = raw.get("signals")
        if not isinstance(signals, dict) or set(signals) != set(SIGNALS):
            raise ValueError(f"Invalid thesis field: {field}.signals requires all four axes")
        for name in SIGNALS:
            if not _valid_signal(signals[name]):
                raise ValueError(f"Invalid thesis field: {field}.signals.{name}")
        profile = deepcopy(raw)
        # PyYAML can decode an unquoted ISO date as datetime.date. Keep runtime
        # profiles JSON-safe without changing the date that the operator supplied.
        for name in SIGNALS:
            profile["signals"][name]["as_of"] = _day(signals[name]["as_of"]).isoformat()
        key = identity_key(raw["name"], raw["set"], number, raw["language"],
                           raw["grade"], variants)
        if key in profiles:
            raise ValueError(f"Duplicate thesis identity at {field}; private contents omitted")
        profiles[key] = profile
    return profiles


def _thesis(opp, config, today, settings):
    card = opp.card
    strategy = opp.strategy or {}
    key = identity_key(card.name, card.set_name, card.number, card.language,
                       opp.grade, strategy.get("variant") or ())
    profiles = config.get("thesis_profiles") or {}
    profile = profiles.get(key) if isinstance(profiles, dict) else None
    raw_signals = profile.get("signals", {}) if isinstance(profile, dict) else {}
    if not isinstance(raw_signals, dict):
        raw_signals = {}
    observed, missing, signals = {}, [], {}
    for name in SIGNALS:
        signal = raw_signals.get(name)
        if not _valid_signal(signal):
            missing.append(f"thesis-{name}-unconfirmed")
            signals[name] = {"status": "unconfirmed"}
            continue
        as_of = _day(signal["as_of"])
        age = (today - as_of).days
        copied = deepcopy(signal)
        copied["as_of"] = as_of.isoformat()
        if age < 0 or age > settings["max_thesis_age_days"]:
            reason = "future-dated" if age < 0 else "stale"
            missing.append(f"thesis-{name}-{reason}")
            copied["status"] = reason
        else:
            observed[name] = signal["direction"]
            copied["status"] = "confirmed"
        signals[name] = copied
    invalidation = profile.get("invalidation") if isinstance(profile, dict) else None
    if not _text(invalidation):
        invalidation = None
        missing.append("thesis-invalidation-unconfirmed")
    supportive = sum(v == "supportive" for v in observed.values())
    adverse = sum(v == "adverse" for v in observed.values())
    if missing:
        status = "unconfirmed"
    elif observed.get("demand") == "adverse" or adverse >= 2:
        status = "unfavorable"
    elif supportive >= 3 and adverse == 0 and observed.get("demand") == "supportive":
        status = "favorable"
    else:
        status = "neutral"
    return {"status": status, "coverage": f"{len(observed)}/{len(SIGNALS)}",
            "provenance": "operator-supplied-sourced-profile",
            "independently_verified_by_scanner": False,
            "supportive_signals": supportive, "adverse_signals": adverse,
            "signals": signals, "invalidation": invalidation,
            "missing": missing, "max_age_days": settings["max_thesis_age_days"]}


def _evidence(opp, settings):
    strategy = opp.strategy or {}
    source = strategy.get("resale_evidence") or {}
    if not isinstance(source, dict):
        source = {}
    sales = source.get("sales_90d")
    months = source.get("active_months_90d")
    price = _number(source.get("price_exact"))
    reasons = []
    if price is None or price <= 0:
        reasons.append("evidence-sale-price-unconfirmed")
    if type(sales) is not int or sales < 0:
        sales = None
        reasons.append("evidence-recent-sales-unconfirmed")
    elif sales < settings["min_sales_90d"]:
        reasons.append("evidence-recent-sales-below-minimum")
    if type(months) is not int or months < 0:
        months = None
        reasons.append("evidence-active-months-unconfirmed")
    elif months < settings["min_active_months_90d"]:
        reasons.append("evidence-activity-not-distributed")
    policy_reviews = list(strategy.get("review_reasons") or [])
    if policy_reviews:
        reasons.append("evidence-policy-review-required")
    return {"status": "insufficient" if reasons else "adequate",
            "sales_90d": sales, "active_months_90d": months,
            "observed_sales_per_month": sales / 3 if sales is not None else None,
            "min_sales_90d": settings["min_sales_90d"],
            "min_active_months_90d": settings["min_active_months_90d"],
            "sale_price_source": "resale_evidence", "policy_reviews": policy_reviews,
            "reasons": reasons}


def _entry(opp):
    strategy = opp.strategy or {}
    gate = strategy.get("economic_gate") or {}
    margin = _number(gate.get("gross_margin_percent_exact"))
    threshold = _number(gate.get("threshold"))
    total = _number(strategy.get("investment_total_exact"))
    proceeds = _number(strategy.get("net_sale_proceeds_exact"))
    reasons = []
    if gate.get("mode") != "longterm" or threshold != MIN_MARGIN_PERCENT:
        reasons.append("entry-minimum-must-be-explicit-20-percent")
    if margin is None or type(gate.get("margin_pass")) is not bool:
        reasons.append("entry-margin-unconfirmed")
    if total is None or total <= 0 or proceeds is None or proceeds <= 0:
        reasons.append("entry-all-in-or-net-proceeds-unconfirmed")
    if reasons:
        status = "unconfirmed"
    else:
        # Recheck exact arithmetic so rounded display fields and inconsistent
        # externally supplied payloads can never promote a line.
        attractive = (gate["margin_pass"] is True and margin > MIN_MARGIN_PERCENT
                      and proceeds > total)
        status = "attractive" if attractive else "unattractive"
        if not gate["margin_pass"] or margin <= MIN_MARGIN_PERCENT:
            reasons.append("entry-below-strict-20-percent-margin")
        if proceeds <= total:
            reasons.append("entry-no-current-net-safety-margin")
    return {"status": status, "min_margin_percent": MIN_MARGIN_PERCENT,
            "strictly_above": True,
            "gross_margin_percent": float(margin) if margin is not None else None,
            "gross_margin_percent_exact": str(margin) if margin is not None else None,
            "investment_total_exact": str(total) if total is not None else None,
            "net_sale_proceeds_exact": str(proceeds) if proceeds is not None else None,
            "reasons": reasons}


def assess(opp, config, today=None):
    """Return auditable axes and classification without modifying any input."""
    today = _day(today) if today is not None else datetime.now(timezone.utc).date()
    if today is None:
        raise ValueError("Invalid assessment date")
    settings = {**DEFAULTS, **(config.get("investment") or {})}
    for key in DEFAULTS:
        if type(settings[key]) is not int or settings[key] < 1:
            raise ValueError(f"Invalid investment setting: {key}")
    thesis = _thesis(opp, config, today, settings)
    evidence = _evidence(opp, settings)
    entry = _entry(opp)
    structural = list((opp.strategy or {}).get("rejection_reasons") or [])
    if opp.grade != "PSA 10" and re.match(r'^(?:PSA|BGS|CGC|TAG|SGC)\s+\d', opp.grade):
        structural.append("investment-only-PSA-10")
    elif opp.grade != "PSA 10":
        # Ambiguous/missing certification is uncertainty, not proof of another
        # grade. The structural policy already rejects raw and known exclusions.
        evidence['status'] = 'insufficient'
        evidence['reasons'].append('investment-grade-unconfirmed')
    if structural:
        classification = "REJEITAR"
    elif thesis["status"] == "unfavorable":
        classification = "REJEITAR"
    elif (thesis["status"] == "unconfirmed" or evidence["status"] != "adequate"
          or entry["status"] == "unconfirmed"):
        classification = "REVISAR"
    elif thesis["status"] == "favorable" and entry["status"] == "attractive":
        classification = "OPORTUNIDADE"
    else:
        classification = "MONITORAR"
    reasons = structural + thesis["missing"] + evidence["reasons"] + entry["reasons"]
    if thesis["status"] == "unfavorable":
        reasons.append("thesis-unfavorable")
    elif thesis["status"] == "neutral":
        reasons.append("thesis-insufficient-positive-convergence")
    if classification == "OPORTUNIDADE":
        reasons.append("three-axes-converge-not-a-purchase-order")
    return {"version": 1, "as_of_date": today.isoformat(),
            "classification": classification, "thesis": thesis,
            "entry": entry, "evidence": evidence,
            "reasons": list(dict.fromkeys(reasons)), "automatic_purchase": False}


def apply(opp, config, today=None):
    """Attach the assessment and final screening status, preserving earlier reasons."""
    assessment = assess(opp, config, today=today)
    opp.verdict = assessment["classification"]
    opp.reasons = list(dict.fromkeys(list(opp.reasons) + assessment["reasons"]))
    opp.strategy["investment_assessment"] = assessment
    return opp
