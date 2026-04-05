from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from db.ops.booster import (
    get_boost_config,
    save_boost_config,
    get_boost_stats,
    get_boost_record,
    get_restricted_members,
    get_exempted_users,
    create_credit_request,
    get_pending_credit_requests,
    get_credit_request,
    approve_credit_request,
    deny_credit_request,
    get_unassigned_adds,
    assign_manual_add_credit,
    record_manual_add,
    get_recent_manual_adds,
    get_invited_by,
    get_user_invites,
    get_recent_invite_events,
    get_all_boost_records,
    create_boost_record,
    set_unlocked,
    set_restricted,
    set_exempted,
    grant_access,
    revoke_access,
    reset_boost_record,
)

router = APIRouter(prefix="/api/groups/{chat_id}/boost", tags=["member-boost"])


# ==================== Config ====================


class BoostConfigUpdate(BaseModel):
    force_add_enabled: Optional[bool] = None
    force_add_required: Optional[int] = None
    force_add_action: Optional[str] = None
    force_add_message: Optional[str] = None
    force_add_unlock_message: Optional[str] = None
    force_add_progress_style: Optional[str] = None
    manual_add_credit_enabled: Optional[bool] = None
    manual_add_auto_detect: Optional[bool] = None
    manual_add_witness_mode: Optional[bool] = None
    exempt_admins: Optional[bool] = None
    exempt_specific_users: Optional[List[int]] = None
    notify_group_on_unlock: Optional[bool] = None
    log_channel_id: Optional[int] = None


@router.get("/config")
async def get_boost_config_route(chat_id: int):
    """Get boost configuration for a group."""
    return await get_boost_config(chat_id)


@router.put("/config")
async def update_boost_config(chat_id: int, config: BoostConfigUpdate):
    """Update boost configuration."""
    current = await get_boost_config(chat_id)
    update_data = config.model_dump(exclude_unset=True)
    current.update(update_data)
    await save_boost_config(chat_id, current)
    return {"success": True, "config": current}


# ==================== Stats ====================


@router.get("/stats")
async def get_boost_stats_route(chat_id: int):
    """Get boost statistics for a group."""
    return await get_boost_stats(chat_id)


# ==================== Records ====================


@router.get("/records")
async def get_all_records(chat_id: int):
    """Get all boost records for a group."""
    return await get_all_boost_records(chat_id)


@router.get("/records/{user_id}")
async def get_user_record(chat_id: int, user_id: int):
    """Get a specific user's boost record."""
    record = await get_boost_record(chat_id, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/restricted")
async def get_restricted(chat_id: int):
    """Get all restricted members."""
    return await get_restricted_members(chat_id)


@router.get("/exempted")
async def get_exempted(chat_id: int):
    """Get all exempted users."""
    return await get_exempted_users(chat_id)


# ==================== Manual Add Credit Requests ====================


class CreditRequestCreate(BaseModel):
    claimant_user_id: int
    claimant_username: Optional[str] = None
    claimed_count: int = 1
    claimed_user_ids: Optional[List[int]] = None


class CreditApproval(BaseModel):
    amount: int
    reviewed_by: int
    note: Optional[str] = None


class CreditDenial(BaseModel):
    reviewed_by: int
    reason: Optional[str] = None


class AssignCredit(BaseModel):
    added_user_id: int
    inviter_user_id: int


@router.get("/credits/pending")
async def get_pending_credits(chat_id: int):
    """Get all pending credit requests."""
    return await get_pending_credit_requests(chat_id)


@router.post("/credits/request")
async def create_credit_request_route(chat_id: int, request: CreditRequestCreate):
    """Create a new credit request."""
    result = await create_credit_request(
        chat_id,
        request.claimant_user_id,
        request.claimant_username,
        request.claimed_count,
        request.claimed_user_ids,
    )
    return {"success": True, "request": result}


@router.post("/credits/{request_id}/approve")
async def approve_credit(chat_id: int, request_id: int, data: CreditApproval):
    """Approve a credit request."""
    result = await approve_credit_request(
        chat_id, request_id, data.amount, data.reviewed_by, data.note
    )
    if not result:
        raise HTTPException(status_code=404, detail="Credit request not found")
    return {"success": True, "request": result}


@router.post("/credits/{request_id}/deny")
async def deny_credit(chat_id: int, request_id: int, data: CreditDenial):
    """Deny a credit request."""
    result = await deny_credit_request(chat_id, request_id, data.reviewed_by, data.reason)
    if not result:
        raise HTTPException(status_code=404, detail="Credit request not found")
    return {"success": True, "request": result}


# ==================== Manual Add Tracking ====================


@router.get("/manual-adds")
async def get_unassigned_manual_adds(chat_id: int, hours: int = 24):
    """Get unassigned manual adds."""
    return await get_unassigned_adds(chat_id, hours)


@router.get("/manual-adds/recent")
async def get_recent_manual_adds_route(chat_id: int, hours: int = 2):
    """Get recent manual adds for correlation."""
    return await get_recent_manual_adds(chat_id, hours)


@router.post("/manual-adds/assign")
async def assign_manual_add(chat_id: int, data: AssignCredit):
    """Assign credit for a manual add."""
    success = await assign_manual_add_credit(chat_id, data.added_user_id, data.inviter_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Manual add not found or already credited")
    return {"success": True}


@router.post("/manual-adds/record")
async def record_manual_add_route(
    chat_id: int,
    added_user_id: int,
    added_username: Optional[str] = None,
    added_first_name: Optional[str] = None,
    added_by_user_id: Optional[int] = None,
):
    """Record a detected manual add."""
    result = await record_manual_add(
        chat_id, added_user_id, added_username, added_first_name, added_by_user_id
    )
    return {"success": True, "record": result}


# ==================== Invite Tracking ====================


@router.get("/invited-by/{user_id}")
async def get_invited_by_route(chat_id: int, user_id: int):
    """Get who invited a specific user."""
    return await get_invited_by(chat_id, user_id)


@router.get("/invites/{user_id}")
async def get_user_invites_route(chat_id: int, user_id: int):
    """Get all users a person has invited."""
    return await get_user_invites(chat_id, user_id)


@router.get("/events")
async def get_recent_events(chat_id: int, limit: int = 50):
    """Get recent boost events."""
    return await get_recent_invite_events(chat_id, limit)


@router.get("/tracking")
async def get_boost_tracking(chat_id: int):
    """Get all boost records with tracking info for the Mini App."""
    records = await get_all_boost_records(chat_id)

    # Enrich records with additional tracking info
    members = []
    for record in records:
        # Check if record was manually granted (unlocked without enough invites)
        total_credits = (record.get("invited_count", 0) + record.get("manual_credits", 0))
        required = record.get("required_count", 0)
        is_manual_grant = record.get("is_unlocked") and total_credits < required and required > 0

        members.append({
            "user_id": record.get("user_id"),
            "username": record.get("username"),
            "first_name": record.get("first_name"),
            "invite_count": total_credits,
            "required_count": required,
            "unlocked": record.get("is_unlocked", False),
            "granted": record.get("is_unlocked", False),
            "manual": is_manual_grant,
            "is_restricted": record.get("is_restricted", False),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        })

    return {"members": members}


# ==================== Actions ====================


class ExemptRequest(BaseModel):
    user_id: int
    exempted_by: Optional[int] = None
    reason: Optional[str] = None


class GrantRequest(BaseModel):
    user_id: int


class ResetRequest(BaseModel):
    user_id: Optional[int] = None  # None means reset all


@router.post("/exempt")
async def exempt_user(chat_id: int, data: ExemptRequest):
    """Exempt a user from boost requirement."""
    result = await set_exempted(chat_id, data.user_id, True, data.exempted_by, data.reason)
    return {"success": True, "record": result}


@router.delete("/exempt/{user_id}")
async def remove_exemption(chat_id: int, user_id: int):
    """Remove exemption from a user."""
    result = await set_exempted(chat_id, user_id, False)
    return {"success": True, "record": result}


@router.post("/grant")
async def grant_access_route(chat_id: int, data: GrantRequest):
    """Manually grant access to a user."""
    result = await grant_access(chat_id, data.user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Boost record not found")
    return {"success": True, "record": result}


@router.post("/revoke")
async def revoke_access_route(chat_id: int, data: GrantRequest):
    """Revoke manually granted access."""
    result = await revoke_access(chat_id, data.user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Boost record not found")
    return {"success": True, "record": result}


@router.post("/reset")
async def reset_boost_route(chat_id: int, data: ResetRequest):
    """Reset boost record for a user or all users."""
    if data.user_id:
        success = await reset_boost_record(chat_id, data.user_id)
    else:
        # Reset all - delete all records
        records = await get_all_boost_records(chat_id)
        for record in records:
            await reset_boost_record(chat_id, record["user_id"])
        success = True

    return {"success": success}


@router.post("/unlock/{user_id}")
async def unlock_user(chat_id: int, user_id: int):
    """Manually unlock a user."""
    result = await set_unlocked(chat_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Boost record not found")
    return {"success": True, "record": result}


@router.post("/restrict/{user_id}")
async def restrict_user(chat_id: int, user_id: int):
    """Manually restrict a user."""
    result = await set_restricted(chat_id, user_id, True)
    return {"success": True, "record": result}
