from fastapi import APIRouter, Depends, HTTPException
from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.api_keys import generate_api_key, hash_api_key, get_key_prefix
from shared.config import settings

router = APIRouter(prefix="/users/me", tags=["devices"])


@router.post("/api-key")
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


@router.get("/api-key")
async def get_api_key_info(user_id: str = Depends(get_current_user)):
    """Return key prefix + Vector config template (not the key itself)."""
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


@router.delete("/api-key")
async def revoke_api_key(user_id: str = Depends(get_current_user)):
    users_col = get_collection("users")
    await users_col.update_one(
        {"user_id": user_id},
        {"$unset": {"api_key_hash": "", "api_key_prefix": ""}},
    )
    return {"status": "revoked"}
