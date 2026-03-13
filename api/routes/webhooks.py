"""
API Routes for Webhook Integrations

Provides endpoints for:
- CRUD operations on webhook configurations
- Testing webhooks
- Viewing delivery logs
- Getting available event types
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel, HttpUrl

from api.auth import get_current_user
from db.client import db
import db.ops.webhooks as webhooks_db

router = APIRouter(prefix="/api/groups")


# Valid event types for webhooks
VALID_EVENT_TYPES = [
    "member_join",
    "member_leave", 
    "ban",
    "unban",
    "mute",
    "unmute",
    "warn",
    "kick",
    "message",
    "automod_trigger",
    "report_created",
    "settings_change",
    "all"  # Subscribe to everything
]


class WebhookCreate(BaseModel):
    name: str
    url: HttpUrl
    events: List[str]
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookTest(BaseModel):
    event_type: str = "member_join"


@router.get("/{chat_id}/webhooks")
async def list_webhooks(
    chat_id: int,
    user: dict = Depends(get_current_user)
):
    """List all webhooks configured for a group."""
    webhooks = await webhooks_db.get_webhooks(chat_id)
    stats = await webhooks_db.get_chat_webhook_stats(chat_id)
    return {
        "webhooks": webhooks,
        "stats": stats
    }


@router.post("/{chat_id}/webhooks")
async def create_webhook(
    chat_id: int,
    data: WebhookCreate,
    user: dict = Depends(get_current_user)
):
    """Create a new webhook configuration."""
    # Validate event types
    invalid_events = [e for e in data.events if e not in VALID_EVENT_TYPES]
    if invalid_events:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event types: {', '.join(invalid_events)}"
        )
    
    webhook = await webhooks_db.create_webhook(
        chat_id=chat_id,
        name=data.name,
        url=str(data.url),
        events=data.events,
        secret=data.secret,
        created_by=user.get("id")
    )
    
    if not webhook:
        raise HTTPException(status_code=500, detail="Failed to create webhook")
    
    return webhook


@router.get("/{chat_id}/webhooks/{webhook_id}")
async def get_webhook(
    chat_id: int,
    webhook_id: int,
    user: dict = Depends(get_current_user)
):
    """Get a specific webhook configuration."""
    webhook = await webhooks_db.get_webhook_by_id(webhook_id)
    if not webhook or webhook["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.put("/{chat_id}/webhooks/{webhook_id}")
async def update_webhook(
    chat_id: int,
    webhook_id: int,
    data: WebhookUpdate,
    user: dict = Depends(get_current_user)
):
    """Update a webhook configuration."""
    # Verify webhook exists and belongs to this group
    existing = await webhooks_db.get_webhook_by_id(webhook_id)
    if not existing or existing["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Validate event types if provided
    if data.events:
        invalid_events = [e for e in data.events if e not in VALID_EVENT_TYPES]
        if invalid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event types: {', '.join(invalid_events)}"
            )
    
    webhook = await webhooks_db.update_webhook(
        webhook_id=webhook_id,
        name=data.name,
        url=str(data.url) if data.url else None,
        events=data.events,
        secret=data.secret,
        is_active=data.is_active
    )
    
    return webhook


@router.delete("/{chat_id}/webhooks/{webhook_id}")
async def delete_webhook(
    chat_id: int,
    webhook_id: int,
    user: dict = Depends(get_current_user)
):
    """Delete a webhook configuration."""
    existing = await webhooks_db.get_webhook_by_id(webhook_id)
    if not existing or existing["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    success = await webhooks_db.delete_webhook(webhook_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete webhook")
    
    return {"success": True}


@router.post("/{chat_id}/webhooks/{webhook_id}/test")
async def test_webhook(
    chat_id: int,
    webhook_id: int,
    data: WebhookTest,
    user: dict = Depends(get_current_user)
):
    """Send a test payload to a webhook."""
    import httpx
    import hmac
    import hashlib
    import time
    import json
    
    webhook = await webhooks_db.get_webhook_by_id(webhook_id)
    if not webhook or webhook["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Build test payload
    payload = {
        "event": data.event_type,
        "timestamp": int(time.time()),
        "test": True,
        "data": {
            "chat_id": chat_id,
            "chat_title": "Test Group",
            "user_id": user.get("id"),
            "user_name": user.get("first_name", "Test User"),
            "message": "This is a test event from Nexus Bot"
        }
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    
    # Build headers
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": data.event_type,
        "X-Webhook-Test": "true",
        "User-Agent": "NexusBot-Webhook/1.0"
    }
    
    # Add HMAC signature if secret is configured
    if webhook.get("secret"):
        signature = hmac.new(
            webhook["secret"].encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    
    # Send request
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook["url"],
                content=payload_bytes,
                headers=headers
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        success = 200 <= response.status_code < 300
        
        # Log the delivery
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=data.event_type,
            payload=payload,
            success=success,
            response_status=response.status_code,
            response_body=response.text[:1000],
            duration_ms=duration_ms
        )
        
        return {
            "success": success,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "response_preview": response.text[:200] if response.text else None
        }
        
    except httpx.TimeoutException:
        duration_ms = int((time.time() - start_time) * 1000)
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=data.event_type,
            payload=payload,
            success=False,
            response_status=None,
            response_body="Request timeout",
            duration_ms=duration_ms
        )
        return {
            "success": False,
            "error": "Timeout",
            "duration_ms": duration_ms
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=data.event_type,
            payload=payload,
            success=False,
            response_status=None,
            response_body=str(e)[:500],
            duration_ms=duration_ms
        )
        return {
            "success": False,
            "error": str(e),
            "duration_ms": duration_ms
        }


@router.get("/{chat_id}/webhooks/{webhook_id}/deliveries")
async def get_webhook_deliveries(
    chat_id: int,
    webhook_id: int,
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    """Get delivery history for a webhook."""
    webhook = await webhooks_db.get_webhook_by_id(webhook_id)
    if not webhook or webhook["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    deliveries = await webhooks_db.get_webhook_deliveries(webhook_id, limit)
    return {"deliveries": deliveries}


@router.get("/webhooks/events")
async def list_event_types(user: dict = Depends(get_current_user)):
    """List all available webhook event types with descriptions."""
    return {
        "events": [
            {"type": "member_join", "description": "Triggered when a new member joins the group", "icon": "👋"},
            {"type": "member_leave", "description": "Triggered when a member leaves or is removed", "icon": "👋"},
            {"type": "ban", "description": "Triggered when a member is banned", "icon": "🚫"},
            {"type": "unban", "description": "Triggered when a member is unbanned", "icon": "✅"},
            {"type": "mute", "description": "Triggered when a member is muted", "icon": "🔇"},
            {"type": "unmute", "description": "Triggered when a member is unmuted", "icon": "🔊"},
            {"type": "warn", "description": "Triggered when a member receives a warning", "icon": "⚠️"},
            {"type": "kick", "description": "Triggered when a member is kicked", "icon": "👢"},
            {"type": "message", "description": "Triggered on every message (use with caution)", "icon": "💬"},
            {"type": "automod_trigger", "description": "Triggered when AutoMod takes action", "icon": "🤖"},
            {"type": "report_created", "description": "Triggered when a new report is submitted", "icon": "🚨"},
            {"type": "settings_change", "description": "Triggered when group settings are modified", "icon": "⚙️"},
            {"type": "all", "description": "Subscribe to all events (high volume)", "icon": "📡"},
        ]
    }
