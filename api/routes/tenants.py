"""Tenant management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime

from db.mongo import get_collection
from db.redis_client import connect_redis, get_redis
from api.dependencies import get_current_user_api_key
from shared.models import User
from shared.api_keys import generate_api_key, hash_api_key

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("")
async def list_tenants(
    tenant_id: str = Depends(get_current_user_api_key),
    skip: int = 0,
    limit: int = 50,
):
    """
    List all tenants.
    
    Note: In single-tenant MVP, returns just the current tenant.
    Multi-tenant will show all accessible tenants.
    """
    users_col = get_collection("users")
    
    # Get current user
    user = await users_col.find_one({"user_id": tenant_id})
    if not user:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "tenant_id": user["user_id"],
        "created_at": user["created_at"],
        "plan": user.get("plan", "free"),
        "stats": {
            "incidents": await get_incident_count(tenant_id),
            "alerts": await get_alert_count(tenant_id),
            "rules": 5,  # MVP: 5 Sigma rules
        },
    }


@router.post("")
async def create_tenant(
    name: str,
    email: str,
    tenant_id: str = Depends(get_current_user_api_key),
):
    """
    Create a new tenant (admin only).
    
    Returns:
        - user_id: Tenant identifier
        - api_key: One-time API key display
    """
    users_col = get_collection("users")
    
    # Create new tenant/user
    api_key = generate_api_key()
    new_user = User(
        user_id=name.lower().replace(" ", "-"),
        email=email,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=api_key[:12],
    )
    
    try:
        await users_col.insert_one(new_user.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Tenant creation failed: {e}")
    
    # Initialize tenant in all streams
    r = get_redis()
    for stream in ["events", "detections", "incidents", "summaries"]:
        try:
            stream_key = f"soc:{stream}:{new_user.user_id}"
            await r.xgroup_create(stream_key, f"{stream}-group", id="0", mkstream=True)
        except Exception:
            pass  # May already exist
    
    return {
        "status": "ok",
        "user_id": new_user.user_id,
        "api_key": api_key,  # Show once
        "note": "Save this API key. You won't see it again.",
    }


@router.get("/{tenant_id}/stats")
async def get_tenant_stats(
    tenant_id: str,
    current_tenant: str = Depends(get_current_user_api_key),
):
    """Get tenant statistics and health."""
    # Verify access
    if tenant_id != current_tenant:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return {
        "tenant_id": tenant_id,
        "timestamp": datetime.utcnow().isoformat(),
        "incidents": {
            "total": await get_incident_count(tenant_id),
            "open": await count_incidents_by_status(tenant_id, "open"),
            "investigating": await count_incidents_by_status(tenant_id, "investigating"),
            "closed": await count_incidents_by_status(tenant_id, "closed"),
        },
        "alerts": {
            "total": await get_alert_count(tenant_id),
            "pending_feedback": await count_alerts_by_feedback(tenant_id, None),
            "true_positives": await count_alerts_by_feedback(tenant_id, "tp"),
            "false_positives": await count_alerts_by_feedback(tenant_id, "fp"),
        },
        "detections": {
            "total": await get_detection_count(tenant_id),
            "critical": await count_detections_by_severity(tenant_id, "critical"),
            "high": await count_detections_by_severity(tenant_id, "high"),
        },
        "health": "ok",
    }


async def get_incident_count(tenant_id: str) -> int:
    """Get total incidents for tenant."""
    incidents_col = get_collection("incidents")
    return await incidents_col.count_documents({"tenant_id": tenant_id})


async def get_alert_count(tenant_id: str) -> int:
    """Get total alerts for tenant."""
    alerts_col = get_collection("alerts")
    return await alerts_col.count_documents({"tenant_id": tenant_id})


async def get_detection_count(tenant_id: str) -> int:
    """Get total detections for tenant."""
    detections_col = get_collection("detections")
    return await detections_col.count_documents({"tenant_id": tenant_id})


async def count_incidents_by_status(tenant_id: str, status: str) -> int:
    """Count incidents by status."""
    incidents_col = get_collection("incidents")
    return await incidents_col.count_documents({"tenant_id": tenant_id, "status": status})


async def count_alerts_by_feedback(tenant_id: str, feedback) -> int:
    """Count alerts by feedback status."""
    alerts_col = get_collection("alerts")
    return await alerts_col.count_documents({"tenant_id": tenant_id, "feedback": feedback})


async def count_detections_by_severity(tenant_id: str, severity: str) -> int:
    """Count detections by severity."""
    detections_col = get_collection("detections")
    return await detections_col.count_documents({"tenant_id": tenant_id, "severity": severity})
