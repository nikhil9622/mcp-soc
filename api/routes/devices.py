from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.models import Device

router = APIRouter(prefix="/devices", tags=["devices"])

# A device is considered online if its last heartbeat was within this window.
_ONLINE_THRESHOLD_SECONDS = 120


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class RegisterDeviceRequest(BaseModel):
    device_id: str
    device_name: str
    os: str
    ip: str
    mac: str = ""
    agent_version: str = "1.0.0"


class HeartbeatRequest(BaseModel):
    ip: str | None = None
    events_sent: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_online(last_seen: datetime) -> bool:
    """Return True when last_seen is within the online threshold."""
    now = datetime.now(tz=timezone.utc)
    # last_seen may be timezone-naive (stored as UTC by motor)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now - last_seen).total_seconds() < _ONLINE_THRESHOLD_SECONDS


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", status_code=201)
async def register_device(
    body: RegisterDeviceRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Agent calls this on first run (and on restart).

    Creates a new device record if the device_id is unseen, or updates the
    existing record with the latest metadata.
    """
    devices_col = get_collection("devices")
    now = datetime.utcnow()

    existing = await devices_col.find_one(
        {"tenant_id": tenant_id, "device_id": body.device_id}
    )

    if existing:
        # Update mutable fields on re-registration / restart.
        await devices_col.update_one(
            {"tenant_id": tenant_id, "device_id": body.device_id},
            {
                "$set": {
                    "device_name": body.device_name,
                    "os": body.os,
                    "ip": body.ip,
                    "mac": body.mac,
                    "agent_version": body.agent_version,
                    "last_seen": now,
                }
            },
        )
        doc = await devices_col.find_one(
            {"tenant_id": tenant_id, "device_id": body.device_id}, {"_id": 0}
        )
        doc["status"] = "online" if _is_online(doc["last_seen"]) else "offline"
        return doc

    device = Device(
        tenant_id=tenant_id,
        device_id=body.device_id,
        device_name=body.device_name,
        os=body.os,
        ip=body.ip,
        mac=body.mac,
        agent_version=body.agent_version,
        registered_by=tenant_id,
        registered_at=now,
        last_seen=now,
    )
    doc = device.model_dump(mode="json")
    await devices_col.insert_one(doc)
    doc.pop("_id", None)
    doc["status"] = "online"
    return doc


@router.get("")
async def list_devices(tenant_id: str = Depends(get_current_user)):
    """List all registered devices for the tenant with computed online status."""
    devices_col = get_collection("devices")
    cursor = devices_col.find({"tenant_id": tenant_id}, {"_id": 0}).sort(
        "last_seen", -1
    )
    devices = await cursor.to_list(length=500)
    for device in devices:
        last_seen = device.get("last_seen")
        if last_seen:
            device["status"] = "online" if _is_online(last_seen) else "offline"
        else:
            device["status"] = "offline"
    return devices


@router.get("/{device_id}")
async def get_device(device_id: str, tenant_id: str = Depends(get_current_user)):
    """Return device detail including total alert count for that device's IP."""
    devices_col = get_collection("devices")
    device = await devices_col.find_one(
        {"tenant_id": tenant_id, "device_id": device_id}, {"_id": 0}
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    last_seen = device.get("last_seen")
    device["status"] = "online" if (last_seen and _is_online(last_seen)) else "offline"

    # Attach alert count — alerts whose source_ip matches this device's current IP.
    alerts_col = get_collection("alerts")
    device["alert_count"] = await alerts_col.count_documents(
        {"tenant_id": tenant_id, "source_ip": device.get("ip", "")}
    )
    return device


@router.patch("/{device_id}")
async def update_device(
    device_id: str,
    body: HeartbeatRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Heartbeat endpoint — agent calls this every 30 seconds.

    Also used for any other partial update (IP change, events_sent counter).
    """
    devices_col = get_collection("devices")
    existing = await devices_col.find_one(
        {"tenant_id": tenant_id, "device_id": device_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")

    update: dict = {"last_seen": datetime.utcnow()}
    if body.ip is not None:
        update["ip"] = body.ip
    if body.events_sent is not None:
        update["events_sent"] = body.events_sent

    await devices_col.update_one(
        {"tenant_id": tenant_id, "device_id": device_id},
        {"$set": update},
    )
    return {"status": "ok", "device_id": device_id}


@router.delete("/{device_id}", status_code=200)
async def delete_device(
    device_id: str,
    tenant_id: str = Depends(get_current_user),
):
    """Remove a device from the registry (SOC Manager only).

    Role enforcement is delegated to the caller layer; the device registry
    itself only validates tenant ownership.
    """
    devices_col = get_collection("devices")
    result = await devices_col.delete_one(
        {"tenant_id": tenant_id, "device_id": device_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")

    audit_col = get_collection("audit_log")
    await audit_col.insert_one(
        {
            "tenant_id": tenant_id,
            "action": "delete_device",
            "entity": "device",
            "entity_id": device_id,
            "timestamp": datetime.utcnow(),
        }
    )
    return {"status": "deleted", "device_id": device_id}
