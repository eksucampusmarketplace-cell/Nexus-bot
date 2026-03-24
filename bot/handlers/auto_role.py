"""
bot/handlers/auto_role.py

Auto-Role by XP — assign roles when users hit XP/level thresholds.

Commands:
  /autorole add <role_id> level=<N>   — Assign role at level N
  /autorole add <role_id> xp=<N>      — Assign role at N XP
  /autorole list                      — List auto-role rules
  /autorole remove <rule_id>          — Remove a rule

Hook: check_auto_roles() is called after every level-up event.

Log prefix: [AUTOROLE]
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.utils.permissions import is_admin

log = logging.getLogger("autorole")


async def cmd_autorole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage auto-role rules."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This command only works in groups.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Only admins can manage auto-roles.")
        return

    if not context.args:
        await update.message.reply_text(
            "<b>Auto-Role by XP</b>\n\n"
            "<code>/autorole add &lt;role_id&gt; level=5</code> — assign role at level 5\n"
            "<code>/autorole add &lt;role_id&gt; xp=1000</code> — assign role at 1000 XP\n"
            "<code>/autorole list</code> — list rules\n"
            "<code>/autorole remove &lt;rule_id&gt;</code> — remove a rule",
            parse_mode=ParseMode.HTML,
        )
        return

    db = context.bot_data.get("db_pool") or context.bot_data.get("db")
    bot_id = context.bot.id
    sub = context.args[0].lower()

    if sub == "add":
        await _add_rule(update, context, db, chat.id, bot_id)
    elif sub == "list":
        await _list_rules(update, db, chat.id, bot_id)
    elif sub == "remove":
        await _remove_rule(update, context, db, chat.id, bot_id)
    else:
        await update.message.reply_text("Unknown subcommand. Use add, list, or remove.")


async def _add_rule(update, context, db, chat_id, bot_id):
    """Add an auto-role rule."""
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /autorole add <role_id> level=<N> or xp=<N>"
        )
        return

    try:
        role_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("role_id must be a number.")
        return

    threshold_arg = context.args[2].lower()
    xp_threshold = 0
    level_threshold = 0

    if threshold_arg.startswith("level="):
        try:
            level_threshold = int(threshold_arg.split("=")[1])
        except ValueError:
            await update.message.reply_text("Invalid level value.")
            return
    elif threshold_arg.startswith("xp="):
        try:
            xp_threshold = int(threshold_arg.split("=")[1])
        except ValueError:
            await update.message.reply_text("Invalid XP value.")
            return
    else:
        await update.message.reply_text("Use level=<N> or xp=<N>.")
        return

    # Verify role exists
    async with db.acquire() as conn:
        role = await conn.fetchrow(
            "SELECT id, name FROM roles WHERE id=$1 AND chat_id=$2", role_id, chat_id
        )
        if not role:
            await update.message.reply_text(f"Role #{role_id} not found in this group.")
            return

        await conn.execute(
            """INSERT INTO auto_role_rules
               (chat_id, bot_id, role_id, xp_threshold, level_threshold)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (chat_id, bot_id, role_id) DO UPDATE
               SET xp_threshold=EXCLUDED.xp_threshold,
                   level_threshold=EXCLUDED.level_threshold,
                   is_active=TRUE""",
            chat_id,
            bot_id,
            role_id,
            xp_threshold,
            level_threshold,
        )

    threshold_str = (
        f"level {level_threshold}" if level_threshold else f"{xp_threshold} XP"
    )
    await update.message.reply_text(
        f"Auto-role rule added: role <b>{role['name']}</b> at {threshold_str}.",
        parse_mode=ParseMode.HTML,
    )
    log.info(
        f"[AUTOROLE] Added | chat={chat_id} role={role_id} "
        f"xp={xp_threshold} level={level_threshold}"
    )


async def _list_rules(update, db, chat_id, bot_id):
    """List auto-role rules."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ar.id, ar.role_id, ar.xp_threshold, ar.level_threshold, r.name
               FROM auto_role_rules ar
               LEFT JOIN roles r ON r.id = ar.role_id
               WHERE ar.chat_id=$1 AND ar.bot_id=$2 AND ar.is_active=TRUE
               ORDER BY ar.level_threshold, ar.xp_threshold""",
            chat_id,
            bot_id,
        )

    if not rows:
        await update.message.reply_text(
            "No auto-role rules configured.\nUse /autorole add to create one."
        )
        return

    lines = ["<b>Auto-Role Rules</b>\n"]
    for r in rows:
        threshold = (
            f"Level {r['level_threshold']}"
            if r["level_threshold"]
            else f"{r['xp_threshold']} XP"
        )
        lines.append(f"#{r['id']}: {r['name'] or 'Unknown'} at {threshold}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _remove_rule(update, context, db, chat_id, bot_id):
    """Remove an auto-role rule."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /autorole remove <rule_id>")
        return

    try:
        rule_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid rule ID.")
        return

    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE auto_role_rules SET is_active=FALSE WHERE id=$1 AND chat_id=$2",
            rule_id,
            chat_id,
        )

    if "UPDATE 1" in result:
        await update.message.reply_text(f"Rule #{rule_id} removed.")
        log.info(f"[AUTOROLE] Removed | chat={chat_id} id={rule_id}")
    else:
        await update.message.reply_text(f"Rule #{rule_id} not found.")


async def check_auto_roles(
    bot, db, chat_id: int, user_id: int, bot_id: int, xp: int, level: int
):
    """
    Check if a user qualifies for any auto-role assignments.
    Called after XP award / level-up events.
    """
    async with db.acquire() as conn:
        rules = await conn.fetch(
            """SELECT ar.id, ar.role_id, ar.xp_threshold, ar.level_threshold, r.name
               FROM auto_role_rules ar
               LEFT JOIN roles r ON r.id = ar.role_id
               WHERE ar.chat_id=$1 AND ar.bot_id=$2 AND ar.is_active=TRUE""",
            chat_id,
            bot_id,
        )

        for rule in rules:
            qualifies = False
            if rule["level_threshold"] and level >= rule["level_threshold"]:
                qualifies = True
            if rule["xp_threshold"] and xp >= rule["xp_threshold"]:
                qualifies = True

            if not qualifies:
                continue

            # Check if already assigned
            existing = await conn.fetchval(
                """SELECT 1 FROM user_roles
                   WHERE user_id=$1 AND chat_id=$2 AND role_id=$3""",
                user_id,
                chat_id,
                rule["role_id"],
            )
            if existing:
                continue

            # Assign role
            await conn.execute(
                """INSERT INTO user_roles (user_id, chat_id, role_id, granted_by)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (user_id, chat_id, role_id) DO NOTHING""",
                user_id,
                chat_id,
                rule["role_id"],
                bot_id,
            )

            role_name = rule["name"] or f"Role #{rule['role_id']}"
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"<b>Role Unlocked!</b>\n\n"
                        f"User {user_id} earned the <b>{role_name}</b> role!"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

            log.info(
                f"[AUTOROLE] Assigned | chat={chat_id} user={user_id} role={rule['role_id']}"
            )


autorole_handlers = [
    CommandHandler("autorole", cmd_autorole),
]
