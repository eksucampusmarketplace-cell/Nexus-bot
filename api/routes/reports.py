"""
api/routes/reports.py

REST API for the report system — used by the Mini App admin dashboard.

Endpoints:
  GET  /api/groups/{chat_id}/reports            — list open reports
  GET  /api/groups/{chat_id}/reports/all        — list all reports (with optional ?status=)
  GET  /api/groups/{chat_id}/reports/{id}       — get a single report
  POST /api/groups/{chat_id}/reports/{id}/resolve
  POST /api/groups/{chat_id}/reports/{id}/dismiss
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from api.auth import get_current_user
from db.client import db
from db.ops import reports as db_reports

router = APIRouter(prefix="/api/groups/{chat_id}/reports")


class ResolveRequest(BaseModel):
    note: str = ""
    status: str = "resolved"
    action: str = ""


@router.get("")
async def list_open_reports(
    chat_id: int,
    user: dict = Depends(get_current_user),
):
    """Return all open reports for the group."""
    rows = await db_reports.get_open_reports(db.pool, chat_id)
    return {"reports": rows, "count": len(rows)}


@router.get("/all")
async def list_all_reports(
    chat_id: int,
    status: str | None = Query(None, description="Filter by status: open | resolved | dismissed"),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Return all reports for the group with optional status filter."""
    rows = await db_reports.get_all_reports(db.pool, chat_id, limit=limit)
    if status:
        rows = [r for r in rows if r["status"] == status]
    return {"reports": rows, "count": len(rows)}


@router.get("/{report_id}")
async def get_report(
    chat_id: int,
    report_id: int,
    user: dict = Depends(get_current_user),
):
    """Return a single report."""
    report = await db_reports.get_report(db.pool, report_id)
    if not report or report["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/{report_id}/resolve")
async def resolve_report(
    chat_id: int,
    report_id: int,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
):
    """Mark a report as resolved."""
    report = await db_reports.get_report(db.pool, report_id)
    if not report or report["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Report not found")

    user_id = user.get("user_id") or user.get("id") or 0
    success = await db_reports.resolve_report(
        pool=db.pool,
        report_id=report_id,
        resolved_by=user_id,
        status="resolved",
        note=body.note,
    )
    if not success:
        raise HTTPException(status_code=409, detail="Report already actioned")
    return {"ok": True, "report_id": report_id, "status": "resolved"}


@router.put("/{report_id}")
async def update_report_status(
    chat_id: int,
    report_id: int,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
):
    """Update report status (resolve/dismiss/etc) via PUT."""
    report = await db_reports.get_report(db.pool, report_id)
    if not report or report["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Report not found")

    user_id = user.get("user_id") or user.get("id") or 0
    status = body.status if body.status in ("resolved", "dismissed") else "resolved"
    await db_reports.resolve_report(
        pool=db.pool,
        report_id=report_id,
        resolved_by=user_id,
        status=status,
        note=body.note or "",
    )
    return {"ok": True, "report_id": report_id, "status": status}


@router.post("/{report_id}/dismiss")
async def dismiss_report(
    chat_id: int,
    report_id: int,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
):
    """Dismiss a report."""
    report = await db_reports.get_report(db.pool, report_id)
    if not report or report["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Report not found")

    user_id = user.get("user_id") or user.get("id") or 0
    success = await db_reports.resolve_report(
        pool=db.pool,
        report_id=report_id,
        resolved_by=user_id,
        status="dismissed",
        note=body.note,
    )
    if not success:
        raise HTTPException(status_code=409, detail="Report already actioned")
    return {"ok": True, "report_id": report_id, "status": "dismissed"}
