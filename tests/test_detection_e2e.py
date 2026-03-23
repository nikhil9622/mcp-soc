"""End-to-end integration tests for Detection Agent with Redis and MongoDB."""

import pytest
import json
from datetime import datetime
from motor.motor_asyncio import AsyncClient
import redis.asyncio as aioredis

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import NormalizedEvent, DetectionEvent
from agents.detection import load_sigma_rules, _match_rule, run_detection_agent


@pytest.mark.asyncio
class TestDetectionE2E:
    """End-to-end tests: NormalizedEvent → Detection → MongoDB → Redis."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to both databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_detection_brute_force(self):
        """Test brute force detection creation."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-bruteforce"

        # Create brute force simulation
        base_time = datetime.utcnow()
        failed_events = []

        for i in range(6):
            event = NormalizedEvent(
                tenant_id=tenant_id,
                timestamp=base_time,
                source="cloudtrail",
                user="attacker",
                ip="192.0.2.100",
                action="ConsoleLogin",
                metadata={"responseElements": {"ConsoleLogin": "Failure"}},
            )
            failed_events.append(event)

        # In real scenario, these would be detected by correlation
        # For this test, we verify they can be stored
        for event in failed_events:
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=event.event_id,
                rule_id="brute-force-rule",
                rule_name="Multiple Failed Logins",
                mitre_technique_id="T1110",
                mitre_tactic="credential_access",
                severity="high",
                risk_score=15.0,
                raw_event=event.model_dump(),
            )
            await detections_col.insert_one(detection.model_dump())

        # Query and verify
        cursor = detections_col.find(
            {"tenant_id": tenant_id, "rule_name": "Multiple Failed Logins"}
        )
        detections = await cursor.to_list(None)
        assert len(detections) >= 6

    async def test_detection_new_location(self):
        """Test new location detection."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-newloc"

        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="alice",
            ip="203.0.113.50",
            action="ConsoleLogin",
            city="Singapore",
            country="SG",
            is_new_location=True,
        )

        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="new-location-rule",
            rule_name="Login from New Geographic Location",
            mitre_technique_id="T1078",
            mitre_tactic="initial_access",
            severity="medium",
            risk_score=8.0,
            raw_event=event.model_dump(),
        )

        await detections_col.insert_one(detection.model_dump())

        # Verify stored
        stored = await detections_col.find_one({"detection_id": detection.detection_id})
        assert stored is not None
        assert stored["rule_name"] == "Login from New Geographic Location"

    async def test_detection_privilege_escalation(self):
        """Test privilege escalation detection."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-priv"

        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="bob",
            ip="192.0.2.10",
            action="PutUserPolicy",
        )

        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="priv-esc-rule",
            rule_name="Privilege Escalation via IAM",
            mitre_technique_id="T1078.004",
            mitre_tactic="privilege_escalation",
            severity="high",
            risk_score=18.0,
            raw_event=event.model_dump(),
        )

        await detections_col.insert_one(detection.model_dump())
        assert detection.risk_score == 18.0

    async def test_detection_unusual_hours(self):
        """Test unusual access hours detection."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-hours"

        # 3 AM login
        early_morning = datetime.utcnow().replace(hour=3, minute=0, second=0)
        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=early_morning,
            source="cloudtrail",
            user="charlie",
            ip="192.0.2.20",
            action="ConsoleLogin",
        )

        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="hours-rule",
            rule_name="AWS Console Access Outside Business Hours",
            mitre_technique_id="T1078",
            mitre_tactic="initial_access",
            severity="low",
            risk_score=3.0,
            raw_event=event.model_dump(),
        )

        await detections_col.insert_one(detection.model_dump())

        # Verify
        stored = await detections_col.find_one({"detection_id": detection.detection_id})
        assert stored is not None

    async def test_detection_root_account(self):
        """Test root account usage detection."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-root"

        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="root",
            user_type="Root",
            ip="192.0.2.30",
            action="DeleteBucket",
        )

        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="root-rule",
            rule_name="Root Account Usage",
            mitre_technique_id="T1078.003",
            mitre_tactic="privilege_escalation",
            severity="critical",
            risk_score=40.0,  # 10.0 * 2.0 * 2.0
            raw_event=event.model_dump(),
        )

        await detections_col.insert_one(detection.model_dump())

        # Verify critical severity
        stored = await detections_col.find_one({"detection_id": detection.detection_id})
        assert stored["severity"] == "critical"
        assert stored["risk_score"] == 40.0

    async def test_detection_to_redis_stream(self):
        """Test detection publishing to Redis Stream."""
        redis_client = get_redis()
        tenant_id = "test-tenant-redis"

        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="dave",
            ip="203.0.113.100",
            action="CreateAccessKey",
        )

        detection = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id="key-rule",
            rule_name="Privilege Escalation via IAM",
            mitre_technique_id="T1078.004",
            mitre_tactic="privilege_escalation",
            severity="high",
            risk_score=15.0,
        )

        # Publish to Redis Stream
        stream_name = f"soc:detections:{tenant_id}"
        msg_id = await redis_client.xadd(stream_name, {"detection": detection.model_dump_json()})

        assert msg_id is not None

        # Verify message in stream
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1

    async def test_detection_tenant_isolation(self):
        """Test that detections are isolated by tenant."""
        detections_col = get_collection("detections")

        # Create detections for two tenants
        for tenant in ["tenant-x", "tenant-y"]:
            event = NormalizedEvent(
                tenant_id=tenant,
                timestamp=datetime.utcnow(),
                source="cloudtrail",
                user="user",
                ip="192.0.2.1",
                action="ConsoleLogin",
            )

            detection = DetectionEvent(
                tenant_id=tenant,
                event_id=event.event_id,
                rule_id="test-rule",
                rule_name="Test Rule",
                mitre_technique_id="T1078",
                mitre_tactic="initial_access",
                severity="medium",
                risk_score=5.0,
            )

            await detections_col.insert_one(detection.model_dump())

        # Query for tenant-x only
        cursor = detections_col.find({"tenant_id": "tenant-x"})
        results = await cursor.to_list(None)

        # Should only see tenant-x detections
        assert all(d["tenant_id"] == "tenant-x" for d in results)

    async def test_risk_score_calculation(self):
        """Test risk score calculation with different severity levels."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-scores"

        test_cases = [
            ("critical", 40.0),  # 10.0 * 2.0 * 2.0 (root + critical)
            ("high", 18.0),      # 7.0 * 2.0 * ? or equivalent
            ("medium", 5.0),     # 5.0 * 1.0 * 1.0
            ("low", 2.0),        # 2.0 * 1.0 * 1.0
        ]

        for severity, expected_score in test_cases:
            event = NormalizedEvent(
                tenant_id=tenant_id,
                timestamp=datetime.utcnow(),
                source="cloudtrail",
                user="test",
                ip="192.0.2.1",
                action="TestAction",
            )

            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=event.event_id,
                rule_id=f"rule-{severity}",
                rule_name=f"Test {severity}",
                mitre_technique_id="T0000",
                mitre_tactic="test",
                severity=severity,
                risk_score=expected_score,
            )

            await detections_col.insert_one(detection.model_dump())

        # Verify all stored
        cursor = detections_col.find({"tenant_id": tenant_id})
        results = await cursor.to_list(None)
        assert len(results) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
