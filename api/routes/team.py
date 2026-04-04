from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db.mongo import get_collection
from api.dependencies import get_current_user
from shared.models import TeamMember

router = APIRouter(prefix="/team", tags=["team"])

# Role hierarchy — higher index == higher privilege.
_ROLE_RANK: dict[str, int] = {
    "readonly": 0,
    "analyst_l2": 1,
    "analyst_l1": 2,
    "soc_manager": 3,
}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class InviteRequest(BaseModel):
    email: str
    role: str = "analyst_l1"


class ChangeRoleRequest(BaseModel):
    role: str


class AcceptInviteRequest(BaseModel):
    invite_token: str


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------


async def _get_member(db_members, tenant_id: str, user_id: str) -> dict | None:
    """Return the team_members doc for a user within a tenant, or None."""
    return await db_members.find_one(
        {"tenant_id": tenant_id, "user_id": user_id, "status": "active"}
    )


async def require_role(
    min_role: str,
    db_members,
    tenant_id: str,
    user_id: str,
) -> None:
    """Raise HTTP 403 when the calling user's role is below min_role.

    The tenant owner (user_id == tenant_id) is always treated as soc_manager
    so the original account retains full access without needing a team record.
    """
    if user_id == tenant_id:
        # Tenant owner: implicitly soc_manager.
        return

    member = await _get_member(db_members, tenant_id, user_id)
    if not member:
        raise HTTPException(
            status_code=403, detail="You are not a member of this tenant."
        )

    caller_rank = _ROLE_RANK.get(member.get("role", "readonly"), 0)
    required_rank = _ROLE_RANK.get(min_role, 0)
    if caller_rank < required_rank:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{min_role}' or higher required. You have '{member['role']}'.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/invite", status_code=201)
async def invite_member(
    body: InviteRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Send an invite to an email address (SOC Manager only).

    Stores a pending TeamMember record with a UUID invite_token.
    The token is returned so the caller can share the invite link.
    """
    if body.role not in _ROLE_RANK:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{body.role}'. Must be one of: {list(_ROLE_RANK)}.",
        )

    members_col = get_collection("team_members")
    await require_role("soc_manager", members_col, tenant_id, tenant_id)

    # Prevent duplicate active/pending invites for the same email.
    existing = await members_col.find_one(
        {
            "tenant_id": tenant_id,
            "email": body.email,
            "status": {"$in": ["pending", "active"]},
        }
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An active or pending invite already exists for this email.",
        )

    member = TeamMember(
        tenant_id=tenant_id,
        email=body.email,
        role=body.role,
        status="pending",
        invited_by=tenant_id,
    )
    doc = member.model_dump(mode="json")
    await members_col.insert_one(doc)
    doc.pop("_id", None)

    audit_col = get_collection("audit_log")
    await audit_col.insert_one(
        {
            "tenant_id": tenant_id,
            "action": "invite_member",
            "entity": "team_member",
            "entity_id": body.email,
            "value": body.role,
            "timestamp": datetime.utcnow(),
        }
    )
    return {"status": "invited", "invite_token": member.invite_token, "email": body.email}


@router.get("/members")
async def list_members(tenant_id: str = Depends(get_current_user)):
    """List all active team members with their roles and device counts."""
    members_col = get_collection("team_members")
    devices_col = get_collection("devices")

    cursor = members_col.find(
        {"tenant_id": tenant_id, "status": "active"}, {"_id": 0}
    ).sort("invited_at", 1)
    members = await cursor.to_list(length=500)

    # Attach device count per member (devices registered_by that user_id).
    for member in members:
        uid = member.get("user_id")
        if uid:
            member["device_count"] = await devices_col.count_documents(
                {"tenant_id": tenant_id, "registered_by": uid}
            )
        else:
            member["device_count"] = 0

    return members


@router.patch("/members/{user_id}/role")
async def change_member_role(
    user_id: str,
    body: ChangeRoleRequest,
    tenant_id: str = Depends(get_current_user),
):
    """Change a member's role (SOC Manager only)."""
    if body.role not in _ROLE_RANK:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{body.role}'. Must be one of: {list(_ROLE_RANK)}.",
        )

    members_col = get_collection("team_members")
    await require_role("soc_manager", members_col, tenant_id, tenant_id)

    result = await members_col.update_one(
        {"tenant_id": tenant_id, "user_id": user_id, "status": "active"},
        {"$set": {"role": body.role}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Member not found or not active.")

    audit_col = get_collection("audit_log")
    await audit_col.insert_one(
        {
            "tenant_id": tenant_id,
            "action": "change_role",
            "entity": "team_member",
            "entity_id": user_id,
            "value": body.role,
            "timestamp": datetime.utcnow(),
        }
    )
    return {"status": "ok", "user_id": user_id, "role": body.role}


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    tenant_id: str = Depends(get_current_user),
):
    """Soft-delete a member (SOC Manager only). Sets status to 'removed'."""
    members_col = get_collection("team_members")
    await require_role("soc_manager", members_col, tenant_id, tenant_id)

    result = await members_col.update_one(
        {"tenant_id": tenant_id, "user_id": user_id, "status": "active"},
        {"$set": {"status": "removed"}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Member not found or not active.")

    audit_col = get_collection("audit_log")
    await audit_col.insert_one(
        {
            "tenant_id": tenant_id,
            "action": "remove_member",
            "entity": "team_member",
            "entity_id": user_id,
            "timestamp": datetime.utcnow(),
        }
    )
    return {"status": "removed", "user_id": user_id}


@router.post("/accept")
async def accept_invite(
    body: AcceptInviteRequest,
    user_id: str = Depends(get_current_user),
):
    """Accept a team invite using the invite token.

    Called by a new user after they authenticate (e.g. after running the EXE
    and signing in for the first time).  The invite_token links their Firebase
    UID to the pending TeamMember record.
    """
    members_col = get_collection("team_members")

    invite = await members_col.find_one(
        {"invite_token": body.invite_token, "status": "pending"}
    )
    if not invite:
        raise HTTPException(
            status_code=404, detail="Invite not found or already accepted."
        )

    now = datetime.utcnow()
    await members_col.update_one(
        {"invite_token": body.invite_token},
        {
            "$set": {
                "user_id": user_id,
                "status": "active",
                "accepted_at": now,
            }
        },
    )

    audit_col = get_collection("audit_log")
    await audit_col.insert_one(
        {
            "tenant_id": invite["tenant_id"],
            "action": "accept_invite",
            "entity": "team_member",
            "entity_id": user_id,
            "timestamp": now,
        }
    )
    return {
        "status": "accepted",
        "tenant_id": invite["tenant_id"],
        "role": invite["role"],
    }


@router.get("/invites")
async def list_invites(tenant_id: str = Depends(get_current_user)):
    """List all pending invites for the tenant (SOC Manager only)."""
    members_col = get_collection("team_members")
    await require_role("soc_manager", members_col, tenant_id, tenant_id)

    cursor = members_col.find(
        {"tenant_id": tenant_id, "status": "pending"}, {"_id": 0}
    ).sort("invited_at", -1)
    invites = await cursor.to_list(length=500)
    return invites
