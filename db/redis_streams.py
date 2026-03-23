"""Redis Stream utilities for MCP SOC event processing."""

import json
from typing import Any
import redis.asyncio as aioredis
from shared.models import NormalizedEvent, DetectionEvent, Incident, Alert


class RedisStreamHelper:
    """Helper class for Redis Stream operations with automatic JSON serialization."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to string for Redis Stream."""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize a string value from Redis Stream."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def publish_normalized_event(
        self, tenant_id: str, event: NormalizedEvent
    ) -> str:
        """Publish a NormalizedEvent to Redis Stream."""
        key = f"soc:events:{tenant_id}"
        data = event.model_dump_json()
        msg_id = await self.redis.xadd(key, {"event": data})
        return msg_id

    async def publish_detection_event(
        self, tenant_id: str, detection: DetectionEvent
    ) -> str:
        """Publish a DetectionEvent to Redis Stream."""
        key = f"soc:detections:{tenant_id}"
        data = detection.model_dump_json()
        msg_id = await self.redis.xadd(key, {"detection": data})
        return msg_id

    async def publish_incident(self, tenant_id: str, incident: Incident) -> str:
        """Publish an Incident to Redis Stream."""
        key = f"soc:incidents:{tenant_id}"
        data = incident.model_dump_json()
        msg_id = await self.redis.xadd(key, {"incident": data})
        return msg_id

    async def publish_alert(self, tenant_id: str, alert: Alert) -> str:
        """Publish an Alert to Redis Stream."""
        key = f"soc:summaries:{tenant_id}"
        data = alert.model_dump_json()
        msg_id = await self.redis.xadd(key, {"alert": data})
        return msg_id

    async def create_consumer_group(
        self, stream_name: str, group_name: str, mkstream: bool = True
    ) -> None:
        """Create a consumer group for a stream (idempotent)."""
        try:
            await self.redis.xgroup_create(stream_name, group_name, id="0", mkstream=mkstream)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list:
        """
        Read messages from a consumer group.
        Returns list of (stream_key, messages) tuples.
        """
        try:
            results = await self.redis.xreadgroup(
                group_name, consumer_name, {stream_name: ">"}, count=count, block=block_ms
            )
            return results or []
        except aioredis.ResponseError as e:
            if "NOGROUP" in str(e):
                await self.create_consumer_group(stream_name, group_name)
                return await self.read_group(
                    stream_name, group_name, consumer_name, count, block_ms
                )
            raise

    async def acknowledge(
        self, stream_name: str, group_name: str, message_ids: list[str]
    ) -> int:
        """Acknowledge messages in a consumer group."""
        if not message_ids:
            return 0
        return await self.redis.xack(stream_name, group_name, *message_ids)

    async def get_pending_count(self, stream_name: str, group_name: str) -> int:
        """Get count of pending messages for a consumer group."""
        info = await self.redis.xinfo_groups(stream_name)
        for group_info in info:
            if group_info.get("name") == group_name:
                return group_info.get("pending", 0)
        return 0


# Tenant provisioning utilities
async def provision_tenant_streams(redis_client: aioredis.Redis, tenant_id: str) -> None:
    """
    Create all required Redis Stream consumer groups for a new tenant.
    Called during tenant on-boarding.
    """
    helper = RedisStreamHelper(redis_client)
    streams = [
        f"soc:events:{tenant_id}",
        f"soc:detections:{tenant_id}",
        f"soc:incidents:{tenant_id}",
        f"soc:summaries:{tenant_id}",
    ]

    for stream in streams:
        await helper.create_consumer_group(stream, f"group_{tenant_id}")


# Stream key helpers
def stream_key(stage: str, tenant_id: str) -> str:
    """Generate Redis Stream key for a stage and tenant."""
    return f"soc:{stage}:{tenant_id}"


def consumer_group_name(tenant_id: str, agent: str = "") -> str:
    """Generate consumer group name for a tenant and agent."""
    if agent:
        return f"group_{tenant_id}_{agent}"
    return f"group_{tenant_id}"


def consumer_name(tenant_id: str, agent: str, instance: int = 1) -> str:
    """Generate consumer name for load-balanced agent instances."""
    return f"consumer_{agent}_{instance}_{tenant_id}"
