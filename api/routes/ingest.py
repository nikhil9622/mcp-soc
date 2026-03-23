import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks
from db.mongo import get_collection
from db.redis_client import xadd
from api.dependencies import get_current_user, get_current_user_api_key
from shared.models import CloudTrailPayload, SyslogPayload

router = APIRouter(prefix="/ingest", tags=["ingest"])


async def _enqueue_events(tenant_id: str, records: list[dict], source: str):
    stream_stage = "raw_cloudtrail" if source == "cloudtrail" else "raw_syslog"
    for record in records:
        await xadd(stream_stage, tenant_id, {
            "tenant_id": tenant_id,
            "source": source,
            "record": json.dumps(record),
            "received_at": datetime.utcnow().isoformat(),
        })


@router.post("/cloudtrail")
async def ingest_cloudtrail(
    payload: CloudTrailPayload,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_user),
):
    background_tasks.add_task(_enqueue_events, tenant_id, payload.records, "cloudtrail")
    return {"status": "accepted", "count": len(payload.records)}


@router.post("/syslog")
async def ingest_syslog(
    payload: SyslogPayload,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_user_api_key),
):
    background_tasks.add_task(_enqueue_events, tenant_id, payload.records, "syslog")
    return {"status": "accepted", "count": len(payload.records)}


@router.get("/stats")
async def ingest_stats(tenant_id: str = Depends(get_current_user)):
    """Return event counts per source for the last 5 minutes and last 24 hours."""
    events_col = get_collection("events")
    now = datetime.utcnow()
    since_5m  = now - timedelta(minutes=5)
    since_24h = now - timedelta(hours=24)

    results = {}
    for source in ("cloudtrail", "syslog", "app"):
        count_5m  = await events_col.count_documents({"tenant_id": tenant_id, "source": source, "timestamp": {"$gte": since_5m}})
        count_24h = await events_col.count_documents({"tenant_id": tenant_id, "source": source, "timestamp": {"$gte": since_24h}})
        results[source] = {"last_5m": count_5m, "last_24h": count_24h}

    total_5m  = sum(v["last_5m"]  for v in results.values())
    total_24h = sum(v["last_24h"] for v in results.values())
    results["total"] = {"last_5m": total_5m, "last_24h": total_24h}
    return results
