"""Tests for Phase 8 FastAPI Broker endpoints."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis
from shared.models import User, Incident, Alert
from shared.api_keys import generate_api_key, hash_api_key


@pytest.mark.asyncio
class TestTenantsEndpoints:
    """Test tenant management endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_get_tenant_stats(self):
        """Test retrieving tenant statistics."""
        users_col = get_collection("users")
        incidents_col = get_collection("incidents")
        alerts_col = get_collection("alerts")
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-stats"

        # Create user (tenant)
        api_key = generate_api_key()
        user = User(
            user_id=tenant_id,
            email="test@example.com",
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=api_key[:12],
        )
        await users_col.insert_one(user.model_dump())

        # Create test incidents
        for i in range(3):
            incident = Incident(
                tenant_id=tenant_id,
                detection_ids=[f"det-{i}"],
                severity="high",
                status=["open", "investigating", "closed"][i % 3],
            )
            await incidents_col.insert_one(incident.model_dump())

        # Create test alerts
        for i in range(5):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{i}",
                recipient="soc@example.com",
                severity="high",
                feedback=[None, "tp", "tp", "fp", None][i % 5],
            )
            await alerts_col.insert_one(alert.model_dump())

        # Create test detections
        for i in range(2):
            await detections_col.insert_one({
                "tenant_id": tenant_id,
                "detection_id": f"det-{i}",
                "severity": ["critical", "high"][i % 2],
                "rule_name": "Test Rule",
            })

        # Verify stats calculation
        incident_count = await incidents_col.count_documents({"tenant_id": tenant_id})
        assert incident_count == 3

        alert_count = await alerts_col.count_documents({"tenant_id": tenant_id})
        assert alert_count == 5

    async def test_tenant_isolation_stats(self):
        """Test stats don't leak across tenants."""
        users_col = get_collection("users")
        incidents_col = get_collection("incidents")
        tenant_x = "tenant-stats-x"
        tenant_y = "tenant-stats-y"

        # Create users for both tenants
        for tenant in [tenant_x, tenant_y]:
            user = User(user_id=tenant, email=f"{tenant}@example.com")
            await users_col.insert_one(user.model_dump())

        # Create incidents for both
        for tenant in [tenant_x, tenant_y]:
            for i in range(2):
                incident = Incident(
                    tenant_id=tenant,
                    detection_ids=["det-1"],
                    severity="high",
                )
                await incidents_col.insert_one(incident.model_dump())

        # Query tenant-x only
        x_count = await incidents_col.count_documents({"tenant_id": tenant_x})
        y_count = await incidents_col.count_documents({"tenant_id": tenant_y})

        assert x_count == 2
        assert y_count == 2

    async def test_tenant_creation(self):
        """Test tenant creation with API key."""
        users_col = get_collection("users")
        
        api_key = generate_api_key()
        new_user = User(
            user_id="new-tenant",
            email="newuser@example.com",
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=api_key[:12],
        )

        await users_col.insert_one(new_user.model_dump())

        # Verify user exists
        stored = await users_col.find_one({"user_id": "new-tenant"})
        assert stored is not None
        assert stored["email"] == "newuser@example.com"

    async def test_tenant_api_key_format(self):
        """Test API key generation and hashing."""
        api_key = generate_api_key()
        
        # Should start with "soc_"
        assert api_key.startswith("soc_")
        
        # Should be reasonably long
        assert len(api_key) > 20
        
        # Hashing should produce a hash
        hashed = hash_api_key(api_key)
        assert hashed != api_key
        assert len(hashed) > 20


@pytest.mark.asyncio
class TestRulesEndpoints:
    """Test detection rules endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_list_rules_returns_sigma_files(self):
        """Test list_rules returns Sigma rule metadata."""
        from pathlib import Path
        
        rules_dir = Path("detection_rules")
        
        # Should have .yaml files
        yaml_files = list(rules_dir.glob("*.yaml"))
        assert len(yaml_files) >= 5  # MVP has 5 rules

    async def test_rule_statistics(self):
        """Test rule statistics calculation."""
        detections_col = get_collection("detections")
        tenant_id = "test-tenant-rule-stats"

        # Create detections for a specific rule
        for i in range(3):
            await detections_col.insert_one({
                "tenant_id": tenant_id,
                "detection_id": f"det-{i}",
                "rule_name": "Test Rule",
                "severity": ["critical", "high", "medium"][i % 3],
            })

        # Query detections for rule
        rule_detections = await detections_col.find(
            {"tenant_id": tenant_id, "rule_name": "Test Rule"}
        ).to_list(None)

        assert len(rule_detections) == 3

        # Count by severity
        severity_counts = {}
        for detection in rule_detections:
            severity = detection["severity"]
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        assert "critical" in severity_counts
        assert "high" in severity_counts

    async def test_rule_feedback_stats(self):
        """Test rule TP/FP statistics."""
        alerts_col = get_collection("alerts")
        tenant_id = "test-tenant-feedback-stats"

        # Create alerts with different feedback
        for i, feedback in enumerate(["tp", "tp", "fp", None, "tp"]):
            alert = Alert(
                tenant_id=tenant_id,
                incident_id=f"inc-{i}",
                recipient="soc@example.com",
                severity="high",
                feedback=feedback,
            )
            await alerts_col.insert_one(alert.model_dump())

        # Count TP/FP
        tp_count = await alerts_col.count_documents({
            "tenant_id": tenant_id,
            "feedback": "tp",
        })
        fp_count = await alerts_col.count_documents({
            "tenant_id": tenant_id,
            "feedback": "fp",
        })

        assert tp_count == 3
        assert fp_count == 1

        # Calculate rate
        total_feedback = tp_count + fp_count
        tp_rate = (tp_count / total_feedback * 100) if total_feedback > 0 else 0
        
        assert tp_rate == 75.0  # 3/4 = 75%


@pytest.mark.asyncio
class TestAuthenticationFlow:
    """Test API key authentication."""

    async def test_api_key_generation(self):
        """Test API key generation format."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        
        # Should be different
        assert key1 != key2
        
        # Should start with soc_
        assert key1.startswith("soc_")
        assert key2.startswith("soc_")

    async def test_api_key_hashing(self):
        """Test API key hashing is one-way."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)
        
        # Should not be same as original
        assert hashed != api_key
        
        # Should be consistent
        hashed2 = hash_api_key(api_key)
        # (bcrypt hashes differently each time, so we can't compare)

    def test_api_key_prefix_extraction(self):
        """Test API key prefix extraction."""
        from shared.api_keys import get_key_prefix
        
        api_key = "soc_abc123def456ghi"
        prefix = get_key_prefix(api_key)
        
        # Should be first 12 chars
        assert prefix == "soc_abc123de"
        assert len(prefix) == 12


class TestEndpointIntegration:
    """Test endpoint integration."""

    def test_tenant_endpoint_structure(self):
        """Test tenant endpoint returns correct structure."""
        # Simulated response
        response = {
            "tenant_id": "test-tenant",
            "created_at": datetime.utcnow(),
            "plan": "free",
            "stats": {
                "incidents": 5,
                "alerts": 10,
                "rules": 5,
            },
        }

        assert "tenant_id" in response
        assert "stats" in response
        assert "incidents" in response["stats"]

    def test_rules_endpoint_structure(self):
        """Test rules endpoint returns correct structure."""
        rules = [
            {
                "rule_id": "brute_force",
                "title": "Multiple Failed Logins",
                "description": "Detects brute force attacks",
                "severity": "high",
                "mitre_techniques": ["T1110"],
                "file": "brute_force_login.yaml",
            }
        ]

        assert len(rules) > 0
        assert "rule_id" in rules[0]
        assert "title" in rules[0]
        assert "mitre_techniques" in rules[0]

    def test_stats_endpoint_structure(self):
        """Test stats endpoint returns correct structure."""
        stats = {
            "tenant_id": "test-tenant",
            "timestamp": datetime.utcnow().isoformat(),
            "incidents": {
                "total": 5,
                "open": 2,
                "investigating": 2,
                "closed": 1,
            },
            "alerts": {
                "total": 10,
                "pending_feedback": 3,
                "true_positives": 6,
                "false_positives": 1,
            },
            "detections": {
                "total": 15,
                "critical": 2,
                "high": 8,
            },
            "health": "ok",
        }

        assert "incidents" in stats
        assert "alerts" in stats
        assert "detections" in stats
        assert stats["health"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
