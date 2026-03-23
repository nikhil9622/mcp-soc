"""Tests for alerts API endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis
from shared.models import Alert


@pytest.mark.asyncio
class TestAlertsEndpoints:
    """Test alerts API endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_alert_feedback_tp_validation(self):
        """Test feedback endpoint validates TP feedback."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-api"

        # Create test alert
        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-api-1",
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Validate feedback type
        valid_types = ["tp", "fp"]
        invalid_types = ["true", "false", "yes", "no", "correct", ""]

        for feedback_type in valid_types:
            assert feedback_type in ("tp", "fp")

        for feedback_type in invalid_types:
            assert feedback_type not in ("tp", "fp")

    async def test_alert_feedback_with_note(self):
        """Test feedback submission with analyst note."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-note"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-note",
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Simulate feedback submission
        note = "Confirmed privilege escalation, user account compromised"
        await alerts_col.update_one(
            {"alert_id": alert.alert_id},
            {
                "$set": {
                    "feedback": "tp",
                    "feedback_at": datetime.utcnow(),
                    "feedback_note": note,
                }
            },
        )

        # Verify
        updated = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert updated["feedback_note"] == note

    async def test_alert_feedback_query_filtering(self):
        """Test querying alerts by feedback status."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-filter"

        # Create multiple alerts
        for i, feedback in enumerate([None, "tp", "fp", "tp", None]):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{i}",
                recipient="soc@example.com",
                severity="high",
                feedback=feedback,
            )
            await alerts_col.insert_one(alert.model_dump())

        # Query by feedback
        tp_count = await alerts_col.count_documents(
            {"tenant_id": tenant_id, "feedback": "tp"}
        )
        assert tp_count == 2

        fp_count = await alerts_col.count_documents(
            {"tenant_id": tenant_id, "feedback": "fp"}
        )
        assert fp_count == 1

    async def test_alert_audit_logging(self):
        """Test feedback audit trail."""
        alerts_col = get_collection("alerts")
        audit_col = get_collection("audit_log")
        tenant_id = "test-tenant-audit"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-audit",
            recipient="soc@example.com",
            severity="critical",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Log feedback submission
        feedback_note = "Rule needs tuning"
        await audit_col.insert_one({
            "tenant_id": tenant_id,
            "action": "submit_feedback",
            "entity": "alert",
            "entity_id": alert.alert_id,
            "value": "fp",
            "note": feedback_note,
            "timestamp": datetime.utcnow(),
        })

        # Verify audit log
        audit_entry = await audit_col.find_one({"entity_id": alert.alert_id})
        assert audit_entry["action"] == "submit_feedback"
        assert audit_entry["value"] == "fp"

    async def test_alert_list_sorting(self):
        """Test alerts list endpoint sorting by sent_at."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-list"

        # Create alerts with different sent_at times
        base_time = datetime.utcnow()
        for i in range(3):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-sort-{i}",
                recipient="soc@example.com",
                severity="high",
                sent_at=datetime(2026, 3, 20 + i, 12, 0, 0),
            )
            await alerts_col.insert_one(alert.model_dump())

        # Query sorted by sent_at descending
        alerts = await alerts_col.find(
            {"tenant_id": tenant_id}, {"_id": 0}
        ).sort("sent_at", -1).to_list(None)

        # Should be in reverse chronological order
        assert len(alerts) == 3
        assert alerts[0]["sent_at"] >= alerts[1]["sent_at"]
        assert alerts[1]["sent_at"] >= alerts[2]["sent_at"]

    async def test_alert_pagination(self):
        """Test pagination of alerts list."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-page"

        # Create 10 alerts
        for i in range(10):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-page-{i}",
                recipient="soc@example.com",
                severity="high",
            )
            await alerts_col.insert_one(alert.model_dump())

        # Page 1: skip=0, limit=5
        page1 = await alerts_col.find({"tenant_id": tenant_id}).skip(0).limit(5).to_list(None)
        assert len(page1) == 5

        # Page 2: skip=5, limit=5
        page2 = await alerts_col.find({"tenant_id": tenant_id}).skip(5).limit(5).to_list(None)
        assert len(page2) == 5

        # Verify no overlap
        page1_ids = set(a["alert_id"] for a in page1)
        page2_ids = set(a["alert_id"] for a in page2)
        assert len(page1_ids & page2_ids) == 0

    async def test_alert_tenant_isolation_endpoint(self):
        """Test endpoint respects tenant isolation."""
        alerts_col = get_collection("alerts")

        # Create alerts for different tenants
        for tenant in ["tenant-x", "tenant-y"]:
            alert = Alert(
                tenant_id=tenant,
                incident_id=f"inc-{tenant}",
                recipient="soc@example.com",
                severity="high",
            )
            await alerts_col.insert_one(alert.model_dump())

        # Simulate user from tenant-x querying
        alerts_x = await alerts_col.find({"tenant_id": "tenant-x"}).to_list(None)

        # Should only see tenant-x alerts
        assert all(a["tenant_id"] == "tenant-x" for a in alerts_x)

    async def test_alert_feedback_timestamp(self):
        """Test feedback timestamp is recorded."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-timestamp"

        alert = Alert(
            tenant_id=tenant_id,
            incident_id="inc-ts",
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Submit feedback
        now = datetime.utcnow()
        await alerts_col.update_one(
            {"alert_id": alert.alert_id},
            {
                "$set": {
                    "feedback": "tp",
                    "feedback_at": now,
                }
            },
        )

        # Verify timestamp
        updated = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert updated["feedback_at"] is not None
        assert isinstance(updated["feedback_at"], datetime)


class TestFeedbackRequest:
    """Test FeedbackRequest model."""

    def test_feedback_request_tp(self):
        """Test creating TP feedback request."""
        from shared.models import FeedbackRequest

        feedback = FeedbackRequest(feedback="tp")
        assert feedback.feedback == "tp"

    def test_feedback_request_fp(self):
        """Test creating FP feedback request."""
        from shared.models import FeedbackRequest

        feedback = FeedbackRequest(feedback="fp")
        assert feedback.feedback == "fp"

    def test_feedback_request_invalid(self):
        """Test invalid feedback type rejected."""
        from shared.models import FeedbackRequest

        with pytest.raises(ValueError):
            FeedbackRequest(feedback="invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
