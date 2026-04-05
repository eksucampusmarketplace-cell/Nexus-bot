import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import get_current_user
from bot.utils.crypto import hash_token
from db.client import db
from db.ops.groups import get_group, get_user_managed_groups, update_group_settings
from db.ops.logs import get_recent_logs

router = APIRouter()
logger = logging.getLogger(__name__)


async def _verify_group_access(chat_id: int, user: dict):
    """Verify the user has access to this group via their bot (direct or clone_bot_groups).
    
    For clone bots: The clone owner has access to all groups where their bot is active.
    Third parties who added the bot to their groups do NOT get Mini App access.
    """
    bot_token = user.get("validated_bot_token")
    if not bot_token:
        return  # Primary bot owner, allow access
    
    # Check if user is the clone owner
    is_clone_owner = user.get("role") == "owner" and user.get("validated_bot_id") is not None
    
    token_hash = hash_token(bot_token)
    async with db.pool.acquire() as conn:
        if is_clone_owner:
            # Clone owner: check if this is ANY active group for their bot
            row = await conn.fetchrow(
                """
                SELECT 1 FROM clone_bot_groups cbg
                JOIN bots b ON b.bot_id = cbg.bot_id
                WHERE cbg.chat_id = $1 
                  AND b.token_hash = $2 
                  AND cbg.is_active = TRUE
                """,
                chat_id,
                token_hash,
            )
        else:
            # Regular user (including third parties who added clone): 
            # Check direct ownership via bot_token_hash only
            row = await conn.fetchrow(
                """
                SELECT 1 FROM groups g
                WHERE g.chat_id = $1 AND g.bot_token_hash = $2
                """,
                chat_id,
                token_hash,
            )
    if not row:
        raise HTTPException(status_code=403, detail="Not authorized for this group")


@router.get("")
async def list_groups(user: dict = Depends(get_current_user)):
    bot_token = user.get("validated_bot_token")
    if not bot_token:
        # Fallback to all groups if no bot context (unlikely with get_current_user)
        return await get_user_managed_groups(user["id"])

    token_hash = hash_token(bot_token)

    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT g.chat_id, g.title, g.member_count, g.settings,
                   g.photo_big, g.photo_small, g.bot_token_hash
            FROM groups g
            WHERE g.bot_token_hash = $1
            UNION
            SELECT g.chat_id, g.title, g.member_count, g.settings,
                   g.photo_big, g.photo_small, g.bot_token_hash
            FROM groups g
            JOIN clone_bot_groups cbg ON g.chat_id = cbg.chat_id
            JOIN bots b ON b.bot_id = cbg.bot_id
            WHERE b.token_hash = $1
            ORDER BY title
            """,
            token_hash,
        )
        res = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("settings"), str):
                try:
                    d["settings"] = json.loads(d["settings"])
                except Exception:
                    d["settings"] = {}
            elif not d.get("settings"):
                d["settings"] = {}
            res.append(d)
        return res


@router.get("/{chat_id}")
async def group_details(chat_id: int, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    group = await get_group(chat_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Try to fetch live member count from Telegram
    try:
        from bot.registry import get_all

        bot_instances = get_all()
        for bid, app_instance in bot_instances.items():
            try:
                live_count = await app_instance.bot.get_chat_member_count(chat_id)
                if live_count:
                    group["member_count"] = live_count
                    # Persist it so future DB reads are correct too
                    async with db.pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE groups SET member_count=$1 WHERE chat_id=$2",
                            live_count,
                            chat_id,
                        )
                    break
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"[groups] Could not refresh member count: {e}")

    return group


@router.get("/{chat_id}/settings")
async def get_settings(chat_id: int, user=Depends(get_current_user)):
    from db.ops.automod import get_group_settings

    bot_token = user.get("validated_bot_token")
    token_hash = hash_token(bot_token) if bot_token else None
    
    s = await get_group_settings(db.pool, chat_id, token_hash)
    return {"status": "ok", "settings": s}


_LOCK_KEY_TO_SHORT = {
    "lock_photo": "photo",
    "lock_video": "video",
    "lock_sticker": "sticker",
    "lock_gif": "gif",
    "lock_voice": "voice",
    "lock_audio": "audio",
    "lock_document": "document",
    "lock_link": "link",
    "lock_forward": "forward",
    "lock_poll": "poll",
    "lock_contact": "contact",
    "lock_username": "username",
    "lock_bot": "bot",
    "lock_bot_inviter": "bot_inviter",
    "lock_website": "website",
    "lock_channel": "forward_channel",
    "lock_hashtag": "hashtag",
    "lock_unofficial_tg": "unofficial_tg",
    "lock_userbots": "userbots",
    "lock_text": "text",
    "lock_no_caption": "no_caption",
    "lock_emoji": "emoji",
    "lock_emoji_only": "emoji_only",
    "lock_porn": "porn",
    "lock_spoiler": "spoiler",
}


def _normalize_settings(incoming: dict, existing: dict):
    if "locks" not in existing:
        existing["locks"] = {}
    for k in list(incoming.keys()):
        if k.startswith("lock_"):
            short = _LOCK_KEY_TO_SHORT.get(k, k[5:])
            existing["locks"][short] = incoming[k]
    incoming["locks"] = existing["locks"]

    if "automod" not in existing:
        existing["automod"] = {}
    if "antiflood" in incoming:
        if "antiflood" not in existing["automod"]:
            existing["automod"]["antiflood"] = {}
        existing["automod"]["antiflood"]["enabled"] = incoming["antiflood"]
        if "antiflood_limit" in incoming:
            existing["automod"]["antiflood"]["flood_threshold"] = incoming["antiflood_limit"]
        if "antiflood_window" in incoming:
            existing["automod"]["antiflood"]["flood_window_sec"] = incoming["antiflood_window"]
    if "antilink" in incoming:
        if "antilink" not in existing["automod"]:
            existing["automod"]["antilink"] = {}
        existing["automod"]["antilink"]["enabled"] = incoming["antilink"]
    incoming["automod"] = existing["automod"]


@router.put("/{chat_id}/settings")
async def update_settings(chat_id: int, settings: dict, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    from db.ops.automod import bulk_update_group_settings, get_group_settings

    bot_token = user.get("validated_bot_token")
    token_hash = hash_token(bot_token) if bot_token else None
    
    # Get existing merged settings
    existing_full = await get_group_settings(db.pool, chat_id, token_hash)
    
    # Extract only settings-related keys (not group metadata like title, member_count, etc.)
    settings_keys = {
        # All individual columns from groups table that are settings
        "antiraid_enabled", "antiraid_mode", "antiraid_threshold", "antiraid_duration_mins",
        "auto_antiraid_enabled", "auto_antiraid_threshold",
        "captcha_enabled", "captcha_mode", "captcha_timeout_mins", "captcha_kick_on_timeout",
        "self_destruct_enabled", "self_destruct_minutes", "lock_admins",
        "unofficial_tg_lock", "bot_inviter_ban",
        "duplicate_limit", "duplicate_window_mins",
        "min_words", "max_words", "min_lines", "max_lines", "min_chars", "max_chars",
        "necessary_words_active", "regex_active",
        "group_password", "password_kick_on_fail", "password_attempts", "password_timeout_mins",
        "log_channel_id", "log_include_preview", "log_include_userid", "inline_mode_enabled",
        # Announcement Channel settings
        "announcement_channel_id", "announcement_notifications", "announcement_auto_pin",
        "announcement_auto_delete_mins", "announcement_restrict_replies",
        # Media locks
        "lock_photo", "lock_video", "lock_sticker", "lock_gif", "lock_voice", "lock_audio", "lock_document",
        # Communication locks
        "lock_link", "lock_forward", "lock_poll", "lock_contact",
        # Additional content locks
        "lock_username", "lock_bot", "lock_bot_inviter", "lock_website", "lock_channel",
        # Content filters
        "lock_porn", "lock_hashtag", "lock_unofficial_tg", "lock_userbots",
        # Anti-flood
        "antiflood", "antiflood_limit", "antiflood_window", "antiflood_action",
        # Anti-spam
        "antispam",
        # Nested settings
        "locks", "automod", "warnings", "welcome", "goodbye", "rules",
        "modules", "_modules", "timed_locks",
    }
    existing = {k: v for k, v in existing_full.items() if k in settings_keys}
    
    incoming = settings.copy()
    _normalize_settings(incoming, existing)
    
    if token_hash:
        import json as _json
        existing.update(incoming)
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO bot_group_settings (bot_token_hash, chat_id, settings, updated_at)
                   VALUES ($1, $2, $3::jsonb, NOW())
                   ON CONFLICT (bot_token_hash, chat_id) DO UPDATE
                   SET settings = $3::jsonb, updated_at = NOW()""",
                token_hash,
                chat_id,
                _json.dumps(existing),
            )
    else:
        await bulk_update_group_settings(db.pool, chat_id, incoming)

    # Sync any flat lock_* keys to the locks table
    LOCK_KEY_MAP = {
        "lock_photo": "photo",
        "lock_video": "video",
        "lock_sticker": "sticker",
        "lock_gif": "gif",
        "lock_voice": "voice",
        "lock_audio": "audio",
        "lock_document": "document",
        "lock_link": "link",
        "lock_forward": "forward",
        "lock_poll": "poll",
        "lock_contact": "contact",
    }
    lock_updates = {
        LOCK_KEY_MAP[k]: v for k, v in incoming.items() if k in LOCK_KEY_MAP and isinstance(v, bool)
    }
    if lock_updates:
        try:
            cols = ", ".join(lock_updates.keys())
            placeholders = ", ".join([f"${i+2}" for i in range(len(lock_updates))])
            updates = ", ".join([f"{k}=EXCLUDED.{k}" for k in lock_updates.keys()])
            async with db.pool.acquire() as conn:
                await conn.execute(
                    f"INSERT INTO locks (chat_id, {cols}) VALUES ($1, {placeholders})"
                    f" ON CONFLICT (chat_id) DO UPDATE SET {updates}",
                    chat_id,
                    *lock_updates.values(),
                )
        except Exception as e:
            logger.warning(f"Lock sync failed: {e}")

    return {"status": "ok"}


@router.put("/{chat_id}/settings/bulk")
async def bulk_update_settings(
    chat_id: int, request: Request, user: dict = Depends(get_current_user)
):
    """Bulk update multiple settings at once (for templates)."""
    body = await request.json()
    settings = body.get("settings", {})

    from db.ops.automod import bulk_update_group_settings, get_group_settings

    bot_token = user.get("validated_bot_token")
    token_hash = hash_token(bot_token) if bot_token else None
    
    # Get existing merged settings
    existing_full = await get_group_settings(db.pool, chat_id, token_hash)
    
    # Extract only settings-related keys (not group metadata like title, member_count, etc.)
    settings_keys = {
        # All individual columns from groups table that are settings
        "antiraid_enabled", "antiraid_mode", "antiraid_threshold", "antiraid_duration_mins",
        "auto_antiraid_enabled", "auto_antiraid_threshold",
        "captcha_enabled", "captcha_mode", "captcha_timeout_mins", "captcha_kick_on_timeout",
        "self_destruct_enabled", "self_destruct_minutes", "lock_admins",
        "unofficial_tg_lock", "bot_inviter_ban",
        "duplicate_limit", "duplicate_window_mins",
        "min_words", "max_words", "min_lines", "max_lines", "min_chars", "max_chars",
        "necessary_words_active", "regex_active",
        "group_password", "password_kick_on_fail", "password_attempts", "password_timeout_mins",
        "log_channel_id", "log_include_preview", "log_include_userid", "inline_mode_enabled",
        # Announcement Channel settings
        "announcement_channel_id", "announcement_notifications", "announcement_auto_pin",
        "announcement_auto_delete_mins", "announcement_restrict_replies",
        # Media locks
        "lock_photo", "lock_video", "lock_sticker", "lock_gif", "lock_voice", "lock_audio", "lock_document",
        # Communication locks
        "lock_link", "lock_forward", "lock_poll", "lock_contact",
        # Additional content locks
        "lock_username", "lock_bot", "lock_bot_inviter", "lock_website", "lock_channel",
        # Content filters
        "lock_porn", "lock_hashtag", "lock_unofficial_tg", "lock_userbots",
        # Anti-flood
        "antiflood", "antiflood_limit", "antiflood_window", "antiflood_action",
        # Anti-spam
        "antispam",
        # Nested settings
        "locks", "automod", "warnings", "welcome", "goodbye", "rules",
        "modules", "_modules", "timed_locks",
    }
    existing = {k: v for k, v in existing_full.items() if k in settings_keys}
    
    incoming = settings.copy()
    _normalize_settings(incoming, existing)

    if token_hash:
        import json as _json
        existing.update(incoming)
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO bot_group_settings (bot_token_hash, chat_id, settings, updated_at)
                   VALUES ($1, $2, $3::jsonb, NOW())
                   ON CONFLICT (bot_token_hash, chat_id) DO UPDATE
                   SET settings = $3::jsonb, updated_at = NOW()""",
                token_hash,
                chat_id,
                _json.dumps(existing),
            )
    else:
        await bulk_update_group_settings(db.pool, chat_id, incoming)

    # Sync any flat lock_* keys to the locks table
    LOCK_KEY_MAP = {
        "lock_photo": "photo",
        "lock_video": "video",
        "lock_sticker": "sticker",
        "lock_gif": "gif",
        "lock_voice": "voice",
        "lock_audio": "audio",
        "lock_document": "document",
        "lock_link": "link",
        "lock_forward": "forward",
        "lock_poll": "poll",
        "lock_contact": "contact",
    }
    lock_updates = {
        LOCK_KEY_MAP[k]: v for k, v in incoming.items() if k in LOCK_KEY_MAP and isinstance(v, bool)
    }
    if lock_updates:
        try:
            cols = ", ".join(lock_updates.keys())
            placeholders = ", ".join([f"${i+2}" for i in range(len(lock_updates))])
            updates = ", ".join([f"{k}=EXCLUDED.{k}" for k in lock_updates.keys()])
            async with db.pool.acquire() as conn:
                await conn.execute(
                    f"INSERT INTO locks (chat_id, {cols}) VALUES ($1, {placeholders})"
                    f" ON CONFLICT (chat_id) DO UPDATE SET {updates}",
                    chat_id,
                    *lock_updates.values(),
                )
        except Exception as e:
            logger.warning(f"Lock sync failed: {e}")

    # Publish SSE event
    from api.routes.events import EventBus

    await EventBus.publish(chat_id, "settings_change", {"settings": incoming})

    return {"status": "ok"}


@router.get("/{chat_id}/logs")
async def group_logs(chat_id: int, limit: int = 50, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    logs = await get_recent_logs(chat_id)
    if isinstance(logs, list):
        return logs[:limit]
    elif isinstance(logs, dict) and "logs" in logs:
        return logs["logs"][:limit]
    return []


@router.post("/{chat_id}/copy-settings")
async def copy_settings_to_groups(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    """Copy settings from source group to target groups."""
    await _verify_group_access(chat_id, user)
    target_chat_ids = body.get("target_chat_ids", [])
    modules = body.get("modules", [])
    if not target_chat_ids:
        raise HTTPException(status_code=400, detail="No target groups specified")

    source = await get_group(chat_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source group not found")

    source_settings = source.get("settings") or {}
    results = []
    for target_id in target_chat_ids:
        try:
            target = await get_group(int(target_id))
            if not target:
                results.append({"chat_id": target_id, "ok": False, "error": "Group not found"})
                continue
            target_settings = target.get("settings") or {}
            if not modules or "automod" in modules:
                automod_keys = [
                    "antiflood",
                    "antispam",
                    "lock_link",
                    "captcha_enabled",
                    "warn_max",
                    "warn_action",
                ]
                for k in automod_keys:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            if not modules or "welcome" in modules:
                for k in ["welcome_enabled", "goodbye_enabled"]:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            if not modules or "modules" in modules:
                for k in ["xp_enabled", "games_enabled", "reports_enabled", "notes_enabled"]:
                    if k in source_settings:
                        target_settings[k] = source_settings[k]
            await update_group_settings(int(target_id), target_settings)
            results.append({"chat_id": target_id, "ok": True})
        except Exception as e:
            results.append({"chat_id": target_id, "ok": False, "error": str(e)})

    return {"ok": True, "results": results}


@router.post("/{chat_id}/actions/slowmode")
async def set_slowmode(chat_id: int, body: dict, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    seconds = max(0, min(3600, int(body.get("seconds", 0))))
    from bot.registry import get_all

    for bid, app_instance in get_all().items():
        try:
            await app_instance.bot.set_chat_slow_mode_delay(chat_id, seconds)
            break
        except Exception:
            continue
    return {"ok": True, "seconds": seconds}


@router.delete("/{chat_id}/settings/reset")
async def reset_settings(chat_id: int, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    
    bot_token = user.get("validated_bot_token")
    token_hash = hash_token(bot_token) if bot_token else None
    
    async with db.pool.acquire() as conn:
        # Reset groups table settings
        await conn.execute("UPDATE groups SET settings='{}'::jsonb WHERE chat_id=$1", chat_id)
        # Also reset bot_group_settings overrides if this is a clone bot context
        if token_hash:
            await conn.execute(
                "DELETE FROM bot_group_settings WHERE chat_id=$1 AND bot_token_hash=$2",
                chat_id, token_hash
            )
        else:
            # For main bot, delete all bot_group_settings for this chat_id
            await conn.execute("DELETE FROM bot_group_settings WHERE chat_id=$1", chat_id)
    
    # Publish SSE event so all pages re-fetch settings
    from api.routes.events import EventBus
    await EventBus.publish(chat_id, "settings_change", {"settings": {}, "reset": True})
    
    return {"ok": True}


@router.post("/{chat_id}/personality")
async def update_group_personality_api(
    chat_id: int, body: dict, user: dict = Depends(get_current_user)
):
    """Update bot personality settings for a group (handles multiple frontend variants)."""
    await _verify_group_access(chat_id, user)
    
    # Verify bot context - clone owners can only modify their own bot's personality
    bot_token = user.get("validated_bot_token")
    if bot_token:
        token_hash = hash_token(bot_token)
        # Check if this user owns the bot being used
        is_clone_owner = user.get("role") == "owner" and user.get("validated_bot_id") is not None
        if is_clone_owner:
            # Clone owners can only modify settings for groups where their bot is active
            async with db.pool.acquire() as conn:
                access_row = await conn.fetchrow(
                    """
                    SELECT 1 FROM clone_bot_groups cbg
                    JOIN bots b ON b.bot_id = cbg.bot_id
                    WHERE cbg.chat_id = $1 AND b.token_hash = $2 AND cbg.is_active = TRUE
                    """,
                    chat_id, token_hash
                )
                if not access_row:
                    raise HTTPException(status_code=403, detail="Not authorized for this group")
    
    # Extract values from various possible frontend key formats
    tone = body.get("tone") or body.get("botTone") or body.get("persona_tone")
    name = body.get("name") or body.get("botName") or body.get("persona_name")
    lang = body.get("language") or body.get("language_code") or body.get("persona_language")
    
    # Emoji can be boolean or string style
    emoji = body.get("emoji")
    if emoji is None:
        emoji = body.get("emojiStyle")
    if isinstance(emoji, str):
        emoji = emoji.lower() not in ("none", "false", "0")

    updates = []
    values = []
    
    if tone:
        updates.append("persona_tone = $" + str(len(values) + 1))
        values.append(tone)
    if name:
        updates.append("persona_name = $" + str(len(values) + 1))
        values.append(name)
    if lang:
        updates.append("persona_language = $" + str(len(values) + 1))
        values.append(lang)
    if emoji is not None:
        updates.append("persona_emoji = $" + str(len(values) + 1))
        values.append(bool(emoji))

    # Also handle custom greeting/welcome if present in body
    welcome_msg = body.get("welcomeMessage") or body.get("custom_welcome")
    if welcome_msg is not None:
        updates.append("welcome_text = $" + str(len(values) + 1))
        values.append(welcome_msg)

    if not updates:
        raise HTTPException(status_code=400, detail="No valid personality fields provided")

    values.append(chat_id)
    async with db.pool.acquire() as conn:
        await conn.execute(
            f"UPDATE groups SET {', '.join(updates)} WHERE chat_id = ${len(values)}",
            *values
        )
    
    return {"ok": True}


@router.post("/{chat_id}/actions/leave")
async def leave_group(chat_id: int, user: dict = Depends(get_current_user)):
    await _verify_group_access(chat_id, user)
    from bot.registry import get_all

    for bid, app_instance in get_all().items():
        try:
            await app_instance.bot.leave_chat(chat_id)
            break
        except Exception:
            continue
    return {"ok": True}
