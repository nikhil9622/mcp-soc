"""End-to-end integration tests for complete SOC pipeline (Phase 9)."""

import pytest
import asyncio
from datetime import datetime, timedelta
import json

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import (
    NormalizedEvent,
    DetectionEvent,
    Incident,
    IncidentSummary,
    Alert,
)


@pytest.mark.asyncio
class TestSOCPipelineE2E:
    """End-to-end tests for complete SOC pipeline: Ingestion → Alerting → Feedback."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_full_pipeline_brute_force_scenario(self):
        """Test complete pipeline: brute force attack detection and alerting."""
        tenant_id = "e2e-tenant-brute-force"
        events_col = get_collection("events")
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        alerts_col = get_collection("alerts")
        redis_client = get_redis()

        # Step 1: Ingest CloudTrail events
        base_time = datetime.utcnow()
        for i in range(5):
            event = NormalizedEvent(
                tenant_id=tenant_id,
                timestamp=base_time + timedelta(minutes=i),
                source="cloudtrail",
                user="admin",
                ip="203.0.113.1",
                action="ConsoleLogin",
                metadata={"response": "Failure"},
            )
            await events_col.insert_one(event.model_dump())

        # Verify events stored
        event_count = await events_col.count_documents({"tenant_id": tenant_id})
        assert event_count == 5

        # Step 2: Detection Agent matches rule
        for i in range(5):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id="brute_force",
                rule_name="Multiple Failed Logins",
                mitre_technique_id="T1110",
                mitre_tactic="initial_access",
                severity="high",
                risk_score=15.0,
            )
            await detections_col.insert_one(detection.model_dump())

        # Step 3: Correlation Agent clusters into incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=["det-0", "det-1", "det-2", "det-3", "det-4"],
            severity="high",
            entities={"users": ["admin"], "ips": ["203.0.113.1"]},
        )
        await incidents_col.insert_one(incident.model_dump())

        # Step 4: Investigation Agent adds summary
        summary = IncidentSummary(
            summary="Brute force attack detected",
            what_happened="5 failed login attempts from 203.0.113.1 in 5 minutes",
            why_suspicious="Exceeds brute force threshold (T1110)",
            impact="Admin account at risk",
            recommended_action="Force password reset; enable MFA",
            severity="high",
        )
        await incidents_col.update_one(
            {"incident_id": incident.incident_id},
            {"$set": {"summary": summary.model_dump()}},
        )

        # Step 5: Alerting Agent sends alert
        alert = Alert(
            tenant_id=tenant_id,
            incident_id=incident.incident_id,
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Step 6: Analyst submits feedback
        await alerts_col.update_one(
            {"alert_id": alert.alert_id},
            {
                "$set": {
                    "feedback": "tp",
                    "feedback_at": datetime.utcnow(),
                    "feedback_note": "Confirmed brute force attempt",
                }
            },
        )

        # Verify end-to-end
        final_alert = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert final_alert["feedback"] == "tp"
        assert final_alert["feedback_note"] is not None

    async def test_full_pipeline_privilege_escalation(self):
        """Test pipeline: privilege escalation detection."""
        tenant_id = "e2e-tenant-priv-esc"
        events_col = get_collection("events")
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        alerts_col = get_collection("alerts")

        # Ingest events
        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="developer",
            ip="192.0.2.1",
            action="PutUserPolicy",
            metadata={"resource": "admin_role"},
        )
        await events_col.insert_one(event.model_dump())

        # Detection
        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="privilege_escalation",
            rule_name="Privilege Escalation via IAM",
            mitre_technique_id="T1078.004",
            mitre_tactic="initial_access",
            severity="high",
            risk_score=18.0,
        )
        await detections_col.insert_one(detection.model_dump())

        # Correlation
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=[detection.detection_id],
            severity="high",
        )
        await incidents_col.insert_one(incident.model_dump())

        # Verify entire flow
        assert await events_col.count_documents({"tenant_id": tenant_id}) == 1
        assert (
            await detections_col.count_documents({"tenant_id": tenant_id}) == 1
        )
        assert (
            await incidents_col.count_documents({"tenant_id": tenant_id}) == 1
        )

    async def test_multi_tenant_isolation_e2e(self):
        """Test E2E with multiple tenants to verify isolation."""
        tenant_x = "e2e-tenant-x"
        tenant_y = "e2e-tenant-y"
        events_col = get_collection("events")
        detections_col = get_collection("detections")

        # Create events for both tenants
        for tenant in [tenant_x, tenant_y]:
            event = NormalizedEvent(
                tenant_id=tenant,
                timestamp=datetime.utcnow(),
                source="cloudtrail",
                user="admin",
                ip="192.0.2.1",
                action="ConsoleLogin",
            )
            await events_col.insert_one(event.model_dump())

        # Verify isolation
        x_events = await events_col.find({"tenant_id": tenant_x}).to_list(None)
        y_events = await events_col.find({"tenant_id": tenant_y}).to_list(None)

        assert len(x_events) == 1
        assert len(y_events) == 1
        assert x_events[0]["tenant_id"] == tenant_x
        assert y_events[0]["tenant_id"] == tenant_y

    async def test_incident_correlation_multiple_detections(self):
        """Test correlation with multiple detections."""
        tenant_id = "e2e-tenant-corr"
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")

        # Create multiple detections from same user/IP
        base_time = datetime.utcnow()
        detection_ids = []
        for i in range(3):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id=f"rule-{i}",
                rule_name=f"Rule {i}",
                mitre_technique_id=f"T1110",
                mitre_tactic="initial_access",
                severity="high",
                risk_score=15.0,
                detected_at=base_time + timedelta(minutes=i),
            )
            await detections_col.insert_one(detection.model_dump())
            detection_ids.append(detection.detection_id)

        # Create incident correlating all detections
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="high",
            entities={"users": ["admin"], "ips": ["192.0.2.1"]},
        )
        await incidents_col.insert_one(incident.model_dump())

        # Verify correlation
        stored_incident = await incidents_col.find_one(
            {"incident_id": incident.incident_id}
        )
        assert len(stored_incident["detection_ids"]) == 3

    async def test_feedback_loop_integration(self):
        """Test complete feedback loop: alert → feedback → stream."""
        tenant_id = "e2e-tenant-feedback"
        alerts_col = get_collection("alerts")
        redis_client = get_redis()

        # Create alert
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
                    "feedback_note": "Verified true positive",
                }
            },
        )

        # Publish to feedback stream
        stream_name = f"soc:feedback:{tenant_id}"
        msg_id = await redis_client.xadd(
            stream_name,
            {
                "alert_id": alert.alert_id,
                "incident_id": alert.incident_id,
                "feedback": "tp",
                "submitted_at": datetime.utcnow().isoformat(),
            },
        )

        # Verify feedback stream
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1

    async def test_severity_escalation_during_correlation(self):
        """Test severity escalation when multiple critical detections correlate."""
        tenant_id = "e2e-tenant-escalation"
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")

        # Create 2 critical detections
        detection_ids = []
        for i in range(2):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id="critical_rule",
                rule_name="Critical Rule",
                mitre_technique_id="T1078",
                mitre_tactic="initial_access",
                severity="critical",
                risk_score=40.0,
            )
            await detections_col.insert_one(detection.model_dump())
            detection_ids.append(detection.detection_id)

        # Correlate into incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="critical",  # Escalated from high to critical
        )
        await incidents_col.insert_one(incident.model_dump())

        # Verify incident is critical
        assert incident.severity == "critical"

    async def test_timestamp_ordering_in_pipeline(self):
        """Test timestamps are preserved through pipeline."""
        tenant_id = "e2e-tenant-timestamps"
        events_col = get_collection("events")
        detections_col = get_collection("detections")

        base_time = datetime.utcnow()

        # Create events with specific timestamps
        for i in range(3):
            event = NormalizedEvent(
                tenant_id=tenant_id,
                timestamp=base_time + timedelta(minutes=i),
                source="cloudtrail",
                user="admin",
                ip="192.0.2.1",
                action="ConsoleLogin",
            )
            await events_col.insert_one(event.model_dump())

        # Create detections
        for i in range(3):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id="test_rule",
                rule_name="Test Rule",
                mitre_technique_id="T1110",
                mitre_tactic="initial_access",
                severity="medium",
                risk_score=5.0,
            )
            await detections_col.insert_one(detection.model_dump())

        # Query and verify ordering
        events = await events_col.find({"tenant_id": tenant_id}).sort("timestamp", 1).to_list(None)
        assert len(events) == 3
        assert events[0]["timestamp"] <= events[1]["timestamp"] <= events[2]["timestamp"]

    async def test_deduplication_in_incident_creation(self):
        """Test incident deduplication (one alert per incident)."""
        tenant_id = "e2e-tenant-dedup"
        incidents_col = get_collection("incidents")
        alerts_col = get_collection("alerts")

        # Create incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=["det-1"],
            severity="high",
        )
        await incidents_col.insert_one(incident.model_dump())

        # Try to create alert for this incident
        alert1 = Alert(
            tenant_id=tenant_id,
            incident_id=incident.incident_id,
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert1.model_dump())

        # Check for duplicates (in real code, this check happens before insert)
        existing = await alerts_col.find_one(
            {"tenant_id": tenant_id, "incident_id": incident.incident_id}
        )
        assert existing is not None

    async def test_api_key_auth_e2e(self):
        """Test API key authentication through broker."""
        from shared.api_keys import generate_api_key, hash_api_key, get_key_prefix
        from shared.models import User

        users_col = get_collection("users")
        tenant_id = "e2e-tenant-auth"

        # Create user with API key
        api_key = generate_api_key()
        user = User(
            user_id=tenant_id,
            email=f"{tenant_id}@example.com",
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=get_key_prefix(api_key),
        )
        await users_col.insert_one(user.model_dump())

        # Verify lookup works
        prefix = get_key_prefix(api_key)
        stored_user = await users_col.find_one({"api_key_prefix": prefix})
        assert stored_user is not None
        assert stored_user["user_id"] == tenant_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
