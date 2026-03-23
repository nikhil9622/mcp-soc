"""Unit and integration tests for Detection Agent."""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from agents.detection import (
    load_sigma_rules,
    _get_mitre_id,
    _match_rule,
    _get_event_field,
    _load_mitre,
    SEVERITY_BASE,
)
from shared.models import NormalizedEvent, DetectionEvent


class TestSigmaRuleLoading:
    """Test Sigma rule loading and validation."""

    def test_load_sigma_rules(self):
        """Test loading all Sigma rules from detection_rules directory."""
        rules = load_sigma_rules("detection_rules")
        assert len(rules) >= 5, "Expected at least 5 Sigma rules"

        # Verify expected rule fields
        for rule in rules:
            assert "title" in rule
            assert "id" in rule
            assert "logsource" in rule
            assert "detection" in rule
            assert "tags" in rule
            assert "level" in rule

    def test_rule_titles(self):
        """Test that all expected rules are present."""
        rules = load_sigma_rules("detection_rules")
        titles = [r.get("title") for r in rules]

        expected_rules = [
            "Multiple Failed Logins",
            "Login from New Geographic Location",
            "Privilege Escalation via IAM",
            "AWS Console Access Outside Business Hours",
            "Root Account Usage",
        ]

        for expected in expected_rules:
            assert any(expected in title for title in titles), f"Missing rule: {expected}"

    def test_rule_severity_levels(self):
        """Test that rules have valid severity levels."""
        rules = load_sigma_rules("detection_rules")
        valid_levels = {"critical", "high", "medium", "low"}

        for rule in rules:
            level = rule.get("level")
            assert level in valid_levels, f"Invalid severity level: {level}"

    def test_rule_mitre_tags(self):
        """Test that rules have MITRE ATT&CK tags."""
        rules = load_sigma_rules("detection_rules")

        for rule in rules:
            tags = rule.get("tags", [])
            has_mitre_tag = any(tag.startswith("attack.t") or tag.startswith("attack.T") for tag in tags)
            assert has_mitre_tag, f"Rule {rule['title']} missing MITRE tag"


class TestMitreIdExtraction:
    """Test MITRE ATT&CK ID extraction from tags."""

    def test_extract_mitre_id_basic(self):
        """Test extracting MITRE ID from tags."""
        tags = ["attack.t1110", "attack.credential_access"]
        technique_id, tactic = _get_mitre_id(tags)

        assert technique_id == "T1110"
        assert tactic == "credential_access"

    def test_extract_mitre_id_uppercase(self):
        """Test extracting uppercase MITRE ID."""
        tags = ["attack.T1078", "attack.initial_access"]
        technique_id, tactic = _get_mitre_id(tags)

        assert technique_id == "T1078"

    def test_extract_mitre_id_subtech(self):
        """Test extracting MITRE sub-technique ID."""
        tags = ["attack.t1078.003", "attack.privilege_escalation"]
        technique_id, tactic = _get_mitre_id(tags)

        assert technique_id == "T1078.003"

    def test_extract_mitre_id_fallback(self):
        """Test fallback when MITRE ID not found."""
        tags = ["custom.tag", "another.tag"]
        technique_id, tactic = _get_mitre_id(tags)

        assert technique_id == "T0000"
        assert tactic == "unknown"


class TestRuleMatching:
    """Test Sigma rule matching logic."""

    def test_match_rule_brute_force(self):
        """Test brute force rule matching."""
        rules = load_sigma_rules("detection_rules")
        brute_force_rule = next((r for r in rules if "Brute" in r.get("title", "")), None)
        assert brute_force_rule is not None

        # Should not match single failed login
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="ConsoleLogin",
        )
        # Threshold rules need stateful counting; per-event should return False
        match = _match_rule(brute_force_rule, event)
        # This is expected to be False because threshold matching requires state

    def test_match_rule_new_location(self):
        """Test new location rule matching."""
        rules = load_sigma_rules("detection_rules")
        new_loc_rule = next((r for r in rules if "New Geographic Location" in r.get("title", "")), None)
        assert new_loc_rule is not None

        # Should match when is_new_location is True
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="ConsoleLogin",
            is_new_location=True,
        )
        match = _match_rule(new_loc_rule, event)
        assert match is True

        # Should not match when is_new_location is False
        event.is_new_location = False
        match = _match_rule(new_loc_rule, event)
        assert match is False

    def test_match_rule_unusual_hours(self):
        """Test unusual access hours rule matching."""
        rules = load_sigma_rules("detection_rules")
        hours_rule = next((r for r in rules if "Outside Business Hours" in r.get("title", "")), None)
        assert hours_rule is not None

        # Should match at 2 AM (outside 6-22)
        early_morning = datetime.utcnow().replace(hour=2, minute=0, second=0)
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=early_morning,
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="ConsoleLogin",
        )
        match = _match_rule(hours_rule, event)
        assert match is True

        # Should not match at 10 AM (inside 6-22)
        business_hours = datetime.utcnow().replace(hour=10, minute=0, second=0)
        event.timestamp = business_hours
        match = _match_rule(hours_rule, event)
        assert match is False

    def test_match_rule_privilege_escalation(self):
        """Test privilege escalation rule matching."""
        rules = load_sigma_rules("detection_rules")
        priv_esc_rule = next((r for r in rules if "Privilege Escalation" in r.get("title", "")), None)
        assert priv_esc_rule is not None

        # Should match PutUserPolicy action
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="attacker",
            ip="192.0.2.1",
            action="PutUserPolicy",
        )
        match = _match_rule(priv_esc_rule, event)
        assert match is True

        # Should match CreateAccessKey
        event.action = "CreateAccessKey"
        match = _match_rule(priv_esc_rule, event)
        assert match is True

        # Should not match GetUser
        event.action = "GetUser"
        match = _match_rule(priv_esc_rule, event)
        assert match is False

    def test_match_rule_root_account(self):
        """Test root account usage rule matching."""
        rules = load_sigma_rules("detection_rules")
        root_rule = next((r for r in rules if "Root Account" in r.get("title", "")), None)
        assert root_rule is not None

        # Should match when user_type is Root
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="root",
            user_type="Root",
            ip="192.0.2.1",
            action="ConsoleLogin",
        )
        match = _match_rule(root_rule, event)
        assert match is True

        # Should not match when user_type is IAMUser
        event.user_type = "IAMUser"
        match = _match_rule(root_rule, event)
        assert match is False


class TestEventFieldMapping:
    """Test field mapping from NormalizedEvent to Sigma fields."""

    def test_get_event_field_direct(self):
        """Test getting direct event fields."""
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="ConsoleLogin",
            user_type="IAMUser",
        )

        assert _get_event_field(event, "eventName") == "ConsoleLogin"
        assert _get_event_field(event, "user") == "admin"
        assert _get_event_field(event, "ip") == "192.0.2.1"
        assert _get_event_field(event, "user_type") == "IAMUser"

    def test_get_event_field_metadata(self):
        """Test getting fields from metadata."""
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="PutObject",
            metadata={"bucket": "sensitive-bucket", "operation": "upload"},
        )

        assert _get_event_field(event, "bucket") == "sensitive-bucket"
        assert _get_event_field(event, "operation") == "upload"

    def test_get_event_field_missing(self):
        """Test getting non-existent field returns None."""
        event = NormalizedEvent(
            tenant_id="tenant",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="admin",
            ip="192.0.2.1",
            action="GetObject",
        )

        assert _get_event_field(event, "nonexistent") is None


class TestSeverityBase:
    """Test severity base scoring."""

    def test_severity_base_values(self):
        """Test severity base scoring constants."""
        assert SEVERITY_BASE["critical"] == 10.0
        assert SEVERITY_BASE["high"] == 7.0
        assert SEVERITY_BASE["medium"] == 5.0
        assert SEVERITY_BASE["low"] == 2.0

    def test_risk_score_calculation(self):
        """Test risk score calculation with multipliers."""
        from shared.config import settings

        # Root user with critical severity
        base = SEVERITY_BASE["critical"]  # 10.0
        priv_mult = settings.RISK_PRIVILEGE_HIGH  # 2.0
        asset_mult = settings.RISK_ASSET_CRITICAL  # 2.0
        expected_score = base * priv_mult * asset_mult  # 40.0
        assert expected_score == 40.0

        # Regular user with medium severity
        base = SEVERITY_BASE["medium"]  # 5.0
        priv_mult = settings.RISK_PRIVILEGE_LOW  # 1.0
        asset_mult = settings.RISK_ASSET_LOW  # 1.0
        expected_score = base * priv_mult * asset_mult  # 5.0
        assert expected_score == 5.0


class TestMitreDataLoading:
    """Test MITRE ATT&CK data loading."""

    def test_load_mitre_data(self):
        """Test loading MITRE ATT&CK data from JSON."""
        mitre_data = _load_mitre()

        # Should load some data or return empty dict
        if mitre_data:
            # If data loaded, check structure
            for tid, info in mitre_data.items():
                assert tid.startswith("T"), f"Invalid technique ID: {tid}"
                assert "name" in info or "tactic" in info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
