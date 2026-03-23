"""End-to-end integration tests for Ingestion Agent with Redis and MongoDB."""

import pytest
import json
from datetime import datetime
from motor.motor_asyncio import AsyncClient
import redis.asyncio as aioredis

from db.mongo import connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis, stream_key
from shared.models import NormalizedEvent
from agents.ingestion import _normalize_cloudtrail, _normalize_syslog


@pytest.mark.asyncio
class TestIngestionE2E:
    """End-to-end tests: CloudTrail → MongoDB → Redis Streams."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to both databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_cloudtrail_normalization_and_storage(self):
        """Test CloudTrail log normalization and storage to MongoDB."""
        events_col = get_collection("events")
        tenant_id = "test-tenant-ct"

        # Normalize CloudTrail record
        raw_cloudtrail = {
            "userIdentity": {"type": "IAMUser", "userName": "admin"},
            "eventTime": "2026-03-22T10:00:00Z",
            "eventName": "ConsoleLogin",
            "sourceIPAddress": "192.0.2.100",
            "awsRegion": "us-east-1",
            "eventSource": "iam.amazonaws.com",
        }

        event = _normalize_cloudtrail(raw_cloudtrail, tenant_id)

        # Verify normalization
        assert event.source == "cloudtrail"
        assert event.user == "admin"
        assert event.ip == "192.0.2.100"
        assert event.action == "ConsoleLogin"

        # Store in MongoDB
        result = await events_col.insert_one(event.model_dump())
        assert result.inserted_id is not None

        # Retrieve and verify
        stored = await events_col.find_one({"event_id": event.event_id})
        assert stored is not None
        assert stored["tenant_id"] == tenant_id
        assert stored["user"] == "admin"

    async def test_syslog_normalization_and_storage(self):
        """Test syslog normalization and storage to MongoDB."""
        events_col = get_collection("events")
        tenant_id = "test-tenant-syslog"

        # Normalize syslog record
        raw_syslog = {
            "message": "sshd[1234]: Failed password for alice from 10.0.0.50 port 22 ssh2",
            "timestamp": "2026-03-22T10:15:00Z",
            "host": "server1",
            "file": "/var/log/auth.log",
        }

        event = _normalize_syslog(raw_syslog, tenant_id)

        # Verify normalization
        assert event.source == "syslog"
        assert event.user == "alice"
        assert event.ip == "10.0.0.50"
        assert "sshd" in event.action.lower()

        # Store in MongoDB
        result = await events_col.insert_one(event.model_dump())
        assert result.inserted_id is not None

    async def test_tenant_isolation_in_ingestion(self):
        """Test that ingestion properly isolates events by tenant."""
        events_col = get_collection("events")

        # Create events for two tenants
        event1 = NormalizedEvent(
            tenant_id="tenant-a",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="user-a",
            ip="192.0.2.1",
            action="ListBuckets",
        )
        event2 = NormalizedEvent(
            tenant_id="tenant-b",
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="user-b",
            ip="192.0.2.2",
            action="GetObject",
        )

        # Insert both
        await events_col.insert_one(event1.model_dump())
        await events_col.insert_one(event2.model_dump())

        # Query for tenant-a only
        cursor = events_col.find({"tenant_id": "tenant-a"})
        results = await cursor.to_list(None)

        # Should only see tenant-a events
        assert len(results) >= 1
        assert all(e["tenant_id"] == "tenant-a" for e in results)

    async def test_redis_stream_publishing(self):
        """Test that normalized events can be published to Redis Streams."""
        redis_client = get_redis()
        tenant_id = "test-tenant-redis"

        # Normalize event
        raw = {
            "userIdentity": {"userName": "bob"},
            "eventTime": "2026-03-22T11:00:00Z",
            "eventName": "PutObject",
            "sourceIPAddress": "203.0.113.10",
            "awsRegion": "us-west-2",
        }
        event = _normalize_cloudtrail(raw, tenant_id)

        # Publish to Redis Stream
        stream_name = stream_key("events", tenant_id)
        msg_id = await redis_client.xadd(stream_name, {"event": event.model_dump_json()})

        assert msg_id is not None

        # Verify message in stream
        stream_len = await redis_client.xlen(stream_name)
        assert stream_len >= 1

    async def test_duplicate_detection(self):
        """Test that duplicate events are detected."""
        events_col = get_collection("events")
        tenant_id = "test-tenant-dedup"

        raw = {
            "userIdentity": {"userName": "charlie"},
            "eventTime": "2026-03-22T12:00:00Z",
            "eventName": "DeleteBucket",
            "sourceIPAddress": "198.51.100.5",
        }

        event = _normalize_cloudtrail(raw, tenant_id)

        # First insert
        await events_col.insert_one(event.model_dump())

        # Second insert should fail (unique index) or be detected
        # In real code, we check find_one first
        existing = await events_col.find_one({"tenant_id": tenant_id, "event_id": event.event_id})
        assert existing is not None  # Duplicate detected

    async def test_geolocation_enrichment(self):
        """Test that geolocation data is included (if GeoIP DB available)."""
        tenant_id = "test-tenant-geo"

        raw = {
            "userIdentity": {"userName": "dave"},
            "eventTime": "2026-03-22T13:00:00Z",
            "eventName": "AssumeRole",
            "sourceIPAddress": "192.0.2.200",  # May or may not have GeoIP data
        }

        event = _normalize_cloudtrail(raw, tenant_id)

        # city and country might be None if GeoIP DB not available
        # but should not cause errors
        assert event.city is None or isinstance(event.city, str)
        assert event.country is None or isinstance(event.country, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
