"""
db/ops/automod.py

All database operations for advanced automod features.
"""

# ── Rule Time Windows ───────────────────────────────────────────────────────


async def get_rule_time_windows(pool, chat_id: int) -> dict:
    """Get all time windows as dict {rule_key: {start, end, is_active}}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT rule_key, start_time, end_time, is_active "
            "FROM rule_time_windows WHERE chat_id=$1",
            chat_id,
        )
    return {row["rule_key"]: dict(row) for row in rows}


async def set_rule_time_window(pool, chat_id: int, rule_key: str, start_time: str, end_time: str):
    """Set or update time window for a rule."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rule_time_windows (chat_id, rule_key, start_time, end_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id, rule_key)
            DO UPDATE SET start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        is_active = TRUE
            """,
            chat_id,
            rule_key,
            start_time,
            end_time,
        )


async def remove_rule_time_window(pool, chat_id: int, rule_key: str):
    """Remove time window for a rule."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM rule_time_windows WHERE chat_id=$1 AND rule_key=$2", chat_id, rule_key
        )


# ── Rule Penalties ───────────────────────────────────────────────────────


async def get_rule_penalties(pool, chat_id: int) -> dict:
    """Get all penalties as dict {rule_key: {penalty, duration_hours}}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT rule_key, penalty, duration_hours " "FROM rule_penalties WHERE chat_id=$1",
            chat_id,
        )
    return {row["rule_key"]: dict(row) for row in rows}


async def set_rule_penalty(
    pool, chat_id: int, rule_key: str, penalty: str, duration_hours: int = 0
):
    """Set or update penalty for a rule."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rule_penalties (chat_id, rule_key, penalty, duration_hours)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id, rule_key)
            DO UPDATE SET penalty = EXCLUDED.penalty,
                        duration_hours = EXCLUDED.duration_hours
            """,
            chat_id,
            rule_key,
            penalty,
            duration_hours,
        )


async def remove_rule_penalty(pool, chat_id: int, rule_key: str):
    """Remove custom penalty for a rule (fall back to default)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM rule_penalties WHERE chat_id=$1 AND rule_key=$2", chat_id, rule_key
        )


# ── Silent Times ──────────────────────────────────────────────────────────


async def get_silent_times(pool, chat_id: int) -> list:
    """Get all silent time slots for a chat."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT slot, start_time, end_time, is_active, start_text, end_text "
            "FROM silent_times WHERE chat_id=$1 ORDER BY slot",
            chat_id,
        )
    return [dict(row) for row in rows]


async def upsert_silent_time(
    pool,
    chat_id: int,
    slot: int,
    start_time: str,
    end_time: str,
    is_active: bool = True,
    start_text: str = "",
    end_text: str = "",
):
    """Set or update a silent time slot."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO silent_times
                (chat_id, slot, start_time, end_time, is_active, start_text, end_text)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id, slot)
            DO UPDATE SET start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        is_active = EXCLUDED.is_active,
                        start_text = EXCLUDED.start_text,
                        end_text = EXCLUDED.end_text
            """,
            chat_id,
            slot,
            start_time,
            end_time,
            is_active,
            start_text,
            end_text,
        )


async def disable_silent_time(pool, chat_id: int, slot: int):
    """Disable a specific silent time slot."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE silent_times SET is_active=FALSE WHERE chat_id=$1 AND slot=$2", chat_id, slot
        )


async def clear_all_silent_times(pool, chat_id: int):
    """Delete all silent time slots for a chat."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM silent_times WHERE chat_id=$1", chat_id)


# ── Message Hashes (Duplicate Detection) ─────────────────────────────


async def record_message_hash(pool, chat_id: int, msg_hash: str, user_id: int):
    """Record a message hash for duplicate detection."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO message_hashes (chat_id, msg_hash, user_id) " "VALUES ($1, $2, $3)",
            chat_id,
            msg_hash,
            user_id,
        )


async def get_recent_hash_count(pool, chat_id: int, msg_hash: str, window_mins: int) -> int:
    """Count how many times this hash appeared in the time window."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) FROM message_hashes
            WHERE chat_id=$1 AND msg_hash=$2
            AND sent_at > NOW() - INTERVAL '1 minute' * $3
            """,
            chat_id,
            msg_hash,
            window_mins,
        )
    return row["count"] if row else 0


async def cleanup_old_hashes(pool, days: int = 7):
    """Clean up old message hashes (run periodically)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM message_hashes WHERE sent_at < NOW() - INTERVAL '1 day' * $1", days
        )


# ── REGEX Patterns ────────────────────────────────────────────────────────


async def get_regex_patterns(pool, chat_id: int) -> list:
    """Get all REGEX patterns for a chat."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, pattern, penalty, is_active "
            "FROM regex_patterns WHERE chat_id=$1 ORDER BY created_at",
            chat_id,
        )
    return [dict(row) for row in rows]


async def add_regex_pattern(pool, chat_id: int, pattern: str, penalty: str = "delete"):
    """Add a REGEX pattern."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO regex_patterns (chat_id, pattern, penalty) " "VALUES ($1, $2, $3)",
            chat_id,
            pattern,
            penalty,
        )


async def remove_regex_pattern(pool, chat_id: int, pattern: str):
    """Remove a REGEX pattern by pattern string."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM regex_patterns WHERE chat_id=$1 AND pattern=$2", chat_id, pattern
        )


async def toggle_regex_pattern(pool, chat_id: int, pattern: str, is_active: bool):
    """Enable/disable a REGEX pattern."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE regex_patterns SET is_active=$1 " "WHERE chat_id=$2 AND pattern=$3",
            is_active,
            chat_id,
            pattern,
        )


# ── Necessary Words ────────────────────────────────────────────────────────


async def get_necessary_words(pool, chat_id: int) -> list:
    """Get list of necessary words for a chat."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT word FROM necessary_words " "WHERE chat_id=$1 AND is_active=TRUE ORDER BY word",
            chat_id,
        )
    return [row["word"] for row in rows]


async def add_necessary_word(pool, chat_id: int, word: str):
    """Add a necessary word."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO necessary_words (chat_id, word)
            VALUES ($1, $2)
            ON CONFLICT (chat_id, word)
            DO UPDATE SET is_active=TRUE
            """,
            chat_id,
            word,
        )


async def remove_necessary_word(pool, chat_id: int, word: str):
    """Remove a necessary word."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM necessary_words WHERE chat_id=$1 AND word=$2", chat_id, word
        )


async def clear_necessary_words(pool, chat_id: int):
    """Clear all necessary words for a chat."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM necessary_words WHERE chat_id=$1", chat_id)


# ── Rule Priority ────────────────────────────────────────────────────────


async def get_rule_priority(pool, chat_id: int) -> list:
    """Get rule evaluation order as list."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT rule_order FROM rule_priority WHERE chat_id=$1", chat_id)
    return row["rule_order"] if row else []


async def save_rule_priority(pool, chat_id: int, rule_order: list):
    """Save rule evaluation order."""
    import json

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rule_priority (chat_id, rule_order)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (chat_id)
            DO UPDATE SET rule_order = EXCLUDED.rule_order, updated_at = NOW()
            """,
            chat_id,
            json.dumps(rule_order),
        )


# ── Group Settings Helpers ───────────────────────────────────────────────


async def update_group_setting(pool, chat_id: int, key: str, value):
    """Update a single setting (either a column in 'groups' or a key in 'settings' JSONB)."""
    import json

    # List of known individual columns in 'groups' table
    INDIVIDUAL_COLUMNS = {
        "antiraid_enabled",
        "antiraid_mode",
        "antiraid_threshold",
        "antiraid_duration_mins",
        "auto_antiraid_enabled",
        "auto_antiraid_threshold",
        "captcha_enabled",
        "captcha_mode",
        "captcha_timeout_mins",
        "captcha_kick_on_timeout",
        "self_destruct_enabled",
        "self_destruct_minutes",
        "lock_admins",
        "unofficial_tg_lock",
        "bot_inviter_ban",
        "duplicate_limit",
        "duplicate_window_mins",
        "min_words",
        "max_words",
        "min_lines",
        "max_lines",
        "min_chars",
        "max_chars",
        "necessary_words_active",
        "regex_active",
        "group_password",
        "password_kick_on_fail",
        "password_attempts",
        "password_timeout_mins",
        "log_channel_id",
        "log_include_preview",
        "log_include_userid",
        "inline_mode_enabled",
        # Media locks
        "lock_photo",
        "lock_video",
        "lock_sticker",
        "lock_gif",
        "lock_voice",
        "lock_audio",
        "lock_document",
        # Communication locks
        "lock_link",
        "lock_forward",
        "lock_poll",
        "lock_contact",
        # Additional content locks
        "lock_username",
        "lock_bot",
        "lock_bot_inviter",
        "lock_website",
        "lock_channel",
        # Content filters
        "lock_porn",
        "lock_hashtag",
        "lock_unofficial_tg",
        "lock_userbots",
        # Anti-flood
        "antiflood",
        "antiflood_limit",
        "antiflood_window",
        "antiflood_action",
        # Anti-spam
        "antispam",
    }

    async with pool.acquire() as conn:
        if key in INDIVIDUAL_COLUMNS:
            await conn.execute(f"UPDATE groups SET {key} = $1 WHERE chat_id=$2", value, chat_id)
            return

        # Fallback to settings JSONB
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        if not row:
            settings = {}
        else:
            settings = row["settings"]
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            elif settings is None:
                settings = {}
            else:
                settings = dict(settings)

        # Update nested key
        if "." in key:
            parts = key.split(".")
            d = settings
            for p in parts[:-1]:
                if p not in d:
                    d[p] = {}
                d = d[p]
            d[parts[-1]] = value
        else:
            settings[key] = value

        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id=$2", json.dumps(settings), chat_id
        )


async def bulk_update_group_settings(pool, chat_id: int, settings: dict):
    """Bulk update multiple settings, handling both columns and JSONB."""
    import json

    # List of known individual columns in 'groups' table
    INDIVIDUAL_COLUMNS = {
        "antiraid_enabled",
        "antiraid_mode",
        "antiraid_threshold",
        "antiraid_duration_mins",
        "auto_antiraid_enabled",
        "auto_antiraid_threshold",
        "captcha_enabled",
        "captcha_mode",
        "captcha_timeout_mins",
        "captcha_kick_on_timeout",
        "self_destruct_enabled",
        "self_destruct_minutes",
        "lock_admins",
        "unofficial_tg_lock",
        "bot_inviter_ban",
        "duplicate_limit",
        "duplicate_window_mins",
        "min_words",
        "max_words",
        "min_lines",
        "max_lines",
        "min_chars",
        "max_chars",
        "necessary_words_active",
        "regex_active",
        "group_password",
        "password_kick_on_fail",
        "password_attempts",
        "password_timeout_mins",
        "log_channel_id",
        "log_include_preview",
        "log_include_userid",
        "inline_mode_enabled",
        # Media locks
        "lock_photo",
        "lock_video",
        "lock_sticker",
        "lock_gif",
        "lock_voice",
        "lock_audio",
        "lock_document",
        # Communication locks
        "lock_link",
        "lock_forward",
        "lock_poll",
        "lock_contact",
        # Additional content locks
        "lock_username",
        "lock_bot",
        "lock_bot_inviter",
        "lock_website",
        "lock_channel",
        # Content filters
        "lock_porn",
        "lock_hashtag",
        "lock_unofficial_tg",
        "lock_userbots",
        # Anti-flood
        "antiflood",
        "antiflood_limit",
        "antiflood_window",
        "antiflood_action",
        # Anti-spam
        "antispam",
    }

    column_updates = {}
    jsonb_updates = {}

    for k, v in settings.items():
        if k in INDIVIDUAL_COLUMNS:
            column_updates[k] = v
        else:
            jsonb_updates[k] = v

    async with pool.acquire() as conn:
        # Update columns
        if column_updates:
            set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(column_updates.keys())])
            await conn.execute(
                f"UPDATE groups SET {set_clause} WHERE chat_id = $1",
                chat_id,
                *column_updates.values(),
            )

        # Update JSONB
        if jsonb_updates:
            row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
            current = {}
            if row and row["settings"]:
                if isinstance(row["settings"], str):
                    try:
                        current = json.loads(row["settings"])
                    except Exception:
                        current = {}
                else:
                    current = dict(row["settings"])

            # Merge
            def deep_merge(base, new):
                result = dict(base) if base else {}
                for k, v in new.items():
                    if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                        result[k] = deep_merge(result[k], v)
                    else:
                        result[k] = v
                return result

            current = deep_merge(current, jsonb_updates)
            await conn.execute(
                "UPDATE groups SET settings = $1::jsonb WHERE chat_id=$2",
                json.dumps(current),
                chat_id,
            )


# ── Timed Locks ──────────────────────────────────────────────────────────


async def set_timed_lock(pool, chat_id: int, rule_key: str, start_time: str, end_time: str):
    """Set a timed lock in the timed_locks JSONB."""
    import json

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        if not row or not row["settings"]:
            settings = {}
        elif isinstance(row["settings"], str):
            try:
                settings = json.loads(row["settings"])
            except Exception:
                settings = {}
        else:
            settings = dict(row["settings"]) or {}

        timed_locks = settings.get("timed_locks", {})
        timed_locks[rule_key] = {"start": start_time, "end": end_time}
        settings["timed_locks"] = timed_locks

        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id=$2", json.dumps(settings), chat_id
        )


async def remove_timed_lock(pool, chat_id: int, rule_key: str):
    """Remove a timed lock."""
    import json

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT settings FROM groups WHERE chat_id=$1", chat_id)
        if not row or not row["settings"]:
            return

        if isinstance(row["settings"], str):
            try:
                settings = json.loads(row["settings"])
            except Exception:
                return
        else:
            settings = dict(row["settings"]) or {}

        timed_locks = settings.get("timed_locks", {})
        if rule_key in timed_locks:
            del timed_locks[rule_key]
            settings["timed_locks"] = timed_locks

        await conn.execute(
            "UPDATE groups SET settings = $1::jsonb WHERE chat_id=$2", json.dumps(settings), chat_id
        )


# ── Whitelist ────────────────────────────────────────────────────────────


async def get_whitelist(pool, chat_id: int) -> list:
    """Get whitelist of user IDs exempt from automod (settings + approved_members)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT (
                COALESCE(settings->'automod'->'whitelist', '[]'::jsonb) || 
                COALESCE((SELECT jsonb_agg(user_id) FROM approved_members WHERE chat_id=$1), '[]'::jsonb)
            ) as full_whitelist
            FROM groups WHERE chat_id=$1
            """,
            chat_id,
        )
        if row and row["full_whitelist"]:
            import json

            # JSONB might come back as a list already with asyncpg
            val = row["full_whitelist"]
            if isinstance(val, str):
                return list(set(json.loads(val)))
            return list(set(val))
    return []


# ── Warning Tracking ─────────────────────────────────────────────────────


async def get_user_warning_count(pool, chat_id: int, user_id: int) -> int:
    """Count user's active warnings."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) FROM warnings
            WHERE chat_id=$1 AND user_id=$2
            AND is_active = TRUE
            AND issued_at > NOW() - INTERVAL '7 days'
            """,
            chat_id,
            user_id,
        )
    return row["count"] if row else 0


async def get_group_settings(pool, chat_id: int, bot_token_hash: str = None) -> dict:
    """Get full settings dict for a group (merges settings JSONB with individual columns).
    If bot_token_hash is provided, it will also merge overrides from bot_group_settings.
    """
    import json

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM groups WHERE chat_id=$1", chat_id)
        
        bot_settings_json = {}
        if bot_token_hash:
            bot_row = await conn.fetchrow(
                "SELECT settings FROM bot_group_settings WHERE bot_token_hash=$1 AND chat_id=$2",
                bot_token_hash,
                chat_id,
            )
            if bot_row and bot_row["settings"]:
                bot_settings_json = bot_row["settings"]
                if isinstance(bot_settings_json, str):
                    try:
                        bot_settings_json = json.loads(bot_settings_json)
                    except Exception:
                        bot_settings_json = {}

    if not row:
        return bot_settings_json if bot_token_hash else {}

    res = dict(row)
    settings_json = res.pop("settings", {})
    if isinstance(settings_json, str):
        try:
            settings_json = json.loads(settings_json)
        except Exception:
            settings_json = {}

    # Also get modules
    modules_json = res.pop("modules", None)
    if isinstance(modules_json, str):
        try:
            modules_json = json.loads(modules_json)
        except Exception:
            modules_json = {}
    if modules_json is None:
        modules_json = {}

    # Merge settings_json into the main dict
    if settings_json:
        res.update(settings_json)

    # Merge bot-specific overrides if provided
    if bot_settings_json:
        # Deep merge bot_settings_json into res
        def deep_merge(base, new):
            for k, v in new.items():
                if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                    deep_merge(base[k], v)
                else:
                    base[k] = v
            return base
            
        deep_merge(res, bot_settings_json)

    # Add modules under _modules key for checking in handlers
    res["_modules"] = modules_json
    res["modules"] = modules_json

    # FIX A: Build the "locks" sub-dict from flat lock_* columns
    # The automod engine reads settings.get("locks", {}) and iterates its keys
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
        "lock_username": "username",
        "lock_bot": "bot",
        "lock_website": "website",
        "lock_channel": "forward_channel",
        "lock_hashtag": "hashtag",
        "lock_unofficial_tg": "unofficial_tg",
        "lock_userbots": "userbots",
        "lock_text": "text",
        "lock_no_caption": "no_caption",
        "lock_emoji": "emoji",
        "lock_emoji_only": "emoji_only",
        "lock_english": "english",
        "lock_arabic_farsi": "arabic_farsi",
        "lock_reply": "reply",
        "lock_external_reply": "external_reply",
        "lock_spoiler": "spoiler",
        "lock_slash": "slash",
    }
    res["locks"] = {
        short: bool(res.get(flat))
        for flat, short in LOCK_KEY_MAP.items()
    }

    return res
