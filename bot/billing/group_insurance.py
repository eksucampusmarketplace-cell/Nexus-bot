"""
bot/billing/group_insurance.py

Group Insurance / SLA System - Premium protection for Telegram groups.

Admins subscribe to group insurance. If their group gets:
- Raided (mass join attack)
- Spammed (mass message attack)
- Compromised (bot takeover, permissions changed)

Nexus automatically:
1. Locks down the group
2. Cleans up spam/raid members
3. Restores permissions
4. Reports to admin

This is a product differentiator - no other bot offers this guarantee.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("group_insurance")

# SLA tiers
TIER_FREE = "free"
TIER_BASIC = "basic"
TIER_PREMIUM = "premium"
TIER_ENTERPRISE = "enterprise"

# Protection types
PROTECTION_RAID = "raid"
PROTECTION_SPAM = "spam"
PROTECTION_COMPROMISE = "compromise"
PROTECTION_DDOS = "ddos"


async def get_group_insurance(pool, chat_id: int, bot_id: int) -> dict:
    """
    Get insurance status for a group.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tier, active, auto_lockdown, auto_cleanup, 
                       max_claims_per_month, claims_used, protection_types,
                       sla_reporting, last_incident_at, expires_at
                FROM group_insurance
                WHERE chat_id = $1 AND bot_id = $2
                """,
                chat_id,
                bot_id,
            )
            
            if row:
                return {
                    "tier": row["tier"] or TIER_FREE,
                    "active": row["active"] or False,
                    "auto_lockdown": row["auto_lockdown"] or False,
                    "auto_cleanup": row["auto_cleanup"] or False,
                    "max_claims_per_month": row["max_claims_per_month"] or 0,
                    "claims_used": row["claims_used"] or 0,
                    "protection_types": row["protection_types"] or [],
                    "sla_reporting": row["sla_reporting"] or False,
                    "last_incident_at": row["last_incident_at"],
                    "expires_at": row["expires_at"],
                }
            
            return {
                "tier": TIER_FREE,
                "active": False,
                "auto_lockdown": False,
                "auto_cleanup": False,
                "max_claims_per_month": 0,
                "claims_used": 0,
                "protection_types": [],
                "sla_reporting": False,
            }
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error getting status: {e}")
        return {"tier": TIER_FREE, "active": False}


async def enable_group_insurance(
    pool,
    chat_id: int,
    bot_id: int,
    tier: str = TIER_BASIC,
    protection_types: list[str] = None,
) -> dict:
    """
    Enable insurance for a group (called after successful payment).
    """
    if protection_types is None:
        protection_types = [PROTECTION_RAID, PROTECTION_SPAM]
    
    tier_config = _get_tier_config(tier)
    
    try:
        async with pool.acquire() as conn:
            # Calculate expiry (1 month)
            expires = datetime.now(timezone.utc) + timedelta(days=30)
            
            await conn.execute(
                """
                INSERT INTO group_insurance
                    (chat_id, bot_id, tier, active, auto_lockdown, auto_cleanup,
                     protection_types, max_claims_per_month, expires_at)
                VALUES ($1, $2, $3, TRUE, $4, $5, $6, $7, $8)
                ON CONFLICT (chat_id, bot_id) DO UPDATE SET
                    tier = $3,
                    active = TRUE,
                    auto_lockdown = $4,
                    auto_cleanup = $5,
                    protection_types = $6,
                    max_claims_per_month = $7,
                    expires_at = $8,
                    claims_used = 0
                """,
                chat_id,
                bot_id,
                tier,
                tier_config["auto_lockdown"],
                tier_config["auto_cleanup"],
                protection_types,
                tier_config["max_claims"],
                expires,
            )
            
        logger.info(f"[GROUP_INSURANCE] Enabled | chat={chat_id} tier={tier}")
        return {"ok": True, "expires_at": expires.isoformat()}
        
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error enabling: {e}")
        return {"ok": False, "error": str(e)}


async def disable_group_insurance(pool, chat_id: int, bot_id: int) -> dict:
    """
    Disable insurance (on cancellation or expiry).
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE group_insurance
                SET active = FALSE
                WHERE chat_id = $1 AND bot_id = $2
                """,
                chat_id,
                bot_id,
            )
            
        return {"ok": True}
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error disabling: {e}")
        return {"ok": False, "error": str(e)}


async def record_incident(
    pool,
    chat_id: int,
    bot_id: int,
    incident_type: str,
    severity: str,
    details: dict,
) -> dict:
    """
    Record an insurance incident (raid, spam, etc.).
    Returns whether auto-actions should be taken.
    """
    insurance = await get_group_insurance(pool, chat_id, bot_id)
    
    if not insurance["active"]:
        return {"auto_action": False, "reason": "not_insured"}
    
    if incident_type not in insurance["protection_types"]:
        return {"auto_action": False, "reason": "not_protected"}
    
    # Check if claims exhausted
    if insurance["claims_used"] >= insurance["max_claims_per_month"]:
        return {"auto_action": False, "reason": "claims_exhausted"}
    
    try:
        async with pool.acquire() as conn:
            # Record incident
            await conn.execute(
                """
                INSERT INTO insurance_incidents
                    (chat_id, bot_id, incident_type, severity, details, auto_action_taken)
                VALUES ($1, $2, $3, $4, $5, FALSE)
                """,
                chat_id,
                bot_id,
                incident_type,
                severity,
                str(details),
            )
            
            # Update claim count
            await conn.execute(
                """
                UPDATE group_insurance
                SET claims_used = claims_used + 1,
                    last_incident_at = NOW()
                WHERE chat_id = $1 AND bot_id = $2
                """,
                chat_id,
                bot_id,
            )
            
        return {
            "auto_action": insurance["auto_lockdown"] or insurance["auto_cleanup"],
            "auto_lockdown": insurance["auto_lockdown"],
            "auto_cleanup": insurance["auto_cleanup"],
            "incident_id": None,
        }
        
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error recording incident: {e}")
        return {"auto_action": False, "error": str(e)}


async def get_incidents(
    pool,
    chat_id: int,
    bot_id: int,
    days: int = 30,
) -> list[dict]:
    """
    Get recent incidents for a group.
    """
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, incident_type, severity, details, auto_action_taken, created_at
                FROM insurance_incidents
                WHERE chat_id = $1 AND bot_id = $2 AND created_at > $3
                ORDER BY created_at DESC
                """,
                chat_id,
                bot_id,
                since,
            )
            
            return [
                {
                    "id": row["id"],
                    "type": row["incident_type"],
                    "severity": row["severity"],
                    "details": row["details"],
                    "auto_action": row["auto_action_taken"],
                    "at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error getting incidents: {e}")
        return []


async def check_expiration(pool) -> list[dict]:
    """
    Check for expired insurance and disable them.
    Returns list of expired groups.
    """
    expired = []
    
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chat_id, bot_id, tier, expires_at
                FROM group_insurance
                WHERE active = TRUE AND expires_at < NOW()
                """
            )
            
            for row in rows:
                await conn.execute(
                    """
                    UPDATE group_insurance
                    SET active = FALSE
                    WHERE chat_id = $1 AND bot_id = $2
                    """,
                    row["chat_id"],
                    row["bot_id"],
                )
                expired.append({
                    "chat_id": row["chat_id"],
                    "bot_id": row["bot_id"],
                    "tier": row["tier"],
                })
                
    except Exception as e:
        logger.error(f"[GROUP_INSURANCE] Error checking expiration: {e}")
    
    return expired


def _get_tier_config(tier: str) -> dict:
    """Get configuration for insurance tier."""
    configs = {
        TIER_FREE: {
            "auto_lockdown": False,
            "auto_cleanup": False,
            "max_claims": 0,
            "sla_response": False,
        },
        TIER_BASIC: {
            "auto_lockdown": True,
            "auto_cleanup": True,
            "max_claims": 2,
            "sla_response": False,
        },
        TIER_PREMIUM: {
            "auto_lockdown": True,
            "auto_cleanup": True,
            "max_claims": 5,
            "sla_response": True,
        },
        TIER_ENTERPRISE: {
            "auto_lockdown": True,
            "auto_cleanup": True,
            "max_claims": 999,
            "sla_response": True,
        },
    }
    return configs.get(tier, configs[TIER_FREE])


async def get_tiers() -> list[dict]:
    """
    Get available insurance tiers for display.
    """
    return [
        {
            "tier": TIER_BASIC,
            "name": "Basic",
            "price_stars": 50,
            "features": [
                "Auto-lockdown on raid",
                "Auto-cleanup spam",
                "2 claims/month",
            ],
        },
        {
            "tier": TIER_PREMIUM,
            "name": "Premium",
            "price_stars": 100,
            "features": [
                "Everything in Basic",
                "5 claims/month",
                "SLA incident reports",
                "Priority support",
            ],
        },
        {
            "tier": TIER_ENTERPRISE,
            "name": "Enterprise",
            "price_stars": 250,
            "features": [
                "Everything in Premium",
                "Unlimited claims",
                "Dedicated incident manager",
                "Custom SLA terms",
            ],
        },
    ]