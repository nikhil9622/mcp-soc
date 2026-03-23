"""Unit tests for all MCP SOC data models (Pydantic schemas)."""

import pytest
from datetime import datetime
from uuid import uuid4

from shared.models import (
    NormalizedEvent,
    DetectionEvent,
    Incident,
    IncidentSummary,
    Alert,
    User,
    SyslogPayload,
    CloudTrailPayload,
    FeedbackRequest,
)


class TestNormalizedEvent:
    """Test NormalizedEvent schema validation and serialization."""

    def test_normalized_event_minimal(self):
        """Test creating NormalizedEvent with minimal required fields."""
        event = NormalizedEvent(
            tenant_id="tenant-123",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="john.doe@example.com",
            ip="192.0.2.1",
            action="ConsoleLogin",
        )
        assert event.tenant_id == "tenant-123"
        assert event.source == "cloudtrail"
        assert event.user == "john.doe@example.com"
        assert event.ip == "192.0.2.1"
        assert event.action == "ConsoleLogin"
        assert event.event_id is not None  # Auto-generated
        assert event.metadata == {}

    def test_normalized_event_with_geolocation(self):
        """Test NormalizedEvent with geolocation data."""
        event = NormalizedEvent(
            tenant_id="tenant-456",
            timestamp=datetime.utcnow(),
            source="syslog",
            user="admin",
            ip="10.0.0.5",
            action="sudo",
            region="us-east-1",
            city="New York",
            country="US",
            is_new_location=True,
        )
        assert event.region == "us-east-1"
        assert event.city == "New York"
        assert event.country == "US"
        assert event.is_new_location is True

    def test_normalized_event_with_metadata(self):
        """Test NormalizedEvent with arbitrary metadata."""
        event = NormalizedEvent(
            tenant_id="tenant-789",
            timestamp=datetime.utcnow(),
            source="app",
            user="service-account",
            ip="192.168.1.100",
            action="api_call",
            metadata={"endpoint": "/api/users", "method": "POST", "status": 201},
        )
        assert event.metadata["endpoint"] == "/api/users"
        assert event.metadata["method"] == "POST"

    def test_normalized_event_source_validation(self):
        """Test that invalid source values are rejected."""
        with pytest.raises(ValueError):
            NormalizedEvent(
                tenant_id="tenant-invalid",
                timestamp=datetime.utcnow(),
                source="invalid_source",  # Not in allowed Literal
                user="user",
                ip="192.0.2.1",
                action="test",
            )

    def test_normalized_event_serialization(self):
        """Test serialization to JSON."""
        event = NormalizedEvent(
            tenant_id="tenant-ser",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="user@example.com",
            ip="203.0.113.5",
            action="PutObject",
        )
        json_data = event.model_dump_json()
        assert isinstance(json_data, str)
        assert "tenant-ser" in json_data
        assert "cloudtrail" in json_data


class TestDetectionEvent:
    """Test DetectionEvent schema validation and serialization."""

    def test_detection_event_minimal(self):
        """Test creating DetectionEvent with required fields."""
        event = DetectionEvent(
            tenant_id="tenant-123",
            event_id="event-456",
            rule_id="sigma-rule-1",
            rule_name="Brute Force Logins",
            mitre_technique_id="T1110",
            mitre_tactic="Credential Access",
            severity="high",
            risk_score=85.5,
        )
        assert event.detection_id is not None
        assert event.tenant_id == "tenant-123"
        assert event.rule_id == "sigma-rule-1"
        assert event.mitre_technique_id == "T1110"
        assert event.severity == "high"
        assert event.risk_score == 85.5
        assert event.detected_at is not None

    def test_detection_event_severity_validation(self):
        """Test severity level validation."""
        for severity in ["critical", "high", "medium", "low"]:
            event = DetectionEvent(
                tenant_id="tenant",
                event_id="event",
                rule_id="rule",
                rule_name="Test Rule",
                mitre_technique_id="T0000",
                mitre_tactic="Test",
                severity=severity,
                risk_score=50.0,
            )
            assert event.severity == severity

    def test_detection_event_risk_score_range(self):
        """Test risk score bounds (0-100)."""
        # Valid scores
        event = DetectionEvent(
            tenant_id="tenant",
            event_id="event",
            rule_id="rule",
            rule_name="Test",
            mitre_technique_id="T0000",
            mitre_tactic="Test",
            severity="medium",
            risk_score=0.0,
        )
        assert event.risk_score == 0.0

        event = DetectionEvent(
            tenant_id="tenant",
            event_id="event",
            rule_id="rule",
            rule_name="Test",
            mitre_technique_id="T0000",
            mitre_tactic="Test",
            severity="medium",
            risk_score=100.0,
        )
        assert event.risk_score == 100.0

    def test_detection_event_with_raw_event(self):
        """Test DetectionEvent with raw event data."""
        raw = {"eventName": "ConsoleLogin", "responseElements": {"ConsoleLogin": "Failure"}}
        event = DetectionEvent(
            tenant_id="tenant",
            event_id="event",
            rule_id="rule",
            rule_name="Test",
            mitre_technique_id="T0000",
            mitre_tactic="Test",
            severity="high",
            risk_score=75.0,
            raw_event=raw,
        )
        assert event.raw_event == raw


class TestIncident:
    """Test Incident schema validation and serialization."""

    def test_incident_minimal(self):
        """Test creating Incident with required fields."""
        incident = Incident(
            tenant_id="tenant-123",
            detection_ids=["det-1", "det-2", "det-3"],
            severity="high",
        )
        assert incident.incident_id is not None
        assert incident.tenant_id == "tenant-123"
        assert len(incident.detection_ids) == 3
        assert incident.status == "open"
        assert incident.severity == "high"
        assert incident.created_at is not None
        assert incident.entities == {}  # Default

    def test_incident_with_entities(self):
        """Test Incident with correlated entities."""
        incident = Incident(
            tenant_id="tenant-123",
            detection_ids=["det-1", "det-2"],
            severity="critical",
            entities={
                "users": ["admin", "root"],
                "ips": ["192.0.2.1", "192.0.2.2"],
            },
        )
        assert incident.entities["users"] == ["admin", "root"]
        assert incident.entities["ips"] == ["192.0.2.1", "192.0.2.2"]

    def test_incident_status_transitions(self):
        """Test all valid status values."""
        for status in ["open", "investigating", "closed"]:
            incident = Incident(
                tenant_id="tenant",
                detection_ids=["det-1"],
                severity="medium",
                status=status,
            )
            assert incident.status == status

    def test_incident_with_summary(self):
        """Test Incident with associated IncidentSummary."""
        summary = IncidentSummary(
            summary="Multiple failed logins detected",
            what_happened="5 failed login attempts from IP 192.0.2.1",
            why_suspicious="Exceeds threshold for brute force detection",
            impact="Potential account compromise",
            recommended_action="Reset password and enable MFA",
            severity="high",
        )
        incident = Incident(
            tenant_id="tenant",
            detection_ids=["det-1"],
            severity="high",
            summary=summary,
        )
        assert incident.summary is not None
        assert incident.summary.what_happened == "5 failed login attempts from IP 192.0.2.1"

    def test_incident_updated_at_tracking(self):
        """Test that updated_at field exists and is tracked."""
        incident = Incident(
            tenant_id="tenant",
            detection_ids=["det-1"],
            severity="medium",
        )
        assert incident.updated_at is not None
        assert incident.created_at is not None


class TestIncidentSummary:
    """Test IncidentSummary schema validation."""

    def test_incident_summary_minimal(self):
        """Test creating IncidentSummary with all required fields."""
        summary = IncidentSummary(
            summary="High-risk incident detected",
            what_happened="User 'admin' logged in from new location",
            why_suspicious="First login from this geographic location",
            impact="Potential unauthorized access",
            recommended_action="Verify user identity and review account activity",
            severity="high",
        )
        assert summary.summary == "High-risk incident detected"
        assert summary.severity == "high"

    def test_incident_summary_all_severities(self):
        """Test all severity levels."""
        for severity in ["critical", "high", "medium", "low"]:
            summary = IncidentSummary(
                summary="Test",
                what_happened="Test",
                why_suspicious="Test",
                impact="Test",
                recommended_action="Test",
                severity=severity,
            )
            assert summary.severity == severity

    def test_incident_summary_structured_output_schema(self):
        """Test that IncidentSummary matches Claude Structured Output schema."""
        summary = IncidentSummary(
            summary="Privilege escalation attempt",
            what_happened="User escalated to root via sudo",
            why_suspicious="Unusual for this user account",
            impact="Full system compromise possible",
            recommended_action="Disable account and investigate",
            severity="critical",
        )
        schema = summary.model_json_schema()
        assert "summary" in schema["properties"]
        assert "what_happened" in schema["properties"]
        assert "why_suspicious" in schema["properties"]
        assert "impact" in schema["properties"]
        assert "recommended_action" in schema["properties"]
        assert "severity" in schema["properties"]


class TestAlert:
    """Test Alert schema validation."""

    def test_alert_minimal(self):
        """Test creating Alert with required fields."""
        alert = Alert(
            tenant_id="tenant-123",
            incident_id="incident-456",
            title="Brute Force Detected",
            severity="high",
            affected_entity="admin",
            source_ip="192.0.2.1",
            location="New York, US",
            source_type="cloudtrail",
            incident_summary="Multiple failed logins detected",
            recommended_action="Reset password",
        )
        assert alert.alert_id is not None
        assert alert.feedback == "pending"
        assert alert.sent_at is not None

    def test_alert_feedback_values(self):
        """Test feedback field values."""
        for feedback in ["pending", "tp", "fp"]:
            alert = Alert(
                tenant_id="tenant",
                incident_id="incident",
                title="Test Alert",
                severity="medium",
                affected_entity="user",
                source_ip="10.0.0.1",
                location="Test Location",
                source_type="syslog",
                incident_summary="Test summary",
                recommended_action="Test action",
                feedback=feedback,
            )
            assert alert.feedback == feedback


class TestUser:
    """Test User schema validation."""

    def test_user_minimal(self):
        """Test creating User with required fields."""
        user = User(
            user_id="user-123",
            email="test@example.com",
        )
        assert user.user_id == "user-123"
        assert user.email == "test@example.com"
        assert user.plan == "free"
        assert user.created_at is not None

    def test_user_with_api_key(self):
        """Test User with API key hash and prefix."""
        user = User(
            user_id="user-456",
            email="admin@example.com",
            plan="enterprise",
            api_key_hash="$2b$12$abcdefghijklmnopqrstuvwxyz",
            api_key_prefix="sk-",
        )
        assert user.api_key_hash is not None
        assert user.api_key_prefix == "sk-"


class TestPayloads:
    """Test request payload schemas."""

    def test_cloudtrail_payload(self):
        """Test CloudTrailPayload validation."""
        payload = CloudTrailPayload(
            records=[
                {
                    "eventName": "ConsoleLogin",
                    "userIdentity": {"principalId": "user-1"},
                    "sourceIPAddress": "192.0.2.1",
                },
                {
                    "eventName": "PutObject",
                    "userIdentity": {"principalId": "user-2"},
                    "sourceIPAddress": "192.0.2.2",
                },
            ]
        )
        assert len(payload.records) == 2
        assert payload.records[0]["eventName"] == "ConsoleLogin"

    def test_syslog_payload(self):
        """Test SyslogPayload validation."""
        payload = SyslogPayload(
            records=[
                {"message": "sudo: user : TTY=pts/0 ; PWD=/home/user ; USER=root ; COMMAND=/bin/ls"},
                {"message": "sshd: Failed password for invalid user admin"},
            ]
        )
        assert len(payload.records) == 2

    def test_feedback_request(self):
        """Test FeedbackRequest validation."""
        for feedback in ["tp", "fp"]:
            req = FeedbackRequest(feedback=feedback)
            assert req.feedback == feedback

        with pytest.raises(ValueError):
            FeedbackRequest(feedback="invalid")  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
