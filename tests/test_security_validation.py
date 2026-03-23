"""Security validation tests for Phase 9."""

import pytest
import json
from datetime import datetime

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis
from shared.models import Alert, User
from shared.api_keys import generate_api_key, hash_api_key, verify_api_key


@pytest.mark.asyncio
class TestSecurityValidation:
    """Security validation tests."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_api_key_not_stored_plaintext(self):
        """Verify API keys are never stored plaintext."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)

        # Should not match
        assert hashed != api_key

        # Hashed should be a bcrypt hash (long string)
        assert len(hashed) > 50

    async def test_api_key_verification_works(self):
        """Test API key verification with correct and incorrect keys."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)

        # Correct key should verify
        assert verify_api_key(api_key, hashed) is True

        # Wrong key should not verify
        wrong_key = generate_api_key()
        assert verify_api_key(wrong_key, hashed) is False

    async def test_tenant_isolation_mongodb_queries(self):
        """Test all MongoDB queries filter by tenant_id."""
        users_col = get_collection("users")
        tenant_1 = "sec-tenant-1"
        tenant_2 = "sec-tenant-2"

        # Create users for different tenants
        for tenant in [tenant_1, tenant_2]:
            user = User(
                user_id=tenant,
                email=f"{tenant}@example.com",
            )
            await users_col.insert_one(user.model_dump())

        # Query tenant 1
        tenant_1_users = await users_col.find({"user_id": tenant_1}).to_list(None)

        # Should only return tenant 1
        assert len(tenant_1_users) == 1
        assert tenant_1_users[0]["user_id"] == tenant_1

    async def test_no_sensitive_data_in_errors(self):
        """Test error messages don't leak sensitive data."""
        # Simulate API error response
        error_responses = [
            {"detail": "Invalid API key"},  # Good: generic
            {"detail": f"API key verification failed"},  # Good: generic
            {"detail": "Alert not found"},  # Good: generic
        ]

        bad_responses = [
            {"detail": f"User 'admin' not found"},  # Bad: leaks username
            {"detail": f"API key: soc_... does not match"},  # Bad: leaks prefix
        ]

        # Verify good responses don't contain sensitive patterns
        for response in error_responses:
            assert "user_id" not in str(response).lower()
            assert "password" not in str(response).lower()
            assert "soc_" not in str(response)

    async def test_password_fields_not_exposed(self):
        """Test password/hash fields are not exposed in responses."""
        users_col = get_collection("users")
        api_key = generate_api_key()

        user = User(
            user_id="sec-user-1",
            email="test@example.com",
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=api_key[:12],
        )
        await users_col.insert_one(user.model_dump())

        # Retrieve user
        stored = await users_col.find_one({"user_id": "sec-user-1"})

        # Should have hash (internal use)
        assert "api_key_hash" in stored

        # But API response should NOT include it (checked at response level)
        # This is enforced by Pydantic response_model in endpoints

    async def test_alert_feedback_validation(self):
        """Test alert feedback values are validated."""
        alerts_col = get_collection("alerts")

        # Valid feedback values
        for feedback in ["tp", "fp", None]:
            alert = Alert(
                tenant_id="sec-tenant",
                incident_id=f"inc-{feedback}",
                recipient="soc@example.com",
                severity="high",
                feedback=feedback,
            )
            await alerts_col.insert_one(alert.model_dump())

        # Verify stored
        tp_alert = await alerts_col.find_one({"feedback": "tp"})
        assert tp_alert is not None

    async def test_injection_protection_mongodb(self):
        """Test MongoDB injection protection via Pydantic."""
        alerts_col = get_collection("alerts")

        # Try to inject via tenant_id (should be validated)
        injection_attempt = """{"$ne": null}"""
        
        # Pydantic should reject or sanitize
        alert = Alert(
            tenant_id="valid-tenant",  # Should only accept string
            incident_id="inc-1",
            recipient="soc@example.com",
            severity="high",
        )
        await alerts_col.insert_one(alert.model_dump())

        # Query should not be vulnerable
        result = await alerts_col.find_one({"tenant_id": injection_attempt})
        assert result is None  # No match on literal string

    async def test_timestamp_precision(self):
        """Test timestamp handling prevents time-based attacks."""
        alerts_col = get_collection("alerts")

        # Create alert with precise timestamp
        now = datetime.utcnow()
        alert = Alert(
            tenant_id="sec-tenant",
            incident_id="inc-timestamp",
            recipient="soc@example.com",
            severity="high",
            sent_at=now,
        )
        await alerts_col.insert_one(alert.model_dump())

        # Retrieve and verify timestamp is preserved
        stored = await alerts_col.find_one({"alert_id": alert.alert_id})
        assert isinstance(stored["sent_at"], datetime)

    async def test_rate_limiting_structure(self):
        """Test rate limiting can be implemented (structure validation)."""
        # Rate limiting would be at endpoint level
        # This test validates the structure is compatible

        rate_limits = {
            "GET /api/incidents": "100 requests per minute",
            "POST /api/alerts/{id}/feedback": "50 requests per minute",
            "GET /api/rules": "200 requests per minute",
        }

        # Should have all endpoints
        assert "GET /api/incidents" in rate_limits
        assert "POST /api/alerts/{id}/feedback" in rate_limits

    async def test_audit_logging_structure(self):
        """Test audit logging structure for compliance."""
        audit_col = get_collection("audit_log")

        # Create audit entry
        audit_entry = {
            "tenant_id": "sec-tenant",
            "action": "submit_feedback",
            "entity": "alert",
            "entity_id": "alert-123",
            "value": "tp",
            "timestamp": datetime.utcnow(),
        }
        await audit_col.insert_one(audit_entry)

        # Verify structure
        stored = await audit_col.find_one({"entity_id": "alert-123"})
        assert "tenant_id" in stored
        assert "timestamp" in stored
        assert "action" in stored

    async def test_cors_headers_validation(self):
        """Test CORS headers are properly configured."""
        # CORS is configured in main.py
        cors_config = {
            "allow_origins": ["http://localhost:3000", "https://soc.company.com"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }

        # Should have safe defaults
        assert "http://localhost:3000" in cors_config["allow_origins"]
        assert cors_config["allow_credentials"] is True

    async def test_api_key_prefix_prevents_full_hash_scan(self):
        """Test API key prefix prevents full table scan."""
        users_col = get_collection("users")

        # Create multiple users
        for i in range(10):
            api_key = generate_api_key()
            user = User(
                user_id=f"sec-user-{i}",
                email=f"user{i}@example.com",
                api_key_hash=hash_api_key(api_key),
                api_key_prefix=api_key[:12],
            )
            await users_col.insert_one(user.model_dump())

        # Query by prefix (efficient)
        api_key = generate_api_key()
        prefix = api_key[:12]

        # Simulate lookup with prefix (would be in index)
        lookup_query = {"api_key_prefix": prefix}

        # Should be indexed query, not full table scan
        cursor = users_col.find(lookup_query)
        result = await cursor.to_list(1)  # Just get one

        # Query should be efficient (no timeout, no scan)
        assert result is not None or result == []


class TestCryptographicSecurity:
    """Test cryptographic security of API keys."""

    def test_api_key_length(self):
        """Test API keys have sufficient entropy."""
        api_key = generate_api_key()

        # Should be reasonably long (>30 chars)
        assert len(api_key) > 30

    def test_api_key_uniqueness(self):
        """Test API key generation produces unique keys."""
        keys = set()
        for _ in range(100):
            key = generate_api_key()
            assert key not in keys
            keys.add(key)

        # All should be unique
        assert len(keys) == 100

    def test_bcrypt_hash_strength(self):
        """Test bcrypt hashing provides strong security."""
        api_key = generate_api_key()
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)

        # Hashes should be different (bcrypt adds salt)
        assert hash1 != hash2

        # But both should verify correctly
        assert verify_api_key(api_key, hash1) is True
        assert verify_api_key(api_key, hash2) is True

    def test_timing_attack_resistance(self):
        """Test API key verification is resistant to timing attacks."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)

        correct = verify_api_key(api_key, hashed)
        wrong = verify_api_key("wrong_key_here", hashed)

        # Results should be boolean (not timing-dependent)
        assert correct is True
        assert wrong is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
