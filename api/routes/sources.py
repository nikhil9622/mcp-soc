"""Source IP registration — lets tenants register devices for UDP syslog."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceRegisterRequest(BaseModel):
    ip: str
    label: str = ""          # e.g. "office-firewall", "prod-linux-01"
    device_type: str = ""    # e.g. "cisco", "palo-alto", "linux", "windows"


class SourceDeleteRequest(BaseModel):
    ip: str


@router.post("/register")
async def register_source(
    body: SourceRegisterRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Register a device IP so UDP syslog packets from it are accepted."""
    col = get_collection("source_ips")
    await col.update_one(
        {"tenant_id": tenant_id, "ip": body.ip},
        {"$set": {
            "tenant_id": tenant_id,
            "ip": body.ip,
            "label": body.label,
            "device_type": body.device_type,
            "registered_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return {"status": "registered", "ip": body.ip}


@router.get("/list")
async def list_sources(tenant_id: str = Depends(get_current_user)):
    """List all registered source IPs for this tenant."""
    col = get_collection("source_ips")
    docs = await col.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "tenant_id": 0},
    ).to_list(100)
    return {"sources": docs}


@router.delete("/remove")
async def remove_source(
    body: SourceDeleteRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Remove a registered source IP."""
    col = get_collection("source_ips")
    result = await col.delete_one({"tenant_id": tenant_id, "ip": body.ip})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="IP not found")
    return {"status": "removed", "ip": body.ip}
