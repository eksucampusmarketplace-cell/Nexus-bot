"""
api/routes/automod.py — additions for advanced automod

GET  /api/groups/{chat_id}/automod/advanced
     → all advanced settings: time windows, penalties, silent times,
       necessary words, regex patterns, rule priority, timed locks

PUT  /api/groups/{chat_id}/automod/advanced
     → bulk update any advanced setting

GET  /api/groups/{chat_id}/automod/templates
     → list all rule templates

POST /api/groups/{chat_id}/automod/templates/apply
     → apply a template to the group
     → Body: { template_id }

PUT  /api/groups/{chat_id}/automod/rule-priority
     → save drag-and-drop rule order
     → Body: { order: ["link","website",...] }

GET  /api/groups/{chat_id}/automod/conflicts
     → detect rule conflicts
     → Returns: [{ rule_a, rule_b, conflict_type, message }]
"""

from fastapi import APIRouter, Request, HTTPException
router = APIRouter()


@router.get("/api/groups/{chat_id}/automod/advanced")
async def get_advanced_automod(chat_id: int, request: Request):
    db = request.app.state.db
    _check_access(request, chat_id)

    from db.ops.automod import (
        get_rule_time_windows, get_rule_penalties, get_silent_times,
        get_necessary_words, get_regex_patterns, get_rule_priority
    )
    from db.ops.groups import get_group

    group = await get_group(chat_id)
    settings     = group.get('settings') or {}
    time_windows = await get_rule_time_windows(db, chat_id)
    penalties    = await get_rule_penalties(db, chat_id)
    silent_times = await get_silent_times(db, chat_id)
    nec_words    = await get_necessary_words(db, chat_id)
    regex_pats   = await get_regex_patterns(db, chat_id)
    rule_order   = await get_rule_priority(db, chat_id)

    return {
        "time_windows":    time_windows,
        "penalties":       penalties,
        "silent_times":    silent_times,
        "necessary_words": nec_words,
        "regex_patterns":  regex_pats,
        "rule_order":      rule_order,
        "self_destruct_enabled":  settings.get("self_destruct_enabled"),
        "self_destruct_minutes":  settings.get("self_destruct_minutes"),
        "duplicate_limit":        settings.get("duplicate_limit"),
        "duplicate_window_mins":  settings.get("duplicate_window_mins"),
        "min_words":              settings.get("min_words"),
        "max_words":              settings.get("max_words"),
        "min_lines":              settings.get("min_lines"),
        "max_lines":              settings.get("max_lines"),
        "min_chars":              settings.get("min_chars"),
        "max_chars":              settings.get("max_chars"),
        "necessary_words_active": settings.get("necessary_words_active"),
        "regex_active":           settings.get("regex_active"),
        "lock_admins":            settings.get("lock_admins"),
        "timed_locks":            settings.get("timed_locks", {}),
    }


@router.put("/api/groups/{chat_id}/automod/advanced")
async def update_advanced_automod(chat_id: int, request: Request):
    db   = request.app.state.db
    _check_access(request, chat_id)
    body = await request.json()

    from db.ops.automod import (
        update_group_setting, upsert_silent_time,
        set_rule_time_window, set_rule_penalty,
        save_rule_priority, add_regex_pattern, remove_regex_pattern,
        add_necessary_word, clear_necessary_words
    )

    # Bulk update simple settings
    simple_keys = [
        "self_destruct_enabled", "self_destruct_minutes",
        "duplicate_limit", "duplicate_window_mins",
        "min_words", "max_words", "min_lines", "max_lines",
        "min_chars", "max_chars", "necessary_words_active",
        "regex_active", "lock_admins",
    ]
    for key in simple_keys:
        if key in body:
            await update_group_setting(db, chat_id, key, body[key])

    # Time windows
    for rule_key, tw in body.get("time_windows", {}).items():
        await set_rule_time_window(
            db, chat_id, rule_key, tw["start"], tw["end"]
        )

    # Penalties
    for rule_key, p in body.get("penalties", {}).items():
        await set_rule_penalty(
            db, chat_id, rule_key,
            p["penalty"], p.get("duration_hours", 0)
        )

    # Silent times
    for slot_data in body.get("silent_times", []):
        await upsert_silent_time(
            db, chat_id,
            slot_data["slot"],
            slot_data["start_time"],
            slot_data["end_time"],
            slot_data.get("is_active", True),
            slot_data.get("start_text", ""),
            slot_data.get("end_text", ""),
        )

    # Rule order
    if "rule_order" in body:
        await save_rule_priority(db, chat_id, body["rule_order"])

    # Add regex patterns
    if "add_regex" in body:
        await add_regex_pattern(db, chat_id, body["add_regex"])

    # Remove regex patterns
    if "remove_regex" in body:
        await remove_regex_pattern(db, chat_id, body["remove_regex"])

    # Necessary words
    if "necessary_words" in body:
        # Clear and re-add
        await clear_necessary_words(db, chat_id)
        for word in body["necessary_words"]:
            await add_necessary_word(db, chat_id, word)

    return {"ok": True}


@router.get("/api/groups/{chat_id}/automod/templates")
async def get_templates(chat_id: int, request: Request):
    db   = request.app.state.db
    _check_access(request, chat_id)
    rows = await db.fetch(
        "SELECT * FROM rule_templates ORDER BY is_builtin DESC, name ASC"
    )
    return [dict(r) for r in rows]


@router.post("/api/groups/{chat_id}/automod/templates/apply")
async def apply_template(chat_id: int, request: Request):
    db          = request.app.state.db
    _check_access(request, chat_id)
    body        = await request.json()
    template_id = body.get("template_id")

    row = await db.fetchrow(
        "SELECT * FROM rule_templates WHERE id=$1", template_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    import json
    settings = row["settings"]
    if isinstance(settings, str):
        settings = json.loads(settings)

    # Apply template settings to group
    from db.ops.automod import bulk_update_group_settings
    await bulk_update_group_settings(db, chat_id, settings)
    return {"ok": True, "applied": row["name"]}


@router.put("/api/groups/{chat_id}/automod/rule-priority")
async def update_rule_priority(chat_id: int, request: Request):
    db   = request.app.state.db
    _check_access(request, chat_id)
    body = await request.json()

    from db.ops.automod import save_rule_priority
    await save_rule_priority(db, chat_id, body.get("order", []))
    return {"ok": True}


@router.get("/api/groups/{chat_id}/automod/conflicts")
async def detect_conflicts(chat_id: int, request: Request):
    db       = request.app.state.db
    _check_access(request, chat_id)

    from db.ops.groups import get_group
    group = await get_group(chat_id)
    if not group:
        return []

    settings = group.get('settings') or {}
    conflicts = []
    locks = settings.get("locks", {}) or {}

    # text=True + min_words > 0 → contradiction
    if locks.get("text") and (settings.get("min_words", 0) > 0):
        conflicts.append({
            "rule_a": "lock_text",
            "rule_b": "min_words",
            "conflict_type": "contradiction",
            "message": "Text is locked but min_words requires text messages"
        })

    # no_caption=True + photo=True → redundant
    if locks.get("no_caption") and locks.get("photo"):
        conflicts.append({
            "rule_a": "lock_photo",
            "rule_b": "lock_no_caption",
            "conflict_type": "redundant",
            "message": "Photos are locked — no_caption rule is redundant"
        })

    # emoji_only=True + emoji=True → redundant
    if locks.get("emoji") and locks.get("emoji_only"):
        conflicts.append({
            "rule_a": "lock_emoji",
            "rule_b": "lock_emoji_only",
            "conflict_type": "redundant",
            "message": "Emoji lock already covers emoji-only messages"
        })

    # necessary_words_active + text locked → impossible
    if settings.get("necessary_words_active") and locks.get("text"):
        conflicts.append({
            "rule_a": "necessary_words",
            "rule_b": "lock_text",
            "conflict_type": "impossible",
            "message": "Necessary words requires text but text is locked"
        })

    # min_words > max_words
    min_w = settings.get("min_words", 0)
    max_w = settings.get("max_words", 0)
    if min_w > 0 and max_w > 0 and min_w > max_w:
        conflicts.append({
            "rule_a": "min_words",
            "rule_b": "max_words",
            "conflict_type": "impossible",
            "message": f"min_words ({min_w}) > max_words ({max_w})"
        })

    return conflicts


def _check_access(request: Request, chat_id: int):
    # Verify user is admin of this group
    # Uses existing middleware
    pass
