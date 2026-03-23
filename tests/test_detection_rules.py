"""Unit tests for Sigma detection rules — no mocking, no real AWS."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from agents.detection import _match_rule, load_sigma_rules
from shared.models import NormalizedEvent


def _load_rule(filename: str) -> dict:
    path = Path("detection_rules") / filename
    with open(path) as f:
        return yaml.safe_load(f)


def _load_fixture(filename: str) -> dict:
    path = Path("tests/fixtures") / filename
    with open(path) as f:
        return json.load(f)


def _ct_event(fixture_file: str, **overrides) -> NormalizedEvent:
    raw = _load_fixture(fixture_file)
    ui = raw.get("userIdentity", {})
    ts = datetime.fromisoformat(raw["eventTime"].replace("Z", "+00:00"))
    data = dict(
        tenant_id="test",
        timestamp=ts,
        source="cloudtrail",
        user=ui.get("userName") or "root",
        user_type=ui.get("type", "IAMUser"),
        ip=raw.get("sourceIPAddress", "1.2.3.4"),
        action=raw.get("eventName", "unknown"),
        metadata=raw,
    )
    data.update(overrides)
    return NormalizedEvent(**data)


def test_brute_force_rule_loads():
    rule = _load_rule("brute_force_login.yaml")
    assert rule["match_type"] == "threshold"
    assert "T1110" in " ".join(rule.get("tags", [])).upper()


def test_privilege_escalation_fires():
    rule = _load_rule("privilege_escalation.yaml")
    event = _ct_event("cloudtrail_privilege_escalation.json")
    assert _match_rule(rule, event)


def test_privilege_escalation_no_fire_on_read():
    rule = _load_rule("privilege_escalation.yaml")
    event = _ct_event("cloudtrail_privilege_escalation.json")
    event = event.model_copy(update={"action": "GetUser"})
    assert not _match_rule(rule, event)


def test_root_account_usage_fires():
    rule = _load_rule("root_account_usage.yaml")
    event = _ct_event("cloudtrail_root_usage.json")
    assert _match_rule(rule, event)


def test_root_account_usage_no_fire_for_iam():
    rule = _load_rule("root_account_usage.yaml")
    event = _ct_event("cloudtrail_root_usage.json")
    event = event.model_copy(update={"user_type": "IAMUser"})
    assert not _match_rule(rule, event)


def test_unusual_hours_fires_at_3am():
    rule = _load_rule("unusual_access_hours.yaml")
    event = _ct_event("cloudtrail_unusual_hours.json")
    assert event.timestamp.hour == 3
    assert _match_rule(rule, event)


def test_unusual_hours_no_fire_at_noon():
    rule = _load_rule("unusual_access_hours.yaml")
    event = _ct_event("cloudtrail_unusual_hours.json")
    event = event.model_copy(update={"timestamp": event.timestamp.replace(hour=14)})
    assert not _match_rule(rule, event)


def test_new_location_fires_when_flag_set():
    rule = _load_rule("new_location_login.yaml")
    event = _ct_event("cloudtrail_new_location.json", is_new_location=True)
    assert _match_rule(rule, event)


def test_new_location_no_fire_when_known():
    rule = _load_rule("new_location_login.yaml")
    event = _ct_event("cloudtrail_new_location.json", is_new_location=False)
    assert not _match_rule(rule, event)


def test_syslog_auth_failure_fires():
    rule = _load_rule("syslog_auth_failure.yaml")
    event = NormalizedEvent(
        tenant_id="test",
        timestamp=datetime.now(timezone.utc),
        source="syslog",
        user="alice",
        ip="1.2.3.4",
        action="sshd",
    )
    assert _match_rule(rule, event)


def test_syslog_rule_no_fire_on_cloudtrail():
    rule = _load_rule("syslog_auth_failure.yaml")
    event = NormalizedEvent(
        tenant_id="test",
        timestamp=datetime.now(timezone.utc),
        source="cloudtrail",
        user="alice",
        ip="1.2.3.4",
        action="sshd",
    )
    assert not _match_rule(rule, event)


def test_cloudtrail_rule_no_fire_on_syslog():
    rule = _load_rule("root_account_usage.yaml")
    event = NormalizedEvent(
        tenant_id="test",
        timestamp=datetime.now(timezone.utc),
        source="syslog",
        user="root",
        user_type="Root",
        ip="1.2.3.4",
        action="sudo",
    )
    assert not _match_rule(rule, event)


def test_all_rules_load():
    rules = load_sigma_rules("detection_rules")
    assert len(rules) >= 7
    for rule in rules:
        assert "title" in rule
        assert "detection" in rule


def test_risk_score_root_multiplier():
    """Root account should get 4x risk (priv=2.0 × asset=2.0)."""
    from agents.detection import SEVERITY_BASE
    from shared.config import settings
    base = SEVERITY_BASE["critical"]
    score = base * settings.RISK_PRIVILEGE_HIGH * settings.RISK_ASSET_CRITICAL
    assert score == 40.0
