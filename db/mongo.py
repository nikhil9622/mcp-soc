from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from shared.config import settings

_client: AsyncIOMotorClient | None = None


async def connect_mongo() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL)


async def close_mongo() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected — call connect_mongo() first")
    return _client[settings.MONGODB_DB]


def get_collection(name: str):
    return get_db()[name]
