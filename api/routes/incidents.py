from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.models import FeedbackRequest, IsolationRequest

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(
    tenant_id: str = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
    status: str = Query(None),
    severity: str = Query(None),
):
    """List all incidents for the tenant with optional filtering."""
    incidents_col = get_collection("incidents")
    
    # Build query
    query = {"tenant_id": tenant_id}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    
    cursor = incidents_col.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    incidents = await cursor.to_list(length=limit)
    
    # Attach detection count for each incident
    detections_col = get_collection("detections")
    for incident in incidents:
        detection_count = len(incident.get("detection_ids", []))
        incident["detection_count"] = detection_count
    
    return incidents


@router.get("/{incident_id}")
async def get_incident(incident_id: str, tenant_id: str = Depends(get_current_user)):
    incidents_col = get_collection("incidents")
    incident = await incidents_col.find_one(
        {"incident_id": incident_id, "tenant_id": tenant_id}, {"_id": 0}
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Attach detection timeline
    detections_col = get_collection("detections")
    detections = await detections_col.find(
        {"detection_id": {"$in": incident.get("detection_ids", [])}, "tenant_id": tenant_id},
        {"_id": 0},
    ).sort("detected_at", 1).to_list(length=100)
    incident["detections"] = detections
    return incident


@router.post("/{incident_id}/isolate")
async def isolate_entity(
    incident_id: str,
    body: IsolationRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Isolate an IP or user — blocks further event ingestion from this entity."""
    blocked_col = get_collection("blocked_entities")
    now = datetime.utcnow()
    await blocked_col.update_one(
        {"tenant_id": tenant_id, "type": body.type, "value": body.value},
        {"$set": {
            "tenant_id": tenant_id,
            "type": body.type,
            "value": body.value,
            "incident_id": incident_id,
            "isolated_at": now,
        }},
        upsert=True,
    )
    audit_col = get_collection("audit_log")
    await audit_col.insert_one({
        "tenant_id": tenant_id,
        "action": "isolate",
        "entity": body.type,
        "entity_id": body.value,
        "incident_id": incident_id,
        "timestamp": now,
    })
    return {"status": "isolated", "type": body.type, "value": body.value}


@router.post("/{incident_id}/unisolate")
async def unisolate_entity(
    incident_id: str,
    body: IsolationRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Remove isolation — resume event ingestion from this entity."""
    blocked_col = get_collection("blocked_entities")
    await blocked_col.delete_one(
        {"tenant_id": tenant_id, "type": body.type, "value": body.value}
    )
    audit_col = get_collection("audit_log")
    await audit_col.insert_one({
        "tenant_id": tenant_id,
        "action": "unisolate",
        "entity": body.type,
        "entity_id": body.value,
        "incident_id": incident_id,
        "timestamp": datetime.utcnow(),
    })
    return {"status": "unisolated", "type": body.type, "value": body.value}


@router.post("/{incident_id}/feedback")
async def submit_incident_feedback(
    incident_id: str,
    body: FeedbackRequest,
    tenant_id: str = Depends(get_current_user),
):
    alerts_col = get_collection("alerts")
    result = await alerts_col.update_one(
        {"incident_id": incident_id, "tenant_id": tenant_id},
        {"$set": {"feedback": body.feedback}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    audit_col = get_collection("audit_log")
    from datetime import datetime
    await audit_col.insert_one({
        "tenant_id": tenant_id,
        "action": "feedback",
        "entity": "incident",
        "entity_id": incident_id,
        "value": body.feedback,
        "timestamp": datetime.utcnow(),
    })
    return {"status": "ok"}
