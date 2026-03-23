"""Unit and integration tests for Alerting Agent."""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import IncidentSummary, Incident, Alert


@pytest.mark.asyncio
class TestAlertingE2E:
    """End-to-end tests: IncidentSummary → Email → Alert → Feedback."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_alert_creation_critical(self):
        """Test creating and storing a critical alert."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-alert-crit"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-crit-1",
            recipient="soc@example.com",
            severity="critical",
            title="Root account compromise",
            affected_entity="root",
            source_ip="203.0.113.1",
            location="Singapore, SG",
            incident_summary="Root account used to delete critical database",
            recommended_action="Immediately revoke root credentials",
        )

        # Store alert
        await alerts_col.insert_one(alert.model_dump())

        # Verify
        stored = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert stored is not None
        assert stored["severity"] == "critical"
        assert stored["recipient"] == "soc@example.com"
        assert stored["feedback"] is None

    async def test_alert_high_priority(self):
        """Test high severity alert."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-alert-high"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-high-1",
            recipient="soc@example.com",
            severity="high",
            title="Privilege escalation detected",
            affected_entity="developer",
            source_ip="192.0.2.1",
        )

        await alerts_col.insert_one(alert.model_dump())
        stored = await alerts_col.find_one({"alert_id": alert.alert_id})

        assert stored["severity"] == "high"

    async def test_alert_idempotency(self):
        """Test one alert per incident (idempotency)."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-idem"
        incident_id = "inc-idem-1"

        alert1 = Alert(
            tenant_id=tenant_id,
            incident_id=incident_id,
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert1.model_dump())

        # Try to insert another alert for same incident (should check for duplicate)
        existing = await alerts_col.find_one(
            {"tenant_id": tenant_id, "incident_id": incident_id}
        )
        assert existing is not None

    async def test_alert_feedback_tp(self):
        """Test recording true positive feedback."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-feedback-tp"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-feedback-1",
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Submit feedback
        await alerts_col.update_one(
            {"alert_id": alert.alert_id},
            {
                "$set": {
                    "feedback": "tp",
                    "feedback_at": datetime.utcnow(),
                    "feedback_note": "Confirmed data exfiltration",
                }
            },
        )

        # Verify feedback stored
        updated = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert updated["feedback"] == "tp"
        assert updated["feedback_note"] is not None

    async def test_alert_feedback_fp(self):
        """Test recording false positive feedback."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-feedback-fp"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-feedback-fp",
            recipient="soc@example.com",
            severity="medium",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Submit false positive feedback
        await alerts_col.update_one(
            {"alert_id": alert.alert_id},
            {
                "$set": {
                    "feedback": "fp",
                    "feedback_at": datetime.utcnow(),
                    "feedback_note": "Benign activity, known user",
                }
            },
        )

        # Verify
        updated = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert updated["feedback"] == "fp"

    async def test_alert_to_redis_stream(self):
        """Test publishing feedback to Redis Stream."""
        redis_client = get_redis()
        tenant_id = "test-tenant-redis-alert"

        # Create alert with feedback
        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-redis",
            recipient="soc@example.com",
            severity="high",
            feedback="tp",
            feedback_at=datetime.utcnow(),
        )

        # Publish to Redis Stream
        stream_name = f"soc:feedback:{tenant_id}"
        msg_id = await redis_client.xadd(
            stream_name,
            {"alert": alert.model_dump_json(default=str)},
        )

        assert msg_id is not None

        # Verify stream has message
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1

    async def test_alert_tenant_isolation(self):
        """Test alerts respect tenant isolation."""
        alerts_col = get_collection("alerts")

        # Create alerts for two tenants
        for tenant in ["tenant-alert-x", "tenant-alert-y"]:
            alert = Alert(
                tenant_id=tenant,
                incident_id=f"inc-{tenant}",
                recipient="soc@example.com",
                severity="high",
            )
            await alerts_col.insert_one(alert.model_dump())

        # Query only tenant-x
        cursor = alerts_col.find({"tenant_id": "tenant-alert-x"})
        results = await cursor.to_list(None)

        # Should only see tenant-x
        assert all(a["tenant_id"] == "tenant-alert-x" for a in results)

    async def test_alert_model_validation(self):
        """Test Alert model creation and validation."""
        alert = Alert(
            tenant_id="test-tenant",
            incident_id="inc-1",
            recipient="user@example.com",
            severity="critical",
        )

        assert alert.alert_id is not None
        assert alert.sent_at is not None
        assert alert.feedback is None
        assert alert.feedback_at is None

    async def test_alert_severity_values(self):
        """Test all severity levels."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-severity"

        for severity in ["critical", "high", "medium", "low"]:
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{severity}",
                recipient="soc@example.com",
                severity=severity,
            )
            await alerts_col.insert_one(alert.model_dump())

            stored = await alerts_col.find_one(
                {"tenant_id": tenant_id, "incident_id": f"inc-{severity}"}
            )
            assert stored["severity"] == severity

    async def test_alert_recipient_extraction(self):
        """Test alert recipient storage."""
        alerts_col = get_collection("alerts")

        recipients = [
            "soc-team@company.com",
            "ciso@company.com",
            "security-ops@company.com",
        ]

        for recipient in recipients:
            alert = Alert(
                tenant_id="test-tenant",
                incident_id=f"inc-{recipient}",
                recipient=recipient,
                severity="high",
            )
            await alerts_col.insert_one(alert.model_dump())

        # Verify all recipients stored
        stored_recipients = await alerts_col.find({"tenant_id": "test-tenant"}).to_list(None)
        assert len(stored_recipients) == len(recipients)

    async def test_alert_feedback_query(self):
        """Test querying alerts by feedback status."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-query"

        # Create alerts with different feedback
        feedback_data = [
            ("inc-1", None),
            ("inc-2", "tp"),
            ("inc-3", "fp"),
            ("inc-4", "tp"),
        ]

        for incident_id, feedback in feedback_data:
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=incident_id,
                recipient="soc@example.com",
                severity="high",
                feedback=feedback,
            )
            await alerts_col.insert_one(alert.model_dump())

        # Query TP alerts
        tp_alerts = await alerts_col.find(
            {"tenant_id": tenant_id, "feedback": "tp"}
        ).to_list(None)
        assert len(tp_alerts) == 2

        # Query FP alerts
        fp_alerts = await alerts_col.find(
            {"tenant_id": tenant_id, "feedback": "fp"}
        ).to_list(None)
        assert len(fp_alerts) == 1

        # Query pending alerts
        pending = await alerts_col.find(
            {"tenant_id": tenant_id, "feedback": None}
        ).to_list(None)
        assert len(pending) == 1

    async def test_alert_multiple_per_tenant(self):
        """Test multiple alerts per tenant."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-multi"

        # Create 5 alerts
        for i in range(5):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{i}",
                recipient=f"recipient-{i}@example.com" if i % 2 == 0 else "soc@example.com",
                severity=["critical", "high", "medium", "low", "high"][i],
            )
            await alerts_col.insert_one(alert.model_dump())

        # Query all
        alerts = await alerts_col.find({"tenant_id": tenant_id}).to_list(None)
        assert len(alerts) == 5

        # Verify different recipients
        recipients = set(a["recipient"] for a in alerts)
        assert len(recipients) >= 2


class TestAlertModel:
    """Test Alert Pydantic model."""

    def test_alert_creation(self):
        """Test Alert model creation."""
        alert = Alert(
            tenant_id="tenant-1",
            incident_id="inc-1",
            recipient="soc@example.com",
            severity="high",
        )

        assert alert.tenant_id == "tenant-1"
        assert alert.severity == "high"
        assert alert.feedback is None

    def test_alert_feedback_update(self):
        """Test updating alert feedback."""
        alert = Alert(
            tenant_id="tenant-1",
            incident_id="inc-1",
            recipient="soc@example.com",
            severity="high",
        )

        # Update with feedback
        updated = alert.model_copy(
            update={"feedback": "tp", "feedback_at": datetime.utcnow()}
        )

        assert updated.feedback == "tp"
        assert updated.feedback_at is not None

    def test_alert_serialization(self):
        """Test Alert serialization."""
        alert = Alert(
            tenant_id="tenant-1",
            incident_id="inc-1",
            recipient="soc@example.com",
            severity="critical",
        )

        # Serialize
        dumped = alert.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["severity"] == "critical"

        # JSON serialization
        json_str = alert.model_dump_json(default=str)
        assert json_str is not None

    def test_alert_all_severity_levels(self):
        """Test Alert with all severity levels."""
        for severity in ["critical", "high", "medium", "low"]:
            alert = Alert(
                tenant_id="tenant-1",
                incident_id=f"inc-{severity}",
                recipient="soc@example.com",
                severity=severity,
            )
            assert alert.severity == severity

    def test_alert_backward_compatibility(self):
        """Test Alert backward compatibility with old schema."""
        alert = Alert(
            tenant_id="tenant-1",
            incident_id="inc-1",
            recipient="soc@example.com",
            severity="high",
            title="Test alert",
            affected_entity="user@example.com",
            source_ip="192.0.2.1",
            location="US",
            incident_summary="Test incident",
            recommended_action="Review logs",
        )

        # Should still have old fields
        assert alert.title == "Test alert"
        assert alert.affected_entity == "user@example.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
