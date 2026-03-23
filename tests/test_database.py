"""Integration tests for MongoDB and Redis database layers."""

import pytest
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncClient
import redis.asyncio as aioredis

from shared.models import NormalizedEvent, DetectionEvent, Incident, Alert
from shared.config import settings
from db.mongo import get_db, connect_mongo, close_mongo, get_collection
from db.redis_client import connect_redis, close_redis, get_redis
from db.redis_streams import RedisStreamHelper, provision_tenant_streams


@pytest.mark.asyncio
class TestMongoDBIndexes:
    """Test MongoDB index creation and queries."""

    @pytest.fixture(autouse=True)
    async def setup_mongo(self):
        """Connect to MongoDB before tests."""
        await connect_mongo()
        yield
        await close_mongo()

    async def test_events_collection_indexes(self):
        """Test events collection has required indexes."""
        events = get_collection("events")
        indexes = await events.list_indexes().to_list(None)
        index_names = [idx["name"] for idx in indexes]

        # Should have (tenant_id, timestamp) compound index
        assert any("tenant_id" in idx["key"] for idx in indexes)

    async def test_detections_collection_indexes(self):
        """Test detections collection has required indexes."""
        detections = get_collection("detections")
        indexes = await detections.list_indexes().to_list(None)

        # Should have compound indexes on (tenant_id, detected_at) and (tenant_id, severity)
        assert len(indexes) >= 3  # Default _id + at least 2 custom indexes

    async def test_incidents_collection_indexes(self):
        """Test incidents collection has required indexes."""
        incidents = get_collection("incidents")
        indexes = await incidents.list_indexes().to_list(None)

        # Should have indexes on (tenant_id, status) and (tenant_id, created_at)
        assert len(indexes) >= 3

    async def test_alerts_collection_indexes(self):
        """Test alerts collection has required indexes."""
        alerts = get_collection("alerts")
        indexes = await alerts.list_indexes().to_list(None)

        # Should have index on (tenant_id, incident_id)
        assert len(indexes) >= 2


@pytest.mark.asyncio
class TestRedisStreams:
    """Test Redis Stream operations."""

    @pytest.fixture(autouse=True)
    async def setup_redis(self):
        """Connect to Redis before tests."""
        await connect_redis()
        yield
        await close_redis()

    async def test_redis_connection(self):
        """Test Redis connection is working."""
        redis_client = get_redis()
        pong = await redis_client.ping()
        assert pong is True

    async def test_stream_helper_publish_normalized_event(self):
        """Test publishing NormalizedEvent to Redis Stream."""
        redis_client = get_redis()
        helper = RedisStreamHelper(redis_client)

        tenant_id = "test-tenant-1"
        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="test-user",
            ip="192.0.2.1",
            action="ConsoleLogin",
        )

        msg_id = await helper.publish_normalized_event(tenant_id, event)
        assert msg_id is not None

        # Verify message was published
        stream_key = f"soc:events:{tenant_id}"
        stream_len = await redis_client.xlen(stream_key)
        assert stream_len >= 1

    async def test_stream_helper_create_consumer_group(self):
        """Test creating consumer group."""
        redis_client = get_redis()
        helper = RedisStreamHelper(redis_client)

        stream_name = "test:stream:1"
        group_name = "test_group"

        # Create consumer group (should not error even if repeated)
        await helper.create_consumer_group(stream_name, group_name)
        await helper.create_consumer_group(stream_name, group_name)  # Idempotent

        # Verify group exists
        groups = await redis_client.xinfo_groups(stream_name)
        group_names = [g["name"] for g in groups]
        assert group_name in group_names

    async def test_provision_tenant_streams(self):
        """Test provisioning all streams for a tenant."""
        redis_client = get_redis()
        tenant_id = "test-tenant-provision"

        await provision_tenant_streams(redis_client, tenant_id)

        # Verify all 4 stream groups created
        for stage in ["events", "detections", "incidents", "summaries"]:
            stream_name = f"soc:{stage}:{tenant_id}"
            groups = await redis_client.xinfo_groups(stream_name)
            assert len(groups) > 0


@pytest.mark.asyncio
class TestDataPersistence:
    """Test data persistence across MongoDB and Redis."""

    @pytest.fixture(autouse=True)
    async def setup_dbs(self):
        """Connect to both databases."""
        await connect_mongo()
        await connect_redis()
        yield
        await close_mongo()
        await close_redis()

    async def test_normalized_event_storage_and_retrieval(self):
        """Test storing and retrieving NormalizedEvent from MongoDB."""
        events = get_collection("events")
        tenant_id = "test-tenant-data"

        event = NormalizedEvent(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            source="cloudtrail",
            user="data-test",
            ip="192.0.2.100",
            action="PutObject",
            metadata={"bucket": "test-bucket"},
        )

        # Insert
        result = await events.insert_one(event.model_dump())
        assert result.inserted_id is not None

        # Retrieve
        retrieved = await events.find_one({"event_id": event.event_id})
        assert retrieved is not None
        assert retrieved["user"] == "data-test"
        assert retrieved["metadata"]["bucket"] == "test-bucket"

    async def test_tenant_isolation_query(self):
        """Test that tenant_id queries properly isolate data."""
        events = get_collection("events")
        now = datetime.utcnow()

        # Insert events for different tenants
        event1 = NormalizedEvent(
            tenant_id="tenant-a",
            timestamp=now,
            source="cloudtrail",
            user="user-a",
            ip="192.0.2.1",
            action="ListBuckets",
        )
        event2 = NormalizedEvent(
            tenant_id="tenant-b",
            timestamp=now,
            source="cloudtrail",
            user="user-b",
            ip="192.0.2.2",
            action="DeleteBucket",
        )

        await events.insert_one(event1.model_dump())
        await events.insert_one(event2.model_dump())

        # Query for tenant-a only
        cursor = events.find({"tenant_id": "tenant-a"})
        results = await cursor.to_list(None)

        # Should only find tenant-a events
        assert all(e["tenant_id"] == "tenant-a" for e in results)
        assert not any(e["user"] == "user-b" for e in results)

    async def test_index_query_performance(self):
        """Test that indexed queries use indexes efficiently."""
        detections = get_collection("detections")
        tenant_id = "test-tenant-perf"

        # Insert multiple detections
        for i in range(100):
            detection = DetectionEvent(
                tenant_id=tenant_id,
                event_id=f"event-{i}",
                rule_id=f"rule-{i % 5}",
                rule_name="Test Rule",
                mitre_technique_id="T1110",
                mitre_tactic="Credential Access",
                severity="high" if i % 2 == 0 else "medium",
                risk_score=50.0 + i,
            )
            await detections.insert_one(detection.model_dump())

        # Query using indexed fields
        cursor = detections.find(
            {"tenant_id": tenant_id, "severity": "high"},
            {"hint": [("tenant_id", 1), ("severity", 1)]},
        )
        results = await cursor.to_list(None)

        # Should retrieve expected results
        assert len(results) == 50
        assert all(d["severity"] == "high" for d in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
