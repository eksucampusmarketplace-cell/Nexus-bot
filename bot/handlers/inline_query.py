"""
bot/handlers/inline_query.py

Enhanced Inline Query System - v21
@BotName queries work from any chat without commands.
"""

import logging
import uuid
from datetime import datetime

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import ContextTypes, InlineQueryHandler

from bot.utils.localization import SUPPORTED_LANGUAGES

log = logging.getLogger("inline_query")


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle @botname queries from users.
    
    Queries:
      (empty) - Feature menu
      who are you / about - Bot identity
      who made you / developer - Developer info
      help / commands - Command reference
      stats / statistics - Live stats
      trust <user_id> - Trust score profile
    """
    query = update.inline_query
    user = update.effective_user
    db = context.bot_data.get("db")
    bot = context.bot
    
    if not query:
        return
    
    raw_query = (query.query or "").strip().lower()
    results = []
    
    # Empty query - show feature menu
    if not raw_query:
        results = _get_feature_menu()
        await query.answer(results, cache_time=60)
        return
    
    # Who are you / about
    if raw_query in ["who are you", "about", "what are you"]:
        results = [_get_about_article()]
    
    # Who made you / developer
    elif raw_query in ["who made you", "developer", "creator", "who built you"]:
        results = [_get_developer_article()]
    
    # Help / commands
    elif raw_query in ["help", "commands", "cmds", "how to use"]:
        results = [_get_help_article()]
    
    # Stats / statistics
    elif raw_query in ["stats", "statistics", "numbers", "info"]:
        results = await _get_stats_article(db)
    
    # Trust score lookup
    elif raw_query.startswith("trust ") or raw_query.startswith("trustscore "):
        parts = raw_query.split(None, 1)
        if len(parts) > 1:
            user_id_str = parts[1].strip()
            try:
                target_id = int(user_id_str)
                results = [await _get_trust_article(db, target_id)]
            except ValueError:
                results = [_get_error_article("Invalid user ID", "Please provide a numeric user ID.")]
        else:
            results = [_get_error_article("Missing user ID", "Usage: trust <user_id>")]
    
    # Unknown query - show suggestions
    else:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="Unknown query",
                description="Try: who are you | help | stats | trust <user_id>",
                input_message_content=InputTextMessageContent(
                    f"⚡ <b>Nexus Bot Inline</b>\n\n"
                    f"Unknown query: <code>{raw_query[:50]}</code>\n\n"
                    f"<b>Try:</b>\n"
                    f"• @BotName who are you\n"
                    f"• @BotName help\n"
                    f"• @BotName stats\n"
                    f"• @BotName trust 123456789",
                    parse_mode="HTML"
                ),
            )
        ]
    
    await query.answer(results, cache_time=30)
    
    # Log query
    if db and user:
        try:
            await db.execute(
                """INSERT INTO inline_queries (bot_id, user_id, query, result_type)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT DO NOTHING""",
                bot.id, user.id, raw_query[:100], raw_query.split()[0] if raw_query else "menu"
            )
        except Exception:
            pass
    
    log.info(f"[INLINE] Query | user={user.id} q={raw_query[:50]!r}")


def _get_feature_menu() -> list:
    """Get the feature menu for empty queries."""
    return [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="🤖 About Nexus Bot",
            description="Learn about the bot and its features",
            input_message_content=InputTextMessageContent(
                "🤖 <b>Nexus Bot</b>\n\n"
                "A powerful Telegram group management bot with:\n"
                "• Advanced moderation tools\n"
                "• TrustNet federation system\n"
                "• Community voting\n"
                "• Night mode scheduling\n"
                "• Name history tracking\n"
                "• 10 language support\n\n"
                "<i>Type @BotName help for commands</i>",
                parse_mode="HTML"
            ),
            thumb_url="https://telegram.org/img/t_logo.png",
        ),
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="❓ Help & Commands",
            description="Full command reference",
            input_message_content=InputTextMessageContent(
                "📚 <b>Nexus Bot Commands</b>\n\n"
                "<b>Moderation:</b> /ban /kick /mute /warn /purge\n"
                "<b>TrustNet:</b> /newtrust /jointrust /trustban\n"
                "<b>Community:</b> /vote /votestats\n"
                "<b>Settings:</b> /nightmode /lang /panel\n"
                "<b>Info:</b> /history /trustinfo /stats\n\n"
                "<i>Add me to your group to get started!</i>",
                parse_mode="HTML"
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="📊 Bot Statistics",
            description="Live stats from the database",
            input_message_content=InputTextMessageContent(
                "📊 <b>Nexus Bot Statistics</b>\n\n"
                "Loading stats...\n\n"
                "<i>Use @BotName stats for live data</i>",
                parse_mode="HTML"
            ),
        ),
    ]


def _get_about_article() -> InlineQueryResultArticle:
    """Get the about article."""
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="🤖 Who Am I?",
        description="Bot identity and feature list",
        input_message_content=InputTextMessageContent(
            "🤖 <b>Nexus Bot v21</b>\n\n"
            "I'm a comprehensive group management bot designed to help moderators "
            "maintain safe and engaging communities.\n\n"
            "<b>Key Features:</b>\n"
            "🌐 TrustNet — Cross-group ban sharing\n"
            "⚖️ Community Vote — Democratic moderation\n"
            "🌙 Night Mode — Scheduled restrictions\n"
            "📋 Name History — Track user changes\n"
            "🎭 Personality — Customizable bot tone\n"
            "🌍 Localization — 10 languages\n\n"
            "<b>Tech Stack:</b>\n"
            "• FastAPI + Python 3.11\n"
            "• PostgreSQL (Supabase)\n"
            "• Redis caching\n"
            "• Render cloud hosting",
            parse_mode="HTML"
        ),
    )


def _get_developer_article() -> InlineQueryResultArticle:
    """Get the developer article."""
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="👨‍💻 Developer Info",
        description="Tech stack and development details",
        input_message_content=InputTextMessageContent(
            "👨‍💻 <b>Nexus Bot Development</b>\n\n"
            "<b>Backend:</b>\n"
            "• Python 3.11 with FastAPI\n"
            "• python-telegram-bot (PTB) v20+\n"
            "• PostgreSQL via Supabase\n"
            "• Redis for caching & sessions\n\n"
            "<b>Frontend:</b>\n"
            "• Telegram Mini App (HTML/CSS/JS)\n"
            "• Telegram Web App SDK\n\n"
            "<b>Deployment:</b>\n"
            "• Render cloud platform\n"
            "• Webhook-based updates\n"
            "• Automatic scaling\n\n"
            "<b>Version:</b> v21 (March 2026)\n"
            "<b>License:</b> Private",
            parse_mode="HTML"
        ),
    )


def _get_help_article() -> InlineQueryResultArticle:
    """Get the help article."""
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="📚 Full Command List",
        description="Complete reference of all commands",
        input_message_content=InputTextMessageContent(
            "📚 <b>Nexus Bot Command Reference</b>\n\n"
            "<b>🛡️ Moderation:</b>\n"
            "/ban /unban /kick /mute /unmute /warn /unwarn /purge\n\n"
            "<b>🌐 TrustNet:</b>\n"
            "/newtrust /jointrust /leavetrust /trustban /trustinfo /myfeds\n\n"
            "<b>⚖️ Community:</b>\n"
            "/vote /votekick /votestats\n\n"
            "<b>🌙 Settings:</b>\n"
            "/nightmode /lang /grouplang /panel\n\n"
            "<b>📋 Info:</b>\n"
            "/history /trustinfo /trusttrust /stats\n\n"
            "<i>Use /help in a group for more details</i>",
            parse_mode="HTML"
        ),
    )


async def _get_stats_article(db) -> InlineQueryResultArticle:
    """Get live statistics from database."""
    stats_text = "📊 <b>Nexus Bot Statistics</b>\n\n"
    
    if db:
        try:
            async with db.acquire() as conn:
                groups = await conn.fetchval("SELECT COUNT(*) FROM groups") or 0
                users = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM users") or 0
                warnings = await conn.fetchval("SELECT COUNT(*) FROM warnings") or 0
                bans = await conn.fetchval("SELECT COUNT(*) FROM bans") or 0
                
                # Federation stats
                fed_bans = await conn.fetchval("SELECT COUNT(*) FROM federation_bans") or 0
                feds = await conn.fetchval("SELECT COUNT(*) FROM federations") or 0
                
                # Vote stats
                votes = await conn.fetchval("SELECT COUNT(*) FROM community_vote_log WHERE result = 'passed'") or 0
                
                stats_text += (
                    f"📱 <b>Groups:</b> {groups:,}\n"
                    f"👥 <b>Users:</b> {users:,}\n"
                    f"⚠️ <b>Warnings:</b> {warnings:,}\n"
                    f"🚫 <b>Bans:</b> {bans:,}\n"
                    f"🌐 <b>TrustNets:</b> {feds}\n"
                    f"🚫 <b>Fed Bans:</b> {fed_bans}\n"
                    f"⚖️ <b>Vote Actions:</b> {votes}\n\n"
                    f"<i>Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
                )
        except Exception as e:
            log.debug(f"Stats query error: {e}")
            stats_text += "<i>Statistics temporarily unavailable</i>"
    else:
        stats_text += "<i>Database connection unavailable</i>"
    
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="📊 Live Statistics",
        description="Real-time stats from the database",
        input_message_content=InputTextMessageContent(stats_text, parse_mode="HTML"),
    )


async def _get_trust_article(db, user_id: int) -> InlineQueryResultArticle:
    """Get trust score article for a user."""
    trust_text = f"🛡️ <b>Trust Profile</b>\n\n"
    trust_text += f"User ID: <code>{user_id}</code>\n\n"
    
    if db:
        try:
            async with db.acquire() as conn:
                # Get federation reputation
                reps = await conn.fetch(
                    """SELECT fr.score, f.name 
                       FROM federation_reputation fr
                       JOIN federations f ON f.id = fr.federation_id
                       WHERE fr.user_id = $1""",
                    user_id
                )
                
                # Get ban status
                bans = await conn.fetch(
                    "SELECT federation_id FROM federation_bans WHERE user_id = $1",
                    user_id
                )
                
                if reps:
                    avg_score = sum(r["score"] for r in reps) / len(reps)
                    
                    # Determine level
                    if avg_score >= 80:
                        level = "🟢 Trusted"
                    elif avg_score >= 60:
                        level = "🟡 Reliable"
                    elif avg_score >= 40:
                        level = "⚪ Neutral"
                    elif avg_score >= 20:
                        level = "🟠 Suspicious"
                    else:
                        level = "🔴 Untrusted"
                    
                    trust_text += f"<b>Trust Score:</b> {avg_score:.0f}/100\n"
                    trust_text += f"<b>Level:</b> {level}\n\n"
                    
                    if len(reps) > 0:
                        trust_text += "<b>By Network:</b>\n"
                        for r in reps[:5]:
                            trust_text += f"• {r['name']}: {r['score']}/100\n"
                else:
                    trust_text += "<b>Trust Score:</b> 50/100\n"
                    trust_text += "<b>Level:</b> ⚪ Neutral\n"
                    trust_text += "<i>No history found in any TrustNet</i>\n"
                
                if bans:
                    trust_text += f"\n⚠️ <b>Federation Bans:</b> {len(bans)}"
                else:
                    trust_text += "\n✅ No federation bans"
                    
        except Exception as e:
            log.debug(f"Trust query error: {e}")
            trust_text += "<i>Trust data temporarily unavailable</i>"
    else:
        trust_text += "<i>Database connection unavailable</i>\n"
        trust_text += "Default: 50/100 (Neutral)"
    
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=f"🛡️ Trust Score: {user_id}",
        description="Cross-federation trust profile",
        input_message_content=InputTextMessageContent(trust_text, parse_mode="HTML"),
    )


def _get_error_article(title: str, description: str) -> InlineQueryResultArticle:
    """Get an error article."""
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=f"❌ {title}",
        description=description,
        input_message_content=InputTextMessageContent(
            f"❌ <b>{title}</b>\n\n{description}",
            parse_mode="HTML"
        ),
    )


# Handler registration
inline_query_handlers = [
    InlineQueryHandler(handle_inline_query),
]
