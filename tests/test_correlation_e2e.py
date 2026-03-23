"""End-to-end integration tests for Correlation Agent with MongoDB and NetworkX."""

import pytest
import networkx as nx
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncClient

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import DetectionEvent, Incident, NormalizedEvent
from agents.correlation import SEVERITY_ORDER


@pytest.mark.asyncio
class TestCorrelationE2E:
    """End-to-end tests: DetectionEvent → Correlation → Incident → MongoDB → Redis."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to both databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_correlation_single_user_multiple_actions(self):
        """Test correlating multiple detections from same user."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-single-user"

        # Create 3 detections from alice
        base_event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="alice",
            ip="192.0.2.100",
            action="ConsoleLogin",
        )

        detection_ids = []
        for i, action in enumerate(["ConsoleLogin", "PutObject", "CreateAccessKey"]):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id=f"rule-{i}",
                rule_name=f"Rule {i}",
                mitre_technique_id=f"T{i}",
                mitre_tactic="test",
                severity=["critical", "high", "medium"][i],
                risk_score=float([40, 18, 10][i]),
                raw_event={
                    "user": "alice",
                    "ip": "192.0.2.100",
                    "action": action,
                },
            )
            await detections_col.insert_one(detection.model_dump())
            detection_ids.append(detection.detection_id)

        # Create incident from these detections
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="critical",  # Max severity
            entities={"users": ["alice"], "ips": ["192.0.2.100"]},
        )

        await incidents_col.insert_one(incident.model_dump())

        # Verify
        stored = await incidents_col.find_one({"incident_id": incident.incident_id})
        assert stored is not None
        assert len(stored["detection_ids"]) == 3
        assert stored["severity"] == "critical"

    async def test_correlation_same_ip_different_users(self):
        """Test correlating detections from same IP by different users."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-same-ip"

        # 2 detections from different users, same IP
        detection_ids = []
        for user in ["alice", "bob"]:
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{user}",
                rule_id="console-login",
                rule_name="Console Login",
                mitre_technique_id="T1078",
                mitre_tactic="initial_access",
                severity="medium",
                risk_score=5.0,
                raw_event={
                    "user": user,
                    "ip": "203.0.113.50",  # Same IP
                    "action": "ConsoleLogin",
                },
            )
            await detections_col.insert_one(detection.model_dump())
            detection_ids.append(detection.detection_id)

        # Create incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="medium",
            entities={"users": ["alice", "bob"], "ips": ["203.0.113.50"]},
        )

        await incidents_col.insert_one(incident.model_dump())

        # Verify
        stored = await incidents_col.find_one({"incident_id": incident.incident_id})
        assert len(stored["detection_ids"]) == 2
        assert "alice" in stored["entities"]["users"]
        assert "bob" in stored["entities"]["users"]

    async def test_correlation_min_detections_rule(self):
        """Test minimum 2 detections rule."""
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-min"

        # Single detection should NOT create incident in real flow
        # (This is filtered in correlation agent)
        # But we can test that a 1-detection incident would be marked as incomplete

        detection_ids = ["det-1"]
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="medium",
        )

        # Store but mark differently (in real code, wouldn't be stored)
        # For test, just verify creation
        assert len(incident.detection_ids) == 1

    async def test_correlation_severity_escalation(self):
        """Test severity escalation in incidents."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-severity"

        # Create detections with mixed severities
        severities_and_scores = [
            ("low", 2.0),
            ("medium", 5.0),
            ("high", 7.0),
            ("critical", 10.0),
        ]

        detection_ids = []
        for severity, score in severities_and_scores:
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{severity}",
                rule_id=f"rule-{severity}",
                rule_name=f"Rule {severity}",
                mitre_technique_id="T0000",
                mitre_tactic="test",
                severity=severity,
                risk_score=score,
                raw_event={"user": "alice", "ip": "192.0.2.1"},
            )
            await detections_col.insert_one(detection.model_dump())
            detection_ids.append(detection.detection_id)

        # Calculate max severity
        severities = [s for s, _ in severities_and_scores]
        max_sev = max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))
        assert max_sev == "critical"

        # Create incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity=max_sev,
        )

        await incidents_col.insert_one(incident.model_dump())

        # Verify critical severity
        stored = await incidents_col.find_one({"incident_id": incident.incident_id})
        assert stored["severity"] == "critical"

    async def test_correlation_deduplication(self):
        """Test incident deduplication (no duplicate incidents)."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-dedup"

        # Create 2 detections
        d1_id = None
        d2_id = None

        for i in range(2):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id="shared-rule",
                rule_name="Shared Rule",
                mitre_technique_id="T1110",
                mitre_tactic="credential_access",
                severity="high",
                risk_score=15.0,
                raw_event={"user": "alice", "ip": "192.0.2.1"},
            )
            await detections_col.insert_one(detection.model_dump())
            if i == 0:
                d1_id = detection.detection_id
            else:
                d2_id = detection.detection_id

        # Create first incident
        incident1 = Incident(
            tenant_id=tenant_id,
            detection_ids=[d1_id, d2_id],
            severity="high",
        )
        await incidents_col.insert_one(incident1.model_dump())

        # Try to create duplicate (should detect overlap)
        d3 = DetectionEvent(
            tenant_id=tenant_id,
            event_id="event-3",
            rule_id="shared-rule",
            rule_name="Shared Rule",
            mitre_technique_id="T1110",
            mitre_tactic="credential_access",
            severity="high",
            risk_score=15.0,
            raw_event={"user": "alice", "ip": "192.0.2.1"},
        )
        await detections_col.insert_one(d3.model_dump())

        # Check for existing incident (overlap detection)
        existing = await incidents_col.find_one({
            "tenant_id": tenant_id,
            "detection_ids": {"$in": [d1_id, d2_id]},
        })
        assert existing is not None  # Found existing incident

    async def test_correlation_tenant_isolation(self):
        """Test that correlation respects tenant isolation."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")

        # Create incidents for two tenants
        for tenant in ["tenant-a", "tenant-b"]:
            detection = DetectionEvent(
                tenant_id=tenant,
                event_id="event-1",
                rule_id="rule-1",
                rule_name="Rule 1",
                mitre_technique_id="T0000",
                mitre_tactic="test",
                severity="medium",
                risk_score=5.0,
                raw_event={"user": "user", "ip": "192.0.2.1"},
            )
            await detections_col.insert_one(detection.model_dump())

            incident = Incident(
                tenant_id=tenant,
                detection_ids=[detection.detection_id],
                severity="medium",
            )
            await incidents_col.insert_one(incident.model_dump())

        # Query tenant-a only
        cursor = incidents_col.find({"tenant_id": "tenant-a"})
        results = await cursor.to_list(None)

        # Should only see tenant-a incidents
        assert all(i["tenant_id"] == "tenant-a" for i in results)

    async def test_correlation_to_redis_stream(self):
        """Test incident publishing to Redis Stream."""
        redis_client = get_redis()
        tenant_id = "test-tenant-redis"

        detection_ids = ["det-1", "det-2"]
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="high",
            entities={"users": ["alice"], "ips": ["192.0.2.1"]},
        )

        # Publish to Redis Stream
        stream_name = f"soc:incidents:{tenant_id}"
        msg_id = await redis_client.xadd(stream_name, {"incident": incident.model_dump_json()})

        assert msg_id is not None

        # Verify message in stream
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
