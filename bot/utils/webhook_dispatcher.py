"""
Webhook Dispatcher Service

Handles sending events to configured webhooks.
Used by bot handlers to notify external systems.
"""
import asyncio
import json
import logging
import time
import hmac
import hashlib
from typing import Dict, Any, Optional
import httpx

from db.client import db
import db.ops.webhooks as webhooks_db

logger = logging.getLogger(__name__)


async def dispatch_event(
    chat_id: int,
    event_type: str,
    data: Dict[str, Any],
    db_pool=None
):
    """
    Dispatch an event to all subscribed webhooks for a group.
    
    Args:
        chat_id: The group chat ID
        event_type: Type of event (member_join, ban, etc.)
        data: Event payload data
        db_pool: Optional database pool (uses default if not provided)
    """
    pool = db_pool or db.pool
    if not pool:
        logger.warning(f"[WEBHOOK] No DB pool available for event {event_type}")
        return
    
    try:
        webhooks = await webhooks_db.get_active_webhooks_for_event(chat_id, event_type)
        
        if not webhooks:
            return
        
        logger.debug(f"[WEBHOOK] Dispatching {event_type} to {len(webhooks)} webhooks for chat {chat_id}")
        
        # Fire and forget - don't block the bot
        asyncio.create_task(_send_to_webhooks(webhooks, event_type, data))
        
    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to dispatch {event_type}: {e}")


async def _send_to_webhooks(
    webhooks: list,
    event_type: str,
    data: Dict[str, Any]
):
    """Send event to multiple webhooks concurrently."""
    tasks = [
        _send_single_webhook(webhook, event_type, data)
        for webhook in webhooks
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _send_single_webhook(
    webhook: Dict[str, Any],
    event_type: str,
    data: Dict[str, Any]
):
    """Send event to a single webhook."""
    webhook_id = webhook["id"]
    url = webhook["url"]
    secret = webhook.get("secret")
    
    # Build payload
    payload = {
        "event": event_type,
        "timestamp": int(time.time()),
        "webhook_id": webhook_id,
        "data": data
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    
    # Build headers
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event_type,
        "X-Webhook-ID": str(webhook_id),
        "User-Agent": "NexusBot-Webhook/1.0"
    }
    
    # Add HMAC signature if secret is configured
    if secret:
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    
    # Send request
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                content=payload_bytes,
                headers=headers
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        success = 200 <= response.status_code < 300
        
        # Log delivery
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            success=success,
            response_status=response.status_code,
            response_body=response.text[:1000] if not success else None,
            duration_ms=duration_ms
        )
        
        if not success:
            logger.warning(
                f"[WEBHOOK] Delivery failed | webhook={webhook_id} | "
                f"event={event_type} | status={response.status_code}"
            )
        else:
            logger.debug(
                f"[WEBHOOK] Delivered | webhook={webhook_id} | "
                f"event={event_type} | duration={duration_ms}ms"
            )
            
    except httpx.TimeoutException:
        duration_ms = int((time.time() - start_time) * 1000)
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            success=False,
            response_status=None,
            response_body="Request timeout",
            duration_ms=duration_ms
        )
        logger.warning(f"[WEBHOOK] Timeout | webhook={webhook_id} | event={event_type}")
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        await webhooks_db.log_webhook_delivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            success=False,
            response_status=None,
            response_body=str(e)[:500],
            duration_ms=duration_ms
        )
        logger.error(f"[WEBHOOK] Error | webhook={webhook_id} | event={event_type} | error={e}")


# Convenience methods for common events

async def notify_member_join(
    chat_id: int,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a new member joining."""
    await dispatch_event(chat_id, "member_join", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        **kwargs
    })


async def notify_member_leave(
    chat_id: int,
    user_id: int,
    chat_title: str,
    reason: Optional[str] = None,
    **kwargs
):
    """Notify webhooks about a member leaving."""
    await dispatch_event(chat_id, "member_leave", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "reason": reason,
        **kwargs
    })


async def notify_ban(
    chat_id: int,
    user_id: int,
    admin_id: int,
    admin_name: str,
    reason: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a ban."""
    await dispatch_event(chat_id, "ban", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "reason": reason,
        **kwargs
    })


async def notify_mute(
    chat_id: int,
    user_id: int,
    admin_id: int,
    admin_name: str,
    duration: Optional[int],
    reason: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a mute."""
    await dispatch_event(chat_id, "mute", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "duration_seconds": duration,
        "reason": reason,
        **kwargs
    })


async def notify_warn(
    chat_id: int,
    user_id: int,
    admin_id: int,
    admin_name: str,
    warn_count: int,
    max_warns: int,
    reason: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a warning."""
    await dispatch_event(chat_id, "warn", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "warn_count": warn_count,
        "max_warns": max_warns,
        "reason": reason,
        **kwargs
    })


async def notify_kick(
    chat_id: int,
    user_id: int,
    admin_id: int,
    admin_name: str,
    reason: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a kick."""
    await dispatch_event(chat_id, "kick", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "reason": reason,
        **kwargs
    })


async def notify_automod(
    chat_id: int,
    user_id: int,
    rule_triggered: str,
    action_taken: str,
    message_preview: Optional[str],
    chat_title: str,
    **kwargs
):
    """Notify webhooks about AutoMod action."""
    await dispatch_event(chat_id, "automod_trigger", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "user_id": user_id,
        "rule_triggered": rule_triggered,
        "action_taken": action_taken,
        "message_preview": message_preview[:200] if message_preview else None,
        **kwargs
    })


async def notify_report(
    chat_id: int,
    report_id: int,
    reporter_id: int,
    reported_id: int,
    reason: str,
    chat_title: str,
    **kwargs
):
    """Notify webhooks about a new report."""
    await dispatch_event(chat_id, "report_created", {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "report_id": report_id,
        "reporter_id": reporter_id,
        "reported_id": reported_id,
        "reason": reason,
        **kwargs
    })
