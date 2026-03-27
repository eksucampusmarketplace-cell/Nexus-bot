"""
api/routes/tickets.py

REST API for the ticket / support system — used by the Mini App dashboard.

Endpoints:
  GET    /api/groups/{chat_id}/tickets                  — list tickets (with filters)
  GET    /api/groups/{chat_id}/tickets/analytics        — ticket analytics
  GET    /api/groups/{chat_id}/tickets/sla              — get SLA configs
  PUT    /api/groups/{chat_id}/tickets/sla              — update SLA config
  GET    /api/groups/{chat_id}/tickets/workload         — staff workload
  GET    /api/groups/{chat_id}/tickets/templates        — response templates
  POST   /api/groups/{chat_id}/tickets/templates        — create/update template
  DELETE /api/groups/{chat_id}/tickets/templates/{name} — delete template
  GET    /api/groups/{chat_id}/tickets/{id}             — get single ticket
  GET    /api/groups/{chat_id}/tickets/{id}/messages    — get ticket messages
  POST   /api/groups/{chat_id}/tickets/{id}/message     — add message to ticket
  POST   /api/groups/{chat_id}/tickets/{id}/assign      — assign ticket
  POST   /api/groups/{chat_id}/tickets/{id}/close       — close ticket
  POST   /api/groups/{chat_id}/tickets/{id}/escalate    — escalate ticket
  POST   /api/groups/{chat_id}/tickets/{id}/priority    — change priority
  POST   /api/groups/{chat_id}/tickets/{id}/survey      — submit satisfaction survey
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import get_current_user
from db.client import db
from db.ops import tickets as db_tickets

log = logging.getLogger("tickets_api")

router = APIRouter(prefix="/api/groups/{chat_id}/tickets")


# ── Request Models ──────────────────────────────────────────────────────────


class AssignRequest(BaseModel):
    staff_id: int
    staff_name: str = ""


class MessageRequest(BaseModel):
    message_text: str
    is_staff: bool = True


class CloseRequest(BaseModel):
    note: str = ""


class PriorityRequest(BaseModel):
    priority: str  # low | normal | high | urgent


class SLAConfigRequest(BaseModel):
    priority: str = "normal"
    response_time_mins: int = 60
    resolution_time_mins: int = 1440
    escalation_chain: list[int] = []
    auto_close_hours: int = 48


class SurveyRequest(BaseModel):
    rating: int  # 1-5
    comment: str = ""


class TemplateRequest(BaseModel):
    name: str
    content: str
    category: str | None = None


# ── List / Analytics ────────────────────────────────────────────────────────


@router.get("")
async def list_tickets(
    chat_id: int,
    status: str | None = Query(None, description="Filter: open|in_progress|escalated|closed|all"),
    priority: str | None = Query(None, description="Filter: low|normal|high|urgent"),
    assigned_to: int | None = Query(None, description="Filter by assigned staff ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List tickets for a group with optional filters."""
    tickets = await db_tickets.get_tickets(
        db.pool,
        chat_id,
        status=status,
        assigned_to=assigned_to,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    total = await db_tickets.count_tickets(db.pool, chat_id, status=status)
    return {"tickets": tickets, "total": total, "limit": limit, "offset": offset}


@router.get("/analytics")
async def ticket_analytics(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    """Get ticket analytics for a group."""
    stats = await db_tickets.get_ticket_analytics(db.pool, chat_id)
    return {"analytics": stats}


@router.get("/workload")
async def staff_workload(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    """Get staff workload (active ticket counts per staff member)."""
    workload = await db_tickets.get_staff_workload(db.pool, chat_id)
    return {"workload": workload}


# ── SLA Configuration ──────────────────────────────────────────────────────


@router.get("/sla")
async def get_sla_configs(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    """Get all SLA configurations for a group."""
    configs = await db_tickets.get_all_sla_configs(db.pool, chat_id)
    return {"sla_configs": configs}


@router.put("/sla")
async def update_sla_config(
    chat_id: int,
    body: SLAConfigRequest,
    user: dict = Depends(get_current_user),
):
    """Create or update SLA config for a group and priority level."""
    if body.priority not in ("low", "normal", "high", "urgent"):
        raise HTTPException(status_code=400, detail="Invalid priority")
    if body.response_time_mins < 1:
        raise HTTPException(status_code=400, detail="Response time must be >= 1 minute")
    if body.resolution_time_mins < 1:
        raise HTTPException(status_code=400, detail="Resolution time must be >= 1 minute")

    config = await db_tickets.upsert_sla_config(
        db.pool,
        chat_id,
        priority=body.priority,
        response_time_mins=body.response_time_mins,
        resolution_time_mins=body.resolution_time_mins,
        escalation_chain=body.escalation_chain,
        auto_close_hours=body.auto_close_hours,
    )
    return {"ok": True, "sla_config": config}


# ── Templates ──────────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    """Get all response templates for a group."""
    templates = await db_tickets.get_templates(db.pool, chat_id)
    return {"templates": templates}


@router.post("/templates")
async def create_template(
    chat_id: int,
    body: TemplateRequest,
    user: dict = Depends(get_current_user),
):
    """Create or update a response template."""
    user_id = user.get("user_id") or user.get("id") or 0
    template = await db_tickets.upsert_template(
        db.pool,
        chat_id,
        name=body.name,
        content=body.content,
        category=body.category,
        created_by=user_id,
    )
    return {"ok": True, "template": template}


@router.delete("/templates/{name}")
async def delete_template(
    chat_id: int,
    name: str,
    user: dict = Depends(get_current_user),
):
    """Delete a response template."""
    success = await db_tickets.delete_template(db.pool, chat_id, name)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


# ── Single Ticket ──────────────────────────────────────────────────────────


@router.get("/{ticket_id}")
async def get_ticket(
    chat_id: int,
    ticket_id: int,
    user: dict = Depends(get_current_user),
):
    """Get a single ticket by ID."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/{ticket_id}/messages")
async def get_ticket_messages(
    chat_id: int,
    ticket_id: int,
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """Get messages for a ticket thread."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages = await db_tickets.get_ticket_messages(db.pool, ticket_id, limit=limit)
    return {"messages": messages, "ticket_id": ticket_id}


@router.post("/{ticket_id}/message")
async def add_ticket_message(
    chat_id: int,
    ticket_id: int,
    body: MessageRequest,
    user: dict = Depends(get_current_user),
):
    """Add a message to a ticket thread."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket is closed")

    user_id = user.get("user_id") or user.get("id") or 0
    user_name = user.get("first_name", "")
    msg = await db_tickets.add_ticket_message(
        db.pool,
        ticket_id,
        sender_id=user_id,
        sender_name=user_name,
        message_text=body.message_text,
        is_staff=body.is_staff,
    )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat_id, "ticket_message", {
            "ticket_id": ticket_id,
            "sender_id": user_id,
            "message_text": body.message_text,
            "is_staff": body.is_staff,
            "chat_id": chat_id,
        })
    except Exception:
        pass

    return {"ok": True, "message": msg}


# ── Ticket Actions ─────────────────────────────────────────────────────────


@router.post("/{ticket_id}/assign")
async def assign_ticket(
    chat_id: int,
    ticket_id: int,
    body: AssignRequest,
    user: dict = Depends(get_current_user),
):
    """Assign a ticket to a staff member."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket is closed")

    user_id = user.get("user_id") or user.get("id") or 0
    await db_tickets.assign_ticket(
        db.pool, ticket_id, body.staff_id, body.staff_name, assigned_by=user_id
    )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat_id, "ticket_assigned", {
            "ticket_id": ticket_id,
            "assigned_to": body.staff_id,
            "assigned_name": body.staff_name,
            "chat_id": chat_id,
        })
    except Exception:
        pass

    return {"ok": True, "ticket_id": ticket_id, "assigned_to": body.staff_id}


@router.post("/{ticket_id}/close")
async def close_ticket(
    chat_id: int,
    ticket_id: int,
    body: CloseRequest,
    user: dict = Depends(get_current_user),
):
    """Close a ticket."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket already closed")

    user_id = user.get("user_id") or user.get("id") or 0
    await db_tickets.update_ticket_status(db.pool, ticket_id, "closed", closed_by=user_id)

    if body.note:
        await db_tickets.add_ticket_message(
            db.pool, ticket_id, user_id, user.get("first_name", ""),
            body.note, is_staff=True, is_system=False,
        )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat_id, "ticket_closed", {
            "ticket_id": ticket_id,
            "closed_by": user_id,
            "chat_id": chat_id,
        })
    except Exception:
        pass

    return {"ok": True, "ticket_id": ticket_id, "status": "closed"}


@router.post("/{ticket_id}/escalate")
async def escalate_ticket(
    chat_id: int,
    ticket_id: int,
    user: dict = Depends(get_current_user),
):
    """Escalate a ticket to the next level."""
    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket is closed")

    updated = await db_tickets.escalate_ticket(db.pool, ticket_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to escalate ticket")

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat_id, "ticket_escalated", {
            "ticket_id": ticket_id,
            "escalation_level": updated["escalation_level"],
            "chat_id": chat_id,
        })
    except Exception:
        pass

    return {"ok": True, "ticket_id": ticket_id, "escalation_level": updated["escalation_level"]}


@router.post("/{ticket_id}/priority")
async def change_priority(
    chat_id: int,
    ticket_id: int,
    body: PriorityRequest,
    user: dict = Depends(get_current_user),
):
    """Change ticket priority."""
    if body.priority not in ("low", "normal", "high", "urgent"):
        raise HTTPException(status_code=400, detail="Invalid priority")

    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db_tickets.update_ticket_priority(db.pool, ticket_id, body.priority)
    return {"ok": True, "ticket_id": ticket_id, "priority": body.priority}


@router.post("/{ticket_id}/survey")
async def submit_survey(
    chat_id: int,
    ticket_id: int,
    body: SurveyRequest,
    user: dict = Depends(get_current_user),
):
    """Submit a satisfaction survey for a closed ticket."""
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    ticket = await db_tickets.get_ticket(db.pool, ticket_id)
    if not ticket or ticket["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] != "closed":
        raise HTTPException(status_code=409, detail="Survey only available for closed tickets")

    success = await db_tickets.submit_satisfaction(db.pool, ticket_id, body.rating, body.comment)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to submit survey")

    return {"ok": True, "ticket_id": ticket_id, "rating": body.rating}
