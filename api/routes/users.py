from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user, get_current_user_with_email
from shared.models import User
from shared.api_keys import generate_api_key, hash_api_key, get_key_prefix
from shared.config import settings

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me", response_model=User, response_model_exclude={"api_key_hash", "api_key_prefix"})
async def upsert_user(user_info: dict = Depends(get_current_user_with_email)):
    user_id = user_info["uid"]
    email = user_info.get("email", "")
    users_col = get_collection("users")
    existing = await users_col.find_one({"user_id": user_id})
    if existing:
        if not existing.get("email") and email:
            await users_col.update_one({"user_id": user_id}, {"$set": {"email": email}})
            existing["email"] = email
        existing.pop("_id", None)
        existing.pop("api_key_hash", None)
        existing.pop("api_key_prefix", None)
        return existing
    user = {"user_id": user_id, "email": email, "created_at": datetime.utcnow(), "plan": "free", "settings": {}}
    await users_col.insert_one(user)
    user.pop("_id", None)
    return user


@router.get("/me", response_model=dict)
async def get_user(user_id: str = Depends(get_current_user)):
    users_col = get_collection("users")
    user = await users_col.find_one({"user_id": user_id}, {"_id": 0, "api_key_hash": 0})
    if not user:
        return {"user_id": user_id}
    return user


# ---------------------------------------------------------------------------
# API-key management (moved from devices.py to keep /users/me prefix intact)
# ---------------------------------------------------------------------------


@router.post("/me/api-key")
async def create_api_key(user_id: str = Depends(get_current_user)):
    """Generate an API key. Returns plaintext key ONCE — not stored."""
    users_col = get_collection("users")
    key = generate_api_key()
    prefix = get_key_prefix(key)
    hashed = hash_api_key(key)
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"api_key_hash": hashed, "api_key_prefix": prefix}},
        upsert=True,
    )
    vector_config = f"""# Vector config for MCP SOC
[sources.system_logs]
type = "file"
include = ["/var/log/syslog", "/var/log/auth.log"]

[sinks.mcp_soc]
type = "http"
inputs = ["system_logs"]
uri = "{settings.API_BASE_URL}/ingest/syslog"
encoding.codec = "json"

[sinks.mcp_soc.request.headers]
X-API-Key = "{key}"
Content-Type = "application/json"
"""
    return {"api_key": key, "prefix": prefix, "vector_config": vector_config}


@router.get("/me/api-key")
async def get_api_key_info(user_id: str = Depends(get_current_user)):
    """Return key prefix + Vector config template (not the key itself)."""
    from fastapi import HTTPException

    users_col = get_collection("users")
    user = await users_col.find_one({"user_id": user_id})
    if not user or not user.get("api_key_prefix"):
        raise HTTPException(status_code=404, detail="No API key found. Generate one first.")
    prefix = user["api_key_prefix"]
    vector_config = f"""# Vector config for MCP SOC
[sources.system_logs]
type = "file"
include = ["/var/log/syslog", "/var/log/auth.log"]

[sinks.mcp_soc]
type = "http"
inputs = ["system_logs"]
uri = "{settings.API_BASE_URL}/ingest/syslog"
encoding.codec = "json"

[sinks.mcp_soc.request.headers]
X-API-Key = "<YOUR_API_KEY>"
Content-Type = "application/json"
"""
    return {"prefix": prefix, "vector_config": vector_config}


@router.delete("/me/api-key")
async def revoke_api_key(user_id: str = Depends(get_current_user)):
    users_col = get_collection("users")
    await users_col.update_one(
        {"user_id": user_id},
        {"$unset": {"api_key_hash": "", "api_key_prefix": ""}},
    )
    return {"status": "revoked"}
