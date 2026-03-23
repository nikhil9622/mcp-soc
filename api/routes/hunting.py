"""Threat Hunting API — ad-hoc event search with saved hunts."""
from __future__ import annotations
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/hunt", tags=["hunting"])


class HuntQuery(BaseModel):
    user: str | None = None
    ip: str | None = None
    action: str | None = None
    source: str | None = None          # cloudtrail | syslog
    free_text: str | None = None       # matched against action + metadata.raw
    hours: int = 24                    # look-back window
    limit: int = 200


class SaveHuntRequest(BaseModel):
    name: str
    query: HuntQuery


@router.post("/search")
async def hunt_search(query: HuntQuery, tenant_id: str = Depends(get_current_user)):
    events_col = get_collection("events")
    since = datetime.utcnow() - timedelta(hours=max(1, min(query.hours, 720)))

    filters: dict = {"tenant_id": tenant_id, "timestamp": {"$gte": since}}

    if query.user:
        filters["user"] = {"$regex": query.user, "$options": "i"}
    if query.ip:
        filters["ip"] = {"$regex": query.ip, "$options": "i"}
    if query.action:
        filters["action"] = {"$regex": query.action, "$options": "i"}
    if query.source:
        filters["source"] = query.source
    if query.free_text:
        filters["$or"] = [
            {"action":        {"$regex": query.free_text, "$options": "i"}},
            {"metadata.raw":  {"$regex": query.free_text, "$options": "i"}},
            {"user":          {"$regex": query.free_text, "$options": "i"}},
        ]

    cursor = events_col.find(filters, {"_id": 0}).sort("timestamp", -1).limit(query.limit)
    events = await cursor.to_list(length=query.limit)

    # Timeline: bucket by hour
    timeline: dict[str, int] = {}
    for e in events:
        ts = e.get("timestamp")
        if ts:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            bucket = ts.strftime("%Y-%m-%dT%H:00")
            timeline[bucket] = timeline.get(bucket, 0) + 1

    # Action frequency
    action_freq: dict[str, int] = {}
    for e in events:
        a = e.get("action", "unknown")
        action_freq[a] = action_freq.get(a, 0) + 1
    top_actions = sorted(action_freq.items(), key=lambda x: -x[1])[:10]

    # User frequency
    user_freq: dict[str, int] = {}
    for e in events:
        u = e.get("user", "unknown")
        user_freq[u] = user_freq.get(u, 0) + 1
    top_users = sorted(user_freq.items(), key=lambda x: -x[1])[:10]

    return {
        "total":       len(events),
        "events":      events,
        "timeline":    [{"hour": k, "count": v} for k, v in sorted(timeline.items())],
        "top_actions": [{"action": a, "count": c} for a, c in top_actions],
        "top_users":   [{"user": u, "count": c} for u, c in top_users],
    }


@router.get("/saved")
async def list_saved(tenant_id: str = Depends(get_current_user)):
    col = get_collection("saved_hunts")
    return await col.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/saved")
async def save_hunt(req: SaveHuntRequest, tenant_id: str = Depends(get_current_user)):
    col = get_collection("saved_hunts")
    doc = {
        "hunt_id":    str(uuid4()),
        "tenant_id":  tenant_id,
        "name":       req.name,
        "query":      req.query.model_dump(),
        "created_at": datetime.utcnow(),
    }
    await col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/saved/{hunt_id}")
async def delete_saved(hunt_id: str, tenant_id: str = Depends(get_current_user)):
    col = get_collection("saved_hunts")
    await col.delete_one({"tenant_id": tenant_id, "hunt_id": hunt_id})
    return {"ok": True}
