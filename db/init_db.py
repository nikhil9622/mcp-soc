"""Idempotent index creation — safe to run multiple times."""
import asyncio
from pymongo import ASCENDING, IndexModel
from motor.motor_asyncio import AsyncIOMotorCollection
from db.mongo import get_collection, connect_mongo


async def create_indexes() -> None:
    events: AsyncIOMotorCollection = get_collection("events")
    await events.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("event_id", ASCENDING)], unique=True),
        IndexModel([("tenant_id", ASCENDING), ("timestamp", ASCENDING)]),
        IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=90 * 24 * 3600),
    ])

    detections: AsyncIOMotorCollection = get_collection("detections")
    await detections.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("detection_id", ASCENDING)], unique=True),
        IndexModel([("tenant_id", ASCENDING), ("detected_at", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("severity", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("event_id", ASCENDING)]),
    ])

    incidents: AsyncIOMotorCollection = get_collection("incidents")
    await incidents.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("incident_id", ASCENDING)], unique=True),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("created_at", ASCENDING)]),
    ])

    alerts: AsyncIOMotorCollection = get_collection("alerts")
    await alerts.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("alert_id", ASCENDING)], unique=True),
        IndexModel([("tenant_id", ASCENDING), ("incident_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("sent_at", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("feedback", ASCENDING)]),  # For TP/FP queries
        IndexModel([("tenant_id", ASCENDING), ("severity", ASCENDING)]),
    ])

    users: AsyncIOMotorCollection = get_collection("users")
    await users.create_indexes([
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("api_key_prefix", ASCENDING)], sparse=True),
    ])

    audit_log: AsyncIOMotorCollection = get_collection("audit_log")
    await audit_log.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("timestamp", ASCENDING)]),
        IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=365 * 24 * 3600),
    ])

    devices: AsyncIOMotorCollection = get_collection("devices")
    await devices.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("device_id", ASCENDING)], unique=True),
        IndexModel([("tenant_id", ASCENDING), ("last_seen", -1)]),
    ])

    team_members: AsyncIOMotorCollection = get_collection("team_members")
    await team_members.create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("email", ASCENDING)]),
        IndexModel([("invite_token", ASCENDING)], unique=True, sparse=True),
    ])


if __name__ == "__main__":
    async def main():
        await connect_mongo()
        await create_indexes()
        print("Indexes created.")
    asyncio.run(main())
