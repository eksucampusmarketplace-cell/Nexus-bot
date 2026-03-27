"""
bot/handlers/tickets.py

Ticket / Support System bot commands.

Commands:
  /ticket <issue>   → open a new support ticket
  /close            → close a ticket (reply to ticket message)
  /assign @user     → assign ticket to a staff member
  /escalate         → escalate ticket to next level

Logs prefix: [TICKET]
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from bot.logging.log_channel import log_event
from db.ops import tickets as db_tickets

log = logging.getLogger("ticket")

GROUP = filters.ChatType.GROUPS
PRIVATE = filters.ChatType.PRIVATE


async def cmd_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ticket <issue> — open a new support ticket in the group."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    if not context.args:
        await msg.reply_text(
            "📋 <b>Open a Support Ticket</b>\n\n"
            "Usage: <code>/ticket your issue description</code>\n\n"
            "Example: <code>/ticket I can't access the study materials</code>",
            parse_mode="HTML",
        )
        return

    subject = " ".join(context.args)
    if len(subject) > 500:
        await msg.reply_text("❌ Ticket description too long (max 500 characters).")
        return

    # Determine priority from keywords
    priority = "normal"
    lower_subject = subject.lower()
    if any(w in lower_subject for w in ("urgent", "emergency", "critical", "asap")):
        priority = "urgent"
    elif any(w in lower_subject for w in ("important", "high priority")):
        priority = "high"

    creator_name = user.full_name or user.first_name or str(user.id)

    ticket = await db_tickets.create_ticket(
        pool=db,
        chat_id=chat.id,
        creator_id=user.id,
        creator_name=creator_name,
        subject=subject,
        priority=priority,
    )

    if not ticket:
        await msg.reply_text("❌ Failed to create ticket. Please try again.")
        return

    ticket_id = ticket["id"]
    priority_emoji = {"low": "🟢", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(priority, "🔵")

    # Create inline keyboard for staff actions
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Claim", callback_data=f"ticket:claim:{ticket_id}"),
            InlineKeyboardButton("⬆️ Escalate", callback_data=f"ticket:escalate:{ticket_id}"),
        ],
        [
            InlineKeyboardButton("✅ Close", callback_data=f"ticket:close:{ticket_id}"),
            InlineKeyboardButton("🔄 Priority", callback_data=f"ticket:priority:{ticket_id}"),
        ],
    ])

    sla_info = ""
    if ticket.get("sla_response_deadline"):
        sla_info = "\n⏱️ SLA: Response expected within configured time"

    reply = await msg.reply_text(
        f"🎫 <b>Ticket #{ticket_id}</b>\n\n"
        f"👤 From: {user.mention_html()}\n"
        f"{priority_emoji} Priority: {priority.title()}\n"
        f"📝 {subject}\n"
        f"📊 Status: Open{sla_info}\n\n"
        f"Staff can use the buttons below or reply with /assign @username",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    # Store the bot message ID for future reference
    if reply:
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE tickets SET bot_message_id = $1 WHERE id = $2",
                reply.message_id,
                ticket_id,
            )

    # Try auto-assign
    assigned = await db_tickets.auto_assign_ticket(db, chat.id, ticket_id)
    if assigned:
        await msg.reply_text(
            f"📥 Ticket #{ticket_id} has been auto-assigned to a staff member.",
        )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat.id, "ticket_created", {
            "ticket_id": ticket_id,
            "creator_id": user.id,
            "creator_name": creator_name,
            "subject": subject,
            "priority": priority,
            "chat_id": chat.id,
        })
    except Exception:
        pass

    await log_event(
        bot=context.bot,
        db=db,
        chat_id=chat.id,
        event_type="ticket_created",
        actor=user,
        details={"ticket_id": ticket_id, "subject": subject, "priority": priority},
        chat_title=chat.title or "",
        bot_id=context.bot.id,
    )
    log.info(f"[TICKET] Created #{ticket_id} | chat={chat.id} user={user.id} priority={priority}")


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/close — close a ticket. Must reply to the ticket message or provide ticket ID."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    ticket = None

    # Try to get ticket from args (e.g., /close 42)
    if context.args:
        try:
            ticket_id = int(context.args[0])
            ticket = await db_tickets.get_ticket(db, ticket_id)
        except (ValueError, IndexError):
            pass

    # Try to find ticket from replied message
    if not ticket and msg.reply_to_message:
        ticket = await db_tickets.get_ticket_by_message(
            db, chat.id, msg.reply_to_message.message_id
        )

    if not ticket:
        await msg.reply_text(
            "❌ Reply to a ticket message or provide ticket ID.\n"
            "Usage: <code>/close</code> (reply) or <code>/close 42</code>",
            parse_mode="HTML",
        )
        return

    if ticket["chat_id"] != chat.id:
        await msg.reply_text("❌ This ticket doesn't belong to this group.")
        return

    if ticket["status"] == "closed":
        await msg.reply_text(f"ℹ️ Ticket #{ticket['id']} is already closed.")
        return

    # Check permission: creator or admin
    is_creator = user.id == ticket["creator_id"]
    is_admin = False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("creator", "administrator")
    except Exception:
        pass

    if not is_creator and not is_admin:
        await msg.reply_text("❌ Only the ticket creator or admins can close tickets.")
        return

    await db_tickets.update_ticket_status(db, ticket["id"], "closed", closed_by=user.id)
    await db_tickets.add_ticket_message(
        db,
        ticket["id"],
        sender_id=user.id,
        sender_name=user.full_name or "",
        message_text="Ticket closed.",
        is_staff=is_admin,
        is_system=True,
    )

    await msg.reply_text(
        f"✅ <b>Ticket #{ticket['id']} closed</b>\n\n"
        f"Closed by: {user.mention_html()}\n"
        f"Thank you for using the support system!",
        parse_mode="HTML",
    )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat.id, "ticket_closed", {
            "ticket_id": ticket["id"],
            "closed_by": user.id,
            "chat_id": chat.id,
        })
    except Exception:
        pass

    log.info(f"[TICKET] Closed #{ticket['id']} | chat={chat.id} by={user.id}")


async def cmd_assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/assign @user — assign a ticket to a staff member. Must reply to ticket message."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    # Check admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ("creator", "administrator"):
            await msg.reply_text("❌ Only admins can assign tickets.")
            return
    except Exception:
        await msg.reply_text("❌ Could not verify admin status.")
        return

    ticket = None

    # Get ticket from reply
    if msg.reply_to_message:
        ticket = await db_tickets.get_ticket_by_message(
            db, chat.id, msg.reply_to_message.message_id
        )

    if not ticket:
        await msg.reply_text(
            "❌ Reply to a ticket message to assign it.\n"
            "Usage: reply to a ticket with <code>/assign @username</code>",
            parse_mode="HTML",
        )
        return

    if ticket["status"] == "closed":
        await msg.reply_text(f"❌ Ticket #{ticket['id']} is already closed.")
        return

    # Get target user
    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user and not context.args:
        # If no args but replying, assign to self
        target = user
    elif context.args:
        # Try to find mentioned user
        if msg.entities:
            for entity in msg.entities:
                if entity.type == "text_mention":
                    target = entity.user
                    break
                elif entity.type == "mention":
                    # @username mention — we'll use the command arg
                    pass

        if not target:
            # Try parsing user ID
            try:
                target_id = int(context.args[0].lstrip("@"))
                member_info = await context.bot.get_chat_member(chat.id, target_id)
                target = member_info.user
            except (ValueError, Exception):
                await msg.reply_text(
                    "❌ Could not find that user. Use <code>/assign @username</code>",
                    parse_mode="HTML",
                )
                return

    if not target:
        target = user  # Default: assign to self

    staff_name = target.full_name or target.first_name or str(target.id)
    await db_tickets.assign_ticket(
        db, ticket["id"], target.id, staff_name, assigned_by=user.id
    )

    await msg.reply_text(
        f"📥 <b>Ticket #{ticket['id']} assigned</b>\n\n"
        f"Assigned to: {target.mention_html()}\n"
        f"By: {user.mention_html()}",
        parse_mode="HTML",
    )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat.id, "ticket_assigned", {
            "ticket_id": ticket["id"],
            "assigned_to": target.id,
            "assigned_name": staff_name,
            "chat_id": chat.id,
        })
    except Exception:
        pass

    log.info(
        f"[TICKET] Assigned #{ticket['id']} to {target.id} | chat={chat.id} by={user.id}"
    )


async def cmd_escalate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/escalate — escalate a ticket to the next level. Reply to ticket message."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data.get("db")

    ticket = None

    # Try args first
    if context.args:
        try:
            ticket_id = int(context.args[0])
            ticket = await db_tickets.get_ticket(db, ticket_id)
        except (ValueError, IndexError):
            pass

    # Try reply
    if not ticket and msg.reply_to_message:
        ticket = await db_tickets.get_ticket_by_message(
            db, chat.id, msg.reply_to_message.message_id
        )

    if not ticket:
        await msg.reply_text(
            "❌ Reply to a ticket message or provide ticket ID.\n"
            "Usage: <code>/escalate</code> (reply) or <code>/escalate 42</code>",
            parse_mode="HTML",
        )
        return

    if ticket["chat_id"] != chat.id:
        await msg.reply_text("❌ This ticket doesn't belong to this group.")
        return

    if ticket["status"] == "closed":
        await msg.reply_text(f"❌ Ticket #{ticket['id']} is already closed.")
        return

    updated = await db_tickets.escalate_ticket(db, ticket["id"])
    if not updated:
        await msg.reply_text("❌ Failed to escalate ticket.")
        return

    await msg.reply_text(
        f"⬆️ <b>Ticket #{ticket['id']} escalated</b>\n\n"
        f"Escalation level: {updated['escalation_level']}\n"
        f"Escalated by: {user.mention_html()}\n"
        f"Status: {updated['status'].replace('_', ' ').title()}",
        parse_mode="HTML",
    )

    # Push SSE event
    try:
        from api.routes.events import EventBus

        await EventBus.publish(chat.id, "ticket_escalated", {
            "ticket_id": ticket["id"],
            "escalation_level": updated["escalation_level"],
            "chat_id": chat.id,
        })
    except Exception:
        pass

    log.info(
        f"[TICKET] Escalated #{ticket['id']} to level {updated['escalation_level']} | "
        f"chat={chat.id} by={user.id}"
    )


# ── Callback Query Handlers ────────────────────────────────────────────────


async def handle_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses on ticket messages."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "ticket:claim:42"
    parts = data.split(":")
    if len(parts) < 3:
        return

    action = parts[1]
    try:
        ticket_id = int(parts[2])
    except ValueError:
        return

    user = query.from_user
    chat = update.effective_chat
    db = context.bot_data.get("db")

    # Check admin permission for staff actions
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("creator", "administrator")
    except Exception:
        is_admin = False

    ticket = await db_tickets.get_ticket(db, ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return

    if ticket["status"] == "closed":
        await query.answer("This ticket is already closed.", show_alert=True)
        return

    if action == "claim":
        if not is_admin:
            await query.answer("Only admins can claim tickets.", show_alert=True)
            return

        staff_name = user.full_name or user.first_name or str(user.id)
        await db_tickets.assign_ticket(db, ticket_id, user.id, staff_name, assigned_by=user.id)
        await query.answer(f"You claimed ticket #{ticket_id}!")

        # Update the message
        updated = await db_tickets.get_ticket(db, ticket_id)
        await _update_ticket_message(query, updated)

    elif action == "escalate":
        if not is_admin:
            await query.answer("Only admins can escalate tickets.", show_alert=True)
            return

        updated = await db_tickets.escalate_ticket(db, ticket_id)
        if updated:
            await query.answer(f"Ticket #{ticket_id} escalated to level {updated['escalation_level']}!")
            await _update_ticket_message(query, updated)

    elif action == "close":
        is_creator = user.id == ticket["creator_id"]
        if not is_admin and not is_creator:
            await query.answer("Only the creator or admins can close tickets.", show_alert=True)
            return

        await db_tickets.update_ticket_status(db, ticket_id, "closed", closed_by=user.id)
        await db_tickets.add_ticket_message(
            db, ticket_id, user.id, user.full_name or "",
            "Ticket closed.", is_staff=is_admin, is_system=True,
        )
        updated = await db_tickets.get_ticket(db, ticket_id)
        await _update_ticket_message(query, updated)

        # Push SSE event
        try:
            from api.routes.events import EventBus

            await EventBus.publish(chat.id, "ticket_closed", {
                "ticket_id": ticket_id, "closed_by": user.id, "chat_id": chat.id,
            })
        except Exception:
            pass

    elif action == "priority":
        if not is_admin:
            await query.answer("Only admins can change priority.", show_alert=True)
            return

        # Cycle priority: normal → high → urgent → low → normal
        cycle = {"low": "normal", "normal": "high", "high": "urgent", "urgent": "low"}
        new_priority = cycle.get(ticket["priority"], "normal")
        await db_tickets.update_ticket_priority(db, ticket_id, new_priority)
        await query.answer(f"Priority changed to {new_priority}!")

        updated = await db_tickets.get_ticket(db, ticket_id)
        await _update_ticket_message(query, updated)

    elif action == "rate":
        # Satisfaction rating: ticket:rate:42:5
        if len(parts) < 4:
            return
        try:
            rating = int(parts[3])
        except ValueError:
            return
        await db_tickets.submit_satisfaction(db, ticket_id, rating)
        await query.edit_message_text(
            f"⭐ Thank you for rating ticket #{ticket_id}! ({rating}/5)\n"
            f"Your feedback helps us improve.",
        )


async def _update_ticket_message(query, ticket: dict):
    """Update the ticket inline message with current status."""
    if not ticket:
        return

    priority_emoji = {"low": "🟢", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(
        ticket["priority"], "🔵"
    )
    status_emoji = {
        "open": "📋", "in_progress": "🔧", "escalated": "⬆️", "closed": "✅"
    }.get(ticket["status"], "📋")

    assigned_text = f"\n👷 Assigned to: {ticket['assigned_name']}" if ticket.get("assigned_name") else ""
    escalation_text = (
        f"\n⬆️ Escalation level: {ticket['escalation_level']}"
        if ticket["escalation_level"] > 0
        else ""
    )

    text = (
        f"🎫 <b>Ticket #{ticket['id']}</b>\n\n"
        f"👤 From: {ticket['creator_name']}\n"
        f"{priority_emoji} Priority: {ticket['priority'].title()}\n"
        f"📝 {ticket['subject']}\n"
        f"{status_emoji} Status: {ticket['status'].replace('_', ' ').title()}"
        f"{assigned_text}{escalation_text}"
    )

    if ticket["status"] == "closed":
        keyboard = None
        text += "\n\n✅ This ticket has been resolved."
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Claim", callback_data=f"ticket:claim:{ticket['id']}"),
                InlineKeyboardButton("⬆️ Escalate", callback_data=f"ticket:escalate:{ticket['id']}"),
            ],
            [
                InlineKeyboardButton("✅ Close", callback_data=f"ticket:close:{ticket['id']}"),
                InlineKeyboardButton("🔄 Priority", callback_data=f"ticket:priority:{ticket['id']}"),
            ],
        ])

    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


# ── Handler Registration ───────────────────────────────────────────────────

ticket_handlers = [
    CommandHandler("ticket", cmd_ticket, filters=GROUP),
    CommandHandler("closeticket", cmd_close, filters=GROUP),
    CommandHandler("assign", cmd_assign, filters=GROUP),
    CommandHandler("escalate", cmd_escalate, filters=GROUP),
    CallbackQueryHandler(handle_ticket_callback, pattern=r"^ticket:"),
]
