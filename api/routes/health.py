from fastapi import APIRouter
from db.mongo import get_db
from db.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health():
    status = {"status": "ok", "mongodb": "ok", "redis": "ok"}
    try:
        await get_db().command("ping")
    except Exception as e:
        status["mongodb"] = f"error: {e}"
        status["status"] = "degraded"
    try:
        await get_redis().ping()
    except Exception as e:
        status["redis"] = f"error: {e}"
        status["status"] = "degraded"
    return status
