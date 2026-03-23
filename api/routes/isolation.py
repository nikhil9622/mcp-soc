from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/blocked-entities", tags=["isolation"])


@router.get("")
async def list_blocked_entities(tenant_id: str = Depends(get_current_user)):
    """Return all currently isolated IPs and users for this tenant."""
    blocked_col = get_collection("blocked_entities")
    cursor = blocked_col.find({"tenant_id": tenant_id}, {"_id": 0}).sort("isolated_at", -1)
    return await cursor.to_list(length=500)
