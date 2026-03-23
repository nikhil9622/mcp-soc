from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime

from db.mongo import get_collection
from db.redis_client import xadd
from api.dependencies import get_current_user
from shared.models import FeedbackRequest

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(tenant_id: str = Depends(get_current_user), skip: int = 0, limit: int = 50):
    """List all alerts for the tenant."""
    alerts_col = get_collection("alerts")
    cursor = alerts_col.find({"tenant_id": tenant_id}, {"_id": 0}).sort("sent_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


@router.post("/{alert_id}/feedback")
async def submit_alert_feedback(
    alert_id: str,
    feedback_type: str = Query(..., alias="type"),  # type=tp or type=fp
    note: str = Query(""),
    tenant_id: str = Depends(get_current_user),
):
    """
    Submit TP/FP feedback on an alert.
    
    Accepts: type=tp or type=fp
    Optional: note=analyst_note
    
    Returns:
        - 200 OK: Feedback recorded
        - 400: Invalid feedback type
        - 404: Alert not found
        - 401: Unauthorized
    """
    # Validate feedback type
    if feedback_type not in ("tp", "fp"):
        raise HTTPException(status_code=400, detail="Invalid feedback type. Use 'tp' or 'fp'.")
    
    alerts_col = get_collection("alerts")
    
    # Find and validate alert exists
    alert = await alerts_col.find_one({"alert_id": alert_id, "tenant_id": tenant_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Update feedback
    now = datetime.utcnow()
    result = await alerts_col.update_one(
        {"alert_id": alert_id, "tenant_id": tenant_id},
        {
            "$set": {
                "feedback": feedback_type,
                "feedback_at": now,
                "feedback_note": note,
            }
        },
    )
    
    # Audit log
    audit_col = get_collection("audit_log")
    await audit_col.insert_one({
        "tenant_id": tenant_id,
        "action": "submit_feedback",
        "entity": "alert",
        "entity_id": alert_id,
        "value": feedback_type,
        "note": note,
        "timestamp": now,
    })
    
    # Publish to Redis feedback stream for ML retraining (Phase 10)
    try:
        await xadd(
            "feedback",
            tenant_id,
            {
                "alert_id": alert_id,
                "incident_id": alert["incident_id"],
                "feedback": feedback_type,
                "note": note,
                "submitted_at": now.isoformat(),
            },
        )
    except Exception as e:
        # Log but don't fail — feedback is already stored in MongoDB
        print(f"Failed to publish feedback to stream: {e}")
    
    return {"status": "ok", "alert_id": alert_id, "feedback": feedback_type}

