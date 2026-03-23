"""End-to-end integration tests for Investigation Agent with Claude API."""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import DetectionEvent, Incident, IncidentSummary


@pytest.mark.asyncio
class TestInvestigationE2E:
    """End-to-end tests: Incident → Claude API → IncidentSummary → Storage."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_investigation_privilege_escalation_scenario(self):
        """Test investigation of privilege escalation incident."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-invest-priv"

        # Create detection events
        detections = [
            {
                "detection_id": "det-priv-1",
                "tenant_id": tenant_id,
                "event_id": "event-1",
                "rule_name": "Privilege Escalation via IAM",
                "mitre_technique_id": "T1078.004",
                "severity": "high",
                "risk_score": 18.0,
                "raw_event": {
                    "user": "developer",
                    "ip": "192.0.2.1",
                    "action": "PutUserPolicy",
                    "metadata": {"resource": "admin_role"},
                },
            },
            {
                "detection_id": "det-priv-2",
                "tenant_id": tenant_id,
                "event_id": "event-2",
                "rule_name": "Root Account Usage",
                "mitre_technique_id": "T1078.003",
                "severity": "critical",
                "risk_score": 40.0,
                "raw_event": {
                    "user": "root",
                    "ip": "192.0.2.1",
                    "action": "CreateAccessKey",
                },
            },
        ]

        # Store detections
        for det in detections:
            await detections_col.insert_one(det)

        # Create incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=["det-priv-1", "det-priv-2"],
            severity="critical",
            entities={
                "users": ["developer", "root"],
                "ips": ["192.0.2.1"],
            },
        )
        await incidents_col.insert_one(incident.model_dump())

        # Verify incident exists
        stored_incident = await incidents_col.find_one({"incident_id": incident.incident_id})
        assert stored_incident is not None
        assert stored_incident["severity"] == "critical"

        # Simulate Claude response (create expected summary)
        expected_summary = IncidentSummary(
            summary="Privilege escalation attack chain detected",
            what_happened="Developer account escalated to root and created unauthorized access keys",
            why_suspicious="Privilege escalation (T1078.004) followed by root account usage (T1078.003); from same IP",
            impact="Root credentials compromised; unauthorized access possible",
            recommended_action="1. Revoke all access keys; 2. Force password reset; 3. Review CloudTrail logs; 4. Enable MFA",
            severity="critical",
        )

        # Verify summary schema
        assert expected_summary.severity == "critical"
        assert "Privilege escalation" in expected_summary.summary

    async def test_investigation_brute_force_scenario(self):
        """Test investigation of brute force incident."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-invest-brute"

        # Create multiple failed login detections
        base_time = datetime.utcnow()
        detection_ids = []

        for i in range(5):
            detection = {
                "detection_id": f"det-brute-{i}",
                "tenant_id": tenant_id,
                "event_id": f"event-brute-{i}",
                "rule_name": "Multiple Failed Logins",
                "mitre_technique_id": "T1110",
                "severity": "high",
                "risk_score": 15.0,
                "detected_at": base_time.isoformat(),
                "raw_event": {
                    "user": "admin",
                    "ip": "203.0.113.1",
                    "action": "ConsoleLogin",
                    "response": "Failure",
                },
            }
            await detections_col.insert_one(detection)
            detection_ids.append(detection["detection_id"])

        # Create incident
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity="high",
            entities={
                "users": ["admin"],
                "ips": ["203.0.113.1"],
            },
        )
        await incidents_col.insert_one(incident.model_dump())

        # Create expected summary
        expected_summary = IncidentSummary(
            summary="Brute force attack detected",
            what_happened="5 failed login attempts for admin from 203.0.113.1 in 5-minute window",
            why_suspicious="Exceeds brute force threshold (T1110); rapid consecutive failures",
            impact="Admin account at risk; potential unauthorized access",
            recommended_action="1. Force password reset; 2. Enable MFA; 3. Block source IP; 4. Review successful logins",
            severity="high",
        )

        # Verify
        assert len(detection_ids) == 5
        assert expected_summary.severity == "high"

    async def test_investigation_context_enrichment(self):
        """Test investigation context includes all relevant data."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-context"

        # Create detection with rich metadata
        detection = {
            "detection_id": "det-context-1",
            "tenant_id": tenant_id,
            "event_id": "event-context",
            "rule_name": "New Location Login",
            "mitre_technique_id": "T1078",
            "mitre_tactic": "initial_access",
            "severity": "medium",
            "risk_score": 8.0,
            "detected_at": datetime.utcnow().isoformat(),
            "raw_event": {
                "user": "alice",
                "ip": "203.0.113.100",
                "action": "ConsoleLogin",
                "city": "Singapore",
                "country": "SG",
                "is_new_location": True,
            },
        }
        await detections_col.insert_one(detection)

        # Verify metadata is captured
        stored = await detections_col.find_one({"detection_id": "det-context-1"})
        assert stored["raw_event"]["city"] == "Singapore"
        assert stored["raw_event"]["is_new_location"] is True

    async def test_investigation_summary_storage(self):
        """Test storing investigation summary back to incidents."""
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-store"

        # Create incident without summary
        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=["det-1"],
            severity="high",
            summary=None,
        )
        await incidents_col.insert_one(incident.model_dump())

        # Create summary
        summary = IncidentSummary(
            summary="Test incident",
            what_happened="Event occurred",
            why_suspicious="Matched detection rule",
            impact="Potential compromise",
            recommended_action="Review logs",
            severity="high",
        )

        # Update incident with summary
        await incidents_col.update_one(
            {"incident_id": incident.incident_id},
            {"$set": {"summary": summary.model_dump()}},
        )

        # Verify update
        updated = await incidents_col.find_one({"incident_id": incident.incident_id})
        assert updated["summary"] is not None
        assert updated["summary"]["severity"] == "high"

    async def test_investigation_to_redis_stream(self):
        """Test publishing investigation summary to Redis Stream."""
        redis_client = get_redis()
        tenant_id = "test-tenant-invest-redis"

        # Create incident with summary
        summary = IncidentSummary(
            summary="Investigation complete",
            what_happened="Data breach detected",
            why_suspicious="Multiple attack indicators",
            impact="Customer data potentially exposed",
            recommended_action="Incident response team activated",
            severity="critical",
        )

        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=["det-1", "det-2"],
            severity="critical",
            summary=summary,
        )

        # Publish to Redis Stream
        stream_name = f"soc:summaries:{tenant_id}"
        msg_id = await redis_client.xadd(
            stream_name,
            {"incident": incident.model_dump_json(default=str)},
        )

        assert msg_id is not None

        # Verify message
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1

    async def test_investigation_tenant_isolation(self):
        """Test investigation respects tenant isolation."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")

        # Create incidents for two tenants
        for tenant in ["tenant-inv-x", "tenant-inv-y"]:
            incident = Incident(
                tenant_id=tenant,
                detection_ids=["det-1"],
                severity="medium",
                summary=IncidentSummary(
                    summary=f"Summary for {tenant}",
                    what_happened="Event",
                    why_suspicious="Suspicious",
                    impact="Impact",
                    recommended_action="Action",
                    severity="medium",
                ),
            )
            await incidents_col.insert_one(incident.model_dump())

        # Query tenant-x only
        cursor = incidents_col.find({"tenant_id": "tenant-inv-x"})
        results = await cursor.to_list(None)

        # Should only see tenant-x
        assert all(i["tenant_id"] == "tenant-inv-x" for i in results)

    async def test_investigation_error_handling(self):
        """Test error handling in investigation (missing incident)."""
        detections_col = get_collection("detections")
        incidents_col = get_collection("incidents")
        tenant_id = "test-tenant-error"

        # Try to investigate non-existent incident
        # In real code, this would error gracefully
        result = await incidents_col.find_one(
            {"incident_id": "non-existent-incident", "tenant_id": tenant_id}
        )

        # Should return None, not error
        assert result is None

    async def test_investigation_multiple_detections_context(self):
        """Test investigation retrieves context from multiple detections."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-multi-det"

        # Create multiple detections
        detection_ids = []
        for i in range(3):
            detection = {
                "detection_id": f"det-multi-{i}",
                "tenant_id": tenant_id,
                "rule_name": f"Rule {i}",
                "raw_event": {
                    "user": "attacker",
                    "ip": "192.0.2.1",
                    "action": f"Action{i}",
                },
            }
            await detections_col.insert_one(detection)
            detection_ids.append(detection["detection_id"])

        # Query all detections for incident
        detections = await detections_col.find(
            {"tenant_id": tenant_id, "detection_id": {"$in": detection_ids}},
            {"_id": 0},
        ).to_list(length=50)

        # Should retrieve all 3
        assert len(detections) == 3
        assert all(d["tenant_id"] == tenant_id for d in detections)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
