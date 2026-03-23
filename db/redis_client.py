import json
import redis.asyncio as aioredis
from shared.config import settings

_redis: aioredis.Redis | None = None


async def connect_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not connected — call connect_redis() first")
    return _redis


# Stream key helpers
def stream_key(stage: str, tenant_id: str) -> str:
    return f"soc:{stage}:{tenant_id}"


async def xadd(stage: str, tenant_id: str, data: dict) -> str:
    r = get_redis()
    key = stream_key(stage, tenant_id)
    payload = {k: json.dumps(v) if isinstance(v, (dict, list)) or v is None else str(v) for k, v in data.items()}
    return await r.xadd(key, payload)


async def xreadgroup(
    group: str,
    consumer: str,
    stage: str,
    tenant_id: str,
    count: int = 10,
    block: int = 5000,
) -> list:
    r = get_redis()
    key = stream_key(stage, tenant_id)
    try:
        await r.xgroup_create(key, group, id="0", mkstream=True)
    except Exception:
        pass  # group already exists
    results = await r.xreadgroup(group, consumer, {key: ">"}, count=count, block=block)
    return results or []


async def xack(stage: str, tenant_id: str, group: str, msg_id: str) -> None:
    r = get_redis()
    key = stream_key(stage, tenant_id)
    await r.xack(key, group, msg_id)
