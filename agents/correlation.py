"""Correlation Agent — NetworkX graph, 60-min window, incident dedup."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import networkx as nx

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, xadd, get_redis
from shared.config import settings
from shared.models import DetectionEvent, Incident

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


async def run_correlation_agent(ctx, *, tenant_id: str, **fields) -> dict:
    data: dict = {"tenant_id": tenant_id}
    for k, v in fields.items():
        try:
            data[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            data[k] = None if v == "None" else v

    try:
        detection = DetectionEvent(**data)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    detections_col = get_collection("detections")
    incidents_col = get_collection("incidents")

    # Load all detections in the time window for this tenant
    window_start = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(
        minutes=settings.CORRELATION_WINDOW_MINUTES
    )
    cursor = detections_col.find({
        "tenant_id": tenant_id,
        "detected_at": {"$gte": window_start},
    })
    recent: list[dict] = await cursor.to_list(length=1000)

    if not recent:
        return {"status": "no_detections"}

    # Build graph: nodes = detection_ids, edges = shared user OR shared IP
    G = nx.Graph()
    for d in recent:
        G.add_node(d["detection_id"], severity=d.get("severity", "low"))

    for i, d1 in enumerate(recent):
        for d2 in recent[i + 1:]:
            e1 = d1.get("raw_event", {})
            e2 = d2.get("raw_event", {})
            shared_user = e1.get("user") and e1.get("user") == e2.get("user")
            shared_ip = e1.get("ip") and e1.get("ip") == e2.get("ip") and e1["ip"] != "0.0.0.0"
            if shared_user or shared_ip:
                G.add_edge(d1["detection_id"], d2["detection_id"])

    # Process connected components with >= 2 detections
    for component in nx.connected_components(G):
        if len(component) < 2:
            continue  # Rule 12: min 2 detections

        detection_ids = sorted(component)

        # Dedup: check if any detection already has an incident
        existing = await incidents_col.find_one({
            "tenant_id": tenant_id,
            "detection_ids": {"$in": detection_ids},
        })
        if existing:
            await incidents_col.update_one(
                {"incident_id": existing["incident_id"]},
                {"$addToSet": {"detection_ids": {"$each": detection_ids}}},
            )
            continue

        # Calculate max severity
        severities = [G.nodes[d].get("severity", "low") for d in component]
        max_sev = max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))

        # Collect entities from the detections in this component
        component_detections = [d for d in recent if d["detection_id"] in component]
        users = list({
            d.get("raw_event", {}).get("user")
            for d in component_detections
            if d.get("raw_event", {}).get("user") and d["raw_event"]["user"] not in ("unknown", "")
        })
        ips = list({
            d.get("raw_event", {}).get("ip")
            for d in component_detections
            if d.get("raw_event", {}).get("ip") and d["raw_event"]["ip"] not in ("0.0.0.0", "")
        })

        incident = Incident(
            tenant_id=tenant_id,
            detection_ids=detection_ids,
            severity=max_sev,
            entities={"users": users, "ips": ips},
        )
        await incidents_col.insert_one(incident.model_dump())
        await xadd("incidents", tenant_id, incident.model_dump(mode="json"))

    return {"status": "ok"}


async def startup(ctx):
    await connect_mongo()
    await connect_redis()
    asyncio.create_task(_poll_detections(ctx))


async def _poll_detections(ctx):
    r = get_redis()
    while ctx.get("running", True):
        try:
            keys = await r.keys("soc:detections:*")
            for key in keys:
                tenant_id = key.split(":")[-1]
                try:
                    await r.xgroup_create(key, "correlation", id="0", mkstream=True)
                except Exception:
                    pass
                try:
                    msgs = await r.xreadgroup("correlation", "correlation-1", {key: ">"}, count=10, block=500)
                except Exception:
                    continue
                if msgs:
                    for _stream, entries in msgs:
                        for msg_id, fields in entries:
                            await run_correlation_agent(ctx, **fields)
                            await r.xack(key, "correlation", msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.1)


async def shutdown(ctx):
    ctx["running"] = False


class WorkerSettings:
    functions = [run_correlation_agent]
    on_startup = startup
    on_shutdown = shutdown
    from arq.connections import RedisSettings as _RS
    redis_settings = _RS.from_dsn(settings.REDIS_URL)
