from datetime import datetime
from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user, get_current_user_with_email
from shared.models import User

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
