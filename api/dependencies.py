import asyncio
import base64
import json
import os
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth as firebase_auth
from db.mongo import get_collection
from shared.api_keys import get_key_prefix, verify_api_key
from shared.config import settings

bearer_scheme = HTTPBearer()

_firebase_app = None
_firebase_verified = False  # True only when real service account loaded


def _init_firebase():
    global _firebase_app, _firebase_verified
    if not firebase_admin._apps:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
        if os.path.exists(cred_path):
            from firebase_admin import credentials
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            _firebase_verified = True
        else:
            _firebase_app = firebase_admin.initialize_app()
            _firebase_verified = False


_init_firebase()


def _decode_jwt_unverified(token: str) -> dict:
    """Decode JWT payload without signature verification (dev mode only)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a JWT")
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token format: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Verify Firebase JWT and return user_id (== tenant_id)."""
    token = credentials.credentials
    if _firebase_verified:
        try:
            loop = asyncio.get_event_loop()
            decoded = await loop.run_in_executor(None, firebase_auth.verify_id_token, token)
            return decoded["uid"]
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    else:
        payload = _decode_jwt_unverified(token)
        uid = payload.get("user_id") or payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="No user_id in token")
        return uid


async def get_current_user_with_email(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Return uid + email from JWT (dev mode reads without verification)."""
    token = credentials.credentials
    if _firebase_verified:
        try:
            loop = asyncio.get_event_loop()
            decoded = await loop.run_in_executor(None, firebase_auth.verify_id_token, token)
            return {"uid": decoded["uid"], "email": decoded.get("email", "")}
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    else:
        payload = _decode_jwt_unverified(token)
        uid = payload.get("user_id") or payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="No user_id in token")
        return {"uid": uid, "email": payload.get("email", "")}


async def get_current_user_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """Verify API key and return user_id (== tenant_id)."""
    prefix = get_key_prefix(x_api_key)
    users_col = get_collection("users")
    user = await users_col.find_one({"api_key_prefix": prefix})
    if not user or not verify_api_key(x_api_key, user["api_key_hash"]):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user["user_id"]
