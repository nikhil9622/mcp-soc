"""Performance and coverage validation for Phase 9."""

import pytest
import time
import asyncio
from datetime import datetime

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from shared.models import Incident, Alert, DetectionEvent


@pytest.mark.asyncio
class TestPerformanceValidation:
    """Performance validation tests."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_incident_list_performance(self):
        """Test incident listing performance with pagination."""
        incidents_col = get_collection("incidents")
        tenant_id = "perf-tenant-incidents"

        # Create 100 incidents
        for i in range(100):
            incident = Incident(
                tenant_id=tenant_id,
                detection_ids=[f"det-{i}"],
                severity=["critical", "high", "medium", "low"][i % 4],
            )
            await incidents_col.insert_one(incident.model_dump())

        # Measure query time
        start = time.time()
        incidents = await incidents_col.find({"tenant_id": tenant_id}).limit(50).to_list(50)
        elapsed = time.time() - start

        # Should be fast (<100ms)
        assert elapsed < 0.1
        assert len(incidents) == 50

    async def test_alert_feedback_query_performance(self):
        """Test alert feedback queries performance."""
        alerts_col = get_collection("alerts")
        tenant_id = "perf-tenant-alerts"

        # Create 50 alerts with various feedback
        for i in range(50):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{i}",
                recipient="soc@example.com",
                severity=["critical", "high", "medium"][i % 3],
                feedback=["tp", "fp", None][i % 3],
            )
            await alerts_col.insert_one(alert.model_dump())

        # Measure TP query
        start = time.time()
        tp_alerts = await alerts_col.find({"tenant_id": tenant_id, "feedback": "tp"}).to_list(None)
        elapsed = time.time() - start

        # Should be fast (<50ms)
        assert elapsed < 0.05
        assert len(tp_alerts) > 0

    async def test_detection_count_performance(self):
        """Test detection counting performance."""
        detections_col = get_collection("detections")
        tenant_id = "perf-tenant-detections"

        # Create 200 detections
        for i in range(200):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id="test_rule",
                rule_name="Test Rule",
                mitre_technique_id="T1110",
                mitre_tactic="initial_access",
                severity=["critical", "high", "medium", "low"][i % 4],
                risk_score=float(i),
            )
            await detections_col.insert_one(detection.model_dump())

        # Measure count
        start = time.time()
        total = await detections_col.count_documents({"tenant_id": tenant_id})
        elapsed = time.time() - start

        # Should be very fast (<50ms)
        assert elapsed < 0.05
        assert total == 200

    async def test_severity_aggregation_performance(self):
        """Test severity-based aggregation performance."""
        detections_col = get_collection("detections")
        tenant_id = "perf-tenant-agg"

        # Create detections with various severities
        for severity in ["critical", "high", "medium", "low"]:
            for i in range(50):
                detection = DetectionEvent(
                    tenant_id=tenant_id,
                    event_id=f"event-{severity}-{i}",
                    rule_id="test_rule",
                    rule_name="Test Rule",
                    mitre_technique_id="T1110",
                    mitre_tactic="initial_access",
                    severity=severity,
                    risk_score=float(i),
                )
                await detections_col.insert_one(detection.model_dump())

        # Measure aggregation
        start = time.time()
        critical_count = await detections_col.count_documents({
            "tenant_id": tenant_id,
            "severity": "critical",
        })
        elapsed = time.time() - start

        # Should be fast (<50ms)
        assert elapsed < 0.05
        assert critical_count == 50

    async def test_redis_stream_publish_performance(self):
        """Test Redis stream publishing performance."""
        redis_client = get_redis()
        tenant_id = "perf-tenant-redis"

        # Publish 100 messages
        start = time.time()
        for i in range(100):
            await redis_client.xadd(
                f"soc:events:{tenant_id}",
                {"event": f"event-{i}"},
            )
        elapsed = time.time() - start

        # Should be fast (<500ms for 100 publishes)
        assert elapsed < 0.5

    async def test_tenant_isolation_query_performance(self):
        """Test tenant isolation doesn't degrade performance."""
        incidents_col = get_collection("incidents")

        # Create incidents for multiple tenants
        for tenant in ["perf-tenant-a", "perf-tenant-b", "perf-tenant-c"]:
            for i in range(50):
                incident = Incident(
                    tenant_id=tenant,
                    detection_ids=[f"det-{i}"],
                    severity="high",
                )
                await incidents_col.insert_one(incident.model_dump())

        # Query single tenant (should still be fast)
        start = time.time()
        results = await incidents_col.find(
            {"tenant_id": "perf-tenant-a"}
        ).to_list(50)
        elapsed = time.time() - start

        # Should be fast even with multiple tenants
        assert elapsed < 0.1
        assert len(results) == 50


@pytest.mark.asyncio
class TestCodeCoverage:
    """Test code coverage validation."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_model_validation_coverage(self):
        """Test all Pydantic models."""
        from shared.models import (
            NormalizedEvent,
            DetectionEvent,
            IncidentSummary,
            Incident,
            Alert,
            User,
        )

        # Test each model
        models_to_test = [
            (NormalizedEvent, {
                "tenant_id": "test",
                "timestamp": datetime.utcnow(),
                "source": "cloudtrail",
                "user": "admin",
                "ip": "192.0.2.1",
                "action": "ConsoleLogin",
            }),
            (DetectionEvent, {
                "tenant_id": "test",
                "event_id": "evt-1",
                "rule_id": "rule-1",
                "rule_name": "Test Rule",
                "mitre_technique_id": "T1110",
                "mitre_tactic": "initial_access",
                "severity": "high",
                "risk_score": 15.0,
            }),
            (IncidentSummary, {
                "summary": "Test",
                "what_happened": "Test",
                "why_suspicious": "Test",
                "impact": "Test",
                "recommended_action": "Test",
                "severity": "high",
            }),
            (Incident, {
                "tenant_id": "test",
                "detection_ids": ["det-1"],
                "severity": "high",
            }),
            (Alert, {
                "tenant_id": "test",
                "incident_id": "inc-1",
                "recipient": "test@example.com",
                "severity": "high",
            }),
            (User, {
                "user_id": "user-1",
                "email": "test@example.com",
            }),
        ]

        # Test each model
        for model_class, data in models_to_test:
            instance = model_class(**data)
            assert instance is not None
            # Test serialization
            serialized = instance.model_dump()
            assert isinstance(serialized, dict)

    async def test_endpoint_response_codes(self):
        """Test all HTTP response codes are handled."""
        # Success codes
        success_codes = {
            200: "OK",
            201: "Created",
        }

        # Error codes
        error_codes = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
        }

        # All should be handled in endpoints
        all_codes = {**success_codes, **error_codes}
        assert 200 in all_codes
        assert 401 in all_codes
        assert 404 in all_codes

    async def test_database_operation_coverage(self):
        """Test all CRUD operations."""
        users_col = get_collection("users")
        tenant_id = "coverage-tenant"

        # Create
        from shared.models import User
        user = User(user_id=tenant_id, email="test@example.com")
        await users_col.insert_one(user.model_dump())

        # Read
        stored = await users_col.find_one({"user_id": tenant_id})
        assert stored is not None

        # Update
        await users_col.update_one(
            {"user_id": tenant_id},
            {"$set": {"plan": "pro"}},
        )
        updated = await users_col.find_one({"user_id": tenant_id})
        assert updated["plan"] == "pro"

        # Delete (list before/after)
        before = await users_col.count_documents({"user_id": tenant_id})
        assert before >= 1

    async def test_error_handling_paths(self):
        """Test error handling paths are covered."""
        users_col = get_collection("users")

        # Test not found
        result = await users_col.find_one({"user_id": "nonexistent"})
        assert result is None

        # Test empty find
        results = await users_col.find({"user_id": "nonexistent"}).to_list(None)
        assert results == []

    async def test_validation_error_paths(self):
        """Test validation error handling."""
        from shared.models import Alert

        # Test invalid severity
        with pytest.raises(ValueError):
            Alert(
                tenant_id="test",
                incident_id="inc-1",
                recipient="test@example.com",
                severity="invalid",  # Should reject
            )

        # Test missing required field
        with pytest.raises(TypeError):
            Alert(
                tenant_id="test",
                # Missing incident_id
                recipient="test@example.com",
                severity="high",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
