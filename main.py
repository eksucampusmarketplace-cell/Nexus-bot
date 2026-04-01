import asyncio
import logging
import os
import re
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update

import db.ops.bots as db_ops_bots
from bot.factory import create_application
from bot.registry import get as registry_get
from bot.registry import get_all as registry_get_all
from bot.registry import register as registry_register
from bot.utils.crypto import decrypt_token
from config import settings
from db.client import db

# Validate settings before starting
settings.validate_required_settings()

# Structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("[STARTUP] Nexus Bot starting")
    logger.info("=" * 60)

    # Initialize database first
    try:
        await db.connect()
        logger.info("[STARTUP] ✅ Database pool connected")
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Database connection failed: {e}")
        raise

    pool = db.pool
    app.state.db = pool
    app.state.redis = None

    # Run all pending migrations before anything else
    try:
        from db.migrate import run_migrations

        logger.info("[STARTUP] Running database migrations...")
        await run_migrations(pool)
        logger.info("[STARTUP] ✅ Migrations complete")
    except Exception as e:
        logger.critical(f"[STARTUP] ❌ Migration failed — cannot start: {e}")
        raise

    # Initialize Redis
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        app.state.redis = redis_client
        db.redis = redis_client  # Make Redis available via db client
        logger.info("[STARTUP] ✅ Redis connected")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Failed to connect to Redis: {e}")
        redis_client = None
        db.redis = None

    # Primary bot
    primary_token = settings.PRIMARY_BOT_TOKEN

    # Validate token format before attempting to initialize
    token_pattern = r"^\d{8,15}:[\w-]{30,}$"
    if not re.match(token_pattern, primary_token):
        logger.error(
            "[STARTUP] ❌ Invalid PRIMARY_BOT_TOKEN format. "
            "Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz "
            "(bot ID: 8-12 digits, token: 35-50 chars). "
            "Please check your environment variables."
        )
        raise ValueError(
            "Invalid bot token format. Bot tokens should be in format: BOT_ID:TOKEN"
        )

    try:
        primary_app = create_application(primary_token, is_primary=True)
        primary_app.bot_data["db_pool"] = pool
        primary_app.bot_data["db"] = pool
        primary_app.bot_data["redis"] = redis_client

        # Startup assertion: verify db key is set
        assert (
            primary_app.bot_data["db"] is not None
        ), "bot_data['db'] must be set before starting the bot"

        logger.info("[STARTUP] Initializing primary bot...")
        await primary_app.initialize()
        logger.info("[STARTUP] Starting primary bot...")
        await primary_app.start()

        # Brief pause to ensure bot is fully ready
        await asyncio.sleep(0.5)

        # Verify bot is properly initialized
        logger.info("[STARTUP] Fetching bot information from Telegram...")
        primary_me = await primary_app.bot.get_me()

        if not primary_me or primary_me.id == 0:
            raise ValueError(
                "Bot initialization failed: get_me() returned invalid bot object."
            )

        logger.info(
            f"[STARTUP] ✅ Primary bot @{primary_me.username} (ID: {primary_me.id}) is online"
        )

        # Check privacy mode (critical for group message handling)
        can_read_all = getattr(primary_me, "can_read_all_group_messages", None)
        if can_read_all is False:
            logger.warning(
                "[STARTUP] ⚠️ PRIVACY MODE IS ON — Bot can only see messages that start with /"
            )
            logger.warning(
                "[STARTUP] ⚠️ To fix: Open @BotFather → Bot Settings → Group Privacy → Turn OFF"
            )
            logger.warning(
                "[STARTUP] ⚠️ Without this: automod, filters, and blacklist will NOT work in groups"
            )

        # Auto-set MAIN_BOT_USERNAME if not configured
        if not settings.MAIN_BOT_USERNAME:
            settings.MAIN_BOT_USERNAME = primary_me.username
            logger.info(
                f"[STARTUP] ✅ Auto-detected MAIN_BOT_USERNAME: @{primary_me.username}"
            )

        # Cache bot info to reduce API calls
        primary_app.bot_data["cached_bot_info"] = {
            "id": primary_me.id,
            "username": primary_me.username,
            "first_name": primary_me.first_name,
            "is_bot": primary_me.is_bot,
        }

        # Save primary bot to DB if not exists
        await db_ops_bots.upsert_bot(
            pool,
            bot_id=primary_me.id,
            username=primary_me.username,
            token=primary_token,
            is_primary=True,
            status="active",
            owner_user_id=settings.OWNER_ID,
        )
        await registry_register(primary_me.id, primary_app)
        app.state.bot = primary_app.bot
        app.state.lazy_manager = None

        # Register webhook for primary bot (Bug D fix)
        try:
            from bot.utils.crypto import hash_token as _hash_token

            # Bug #12 fix: Use opaque webhook secret instead of raw bot token
            webhook_secret = _hash_token(primary_token)[:32]
            webhook_url = f"{settings.webhook_url}/webhook/{webhook_secret}"
            await primary_app.bot.set_webhook(
                url=webhook_url,
                allowed_updates=[
                    "message",
                    "callback_query",
                    "chat_member",
                    "my_chat_member",
                    "inline_query",
                ],
            )
            logger.info(f"[STARTUP] ✅ Primary bot webhook set → {webhook_url}")
        except Exception as e:
            logger.warning(f"[STARTUP] ⚠️ Failed to set primary bot webhook: {e}")

    except Exception as e:
        logger.critical(f"[STARTUP] ❌ Failed to start primary bot: {e}")
        raise

    # Load and start clone bots
    try:
        logger.info("[STARTUP] Loading clone bots...")
        clones = await db_ops_bots.get_active_clones(pool)
        logger.info(f"[STARTUP] Found {len(clones)} active clones to start")

        for clone_row in clones:
            try:
                clone_token = decrypt_token(clone_row["token_encrypted"])
                clone_app = create_application(clone_token, is_primary=False)
                clone_app.bot_data["db_pool"] = pool
                clone_app.bot_data["db"] = pool
                clone_app.bot_data["redis"] = redis_client

                await clone_app.initialize()
                await clone_app.start()

                try:
                    me = await clone_app.bot.get_me()
                except AttributeError:
                    me = clone_app.bot.get_me()

                # Cache bot info to reduce API calls
                clone_app.bot_data["cached_bot_info"] = {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "is_bot": me.is_bot,
                }

                await registry_register(me.id, clone_app)
                logger.info(
                    f"[STARTUP] ✅ Started clone bot @{me.username} (ID: {me.id})"
                )

                # Re-register webhook for clone bot so it receives my_chat_member events
                try:
                    from bot.utils.crypto import hash_token as _clone_hash

                    clone_webhook_secret = _clone_hash(clone_token)[:32]
                    clone_webhook_url = (
                        f"{settings.webhook_url}/webhook/{clone_webhook_secret}"
                    )
                    await clone_app.bot.set_webhook(
                        url=clone_webhook_url,
                        allowed_updates=[
                            "message",
                            "callback_query",
                            "chat_member",
                            "my_chat_member",
                            "inline_query",
                        ],
                    )
                    logger.info(f"[STARTUP] ✅ Clone webhook set for @{me.username}")
                except Exception as wh_err:
                    logger.warning(
                        f"[STARTUP] ⚠️ Failed to set clone webhook for @{me.username}: {wh_err}"
                    )

                # Sync clone bot groups that have NULL bot_token_hash (Bug E fix)
                try:
                    from bot.utils.crypto import hash_token

                    token_hash = hash_token(clone_token)
                    async with pool.acquire() as sync_conn:
                        synced_count = (
                            await sync_conn.fetchval(
                                """WITH updated AS (
                                       UPDATE groups SET bot_token_hash = $1
                                       WHERE chat_id IN (
                                           SELECT chat_id FROM clone_bot_groups WHERE bot_id = $2
                                       )
                                       AND (bot_token_hash IS NULL OR bot_token_hash != $1)
                                       RETURNING 1
                                   )
                                   SELECT COUNT(*) FROM updated""",
                                token_hash,
                                me.id,
                            )
                            or 0
                        )
                    if synced_count > 0:
                        logger.info(
                            f"[STARTUP] ✅ Synced {synced_count} groups for clone @{me.username}"
                        )
                except Exception as sync_err:
                    logger.debug(
                        f"[STARTUP] Clone group sync skipped for @{me.username}: {sync_err}"
                    )

            except Exception as ce:
                logger.error(
                    f"[STARTUP] ⚠️ Failed to start clone {clone_row['bot_id']}: {ce}"
                )
                continue
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Failed to load clones: {e}")

    # Fix 14 + Bug F: Check privacy mode for ALL bots (primary + clones)
    # Also send DM notifications to clone owners
    for bot_id, bot_app in registry_get_all().items():
        try:
            me = await bot_app.bot.get_me()
            if getattr(me, "can_read_all_group_messages", None) is False:
                logger.warning(f"[STARTUP] ⚠️ CLONE @{me.username} has PRIVACY MODE ON")
                logger.warning(
                    "[STARTUP] Fix: @BotFather → /mybots → Bot Settings → Group Privacy → Turn OFF"
                )
                logger.warning(
                    "[STARTUP] Without this: automod, filters, and blacklist will NOT work "
                    "for this clone"
                )
                # Send DM notification to clone owner (not just log)
                try:
                    from bot.utils.error_notifier import notify_privacy_mode_on

                    asyncio.create_task(
                        notify_privacy_mode_on(bot_app.bot, me.id, me.username, pool)
                    )
                except Exception as notify_err:
                    logger.debug(
                        f"[STARTUP] Privacy mode notification skipped: {notify_err}"
                    )
        except Exception:
            pass

    # Start night mode scheduler (v21)
    try:
        from bot.handlers.night_mode import start_night_mode_scheduler

        await start_night_mode_scheduler(primary_app)
        logger.info("[STARTUP] ✅ Night mode scheduler started")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Night mode scheduler failed to start: {e}")

    # ── Phase 3: ML Classifier Startup ──────────────────────────────────────
    try:
        from bot.ml.spam_classifier import classifier

        loaded = await classifier.load()
        if loaded:
            logger.info("[STARTUP] ✅ Spam classifier loaded")
        else:
            logger.info(
                "[STARTUP] ℹ️  No spam model yet — run python -m bot.ml.train when ready"
            )
    except Exception as e:
        logger.debug(f"[STARTUP] Classifier load skipped: {e}")
    # ───────────────────────────────────────────────────────────────────────

    # ── Phase 4: Analytics Background Jobs ────────────────────────────────
    # Track consecutive failures for persistent error notification
    analytics_failure_counts = {"hourly": 0, "daily": 0}

    async def _hourly_analytics_job():
        while True:
            try:
                from bot.analytics.aggregator import aggregate_hourly

                await aggregate_hourly(pool)
                analytics_failure_counts["hourly"] = 0  # Reset on success
            except Exception as e:
                logger.error(f"[ANALYTICS] Hourly job error: {e}")
                analytics_failure_counts["hourly"] += 1
                # Notify owner if 3 consecutive failures
                if analytics_failure_counts["hourly"] >= 3:
                    try:
                        from bot.utils.error_notifier import notify_owner

                        asyncio.create_task(
                            notify_owner(
                                primary_app.bot,
                                settings.OWNER_ID,
                                "ANALYTICS_ERROR",
                                context={
                                    "failures": analytics_failure_counts["hourly"],
                                    "error": str(e),
                                },
                                pool=pool,
                            )
                        )
                    except Exception:
                        pass
            await asyncio.sleep(3600)

    async def _daily_analytics_job():
        while True:
            try:
                from bot.analytics.aggregator import aggregate_daily

                await aggregate_daily(pool)
                analytics_failure_counts["daily"] = 0  # Reset on success
            except Exception as e:
                logger.error(f"[ANALYTICS] Daily job error: {e}")
                analytics_failure_counts["daily"] += 1
            await asyncio.sleep(86400)

    # Bug #86 fix: Stagger analytics jobs so they don't all run at the same time on startup
    async def _staggered_daily():
        await asyncio.sleep(300)  # 5 minute offset from hourly
        await _daily_analytics_job()

    asyncio.create_task(_hourly_analytics_job())
    asyncio.create_task(_staggered_daily())
    logger.info(
        "[STARTUP] ✅ Analytics background jobs started (daily staggered by 5min)"
    )

    # ── Federation XP sync background job (Feature 7) ─────────────────────
    async def _federation_xp_sync_job():
        await asyncio.sleep(600)  # 10 minute offset from other jobs
        while True:
            try:
                from bot.handlers.fed_leaderboard import sync_federation_xp

                await sync_federation_xp(pool)
            except Exception as e:
                logger.error(f"[FED_XP] Sync job error: {e}")
            await asyncio.sleep(3600)  # Run hourly

    asyncio.create_task(_federation_xp_sync_job())
    logger.info("[STARTUP] ✅ Federation XP sync background job started")
    # ───────────────────────────────────────────────────────────────────────

    # ── Ticket Support System background jobs ─────────────────────────────
    async def _ticket_auto_close_job():
        await asyncio.sleep(900)  # 15 minute offset from other jobs
        while True:
            try:
                from db.ops.tickets import auto_close_stale_tickets

                closed = await auto_close_stale_tickets(pool)
                if closed:
                    logger.info(f"[TICKETS] Auto-closed {closed} stale ticket(s)")
            except Exception as e:
                logger.error(f"[TICKETS] Auto-close job error: {e}")
            await asyncio.sleep(1800)  # Run every 30 minutes

    async def _ticket_survey_job():
        await asyncio.sleep(1200)  # 20 minute offset
        while True:
            try:
                from db.ops.tickets import (get_unsurveyed_closed_tickets,
                                            mark_survey_sent)

                tickets = await get_unsurveyed_closed_tickets(pool)
                for ticket in tickets:
                    try:
                        # Send satisfaction survey via DM to ticket creator
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    f"{'⭐' * i} ({i})",
                                    callback_data=f"ticket:rate:{ticket['id']}:{i}",
                                )
                                for i in range(1, 6)
                            ]
                        ])
                        await primary_app.bot.send_message(
                            chat_id=ticket["creator_id"],
                            text=(
                                f"🎫 <b>Ticket #{ticket['id']} — Satisfaction Survey</b>\n\n"
                                f"Your ticket \"{ticket['subject'][:50]}\" has been resolved.\n"
                                f"How would you rate the support you received?\n\n"
                                f"Please tap a rating below:"
                            ),
                            parse_mode="HTML",
                            reply_markup=keyboard,
                        )
                        await mark_survey_sent(pool, ticket["id"])
                    except Exception:
                        # User may have blocked the bot — skip silently
                        await mark_survey_sent(pool, ticket["id"])
            except Exception as e:
                logger.error(f"[TICKETS] Survey job error: {e}")
            await asyncio.sleep(3600)  # Run hourly

    asyncio.create_task(_ticket_auto_close_job())
    asyncio.create_task(_ticket_survey_job())
    logger.info("[STARTUP] ✅ Ticket background jobs started (auto-close + surveys)")
    # ───────────────────────────────────────────────────────────────────────

    # ── Phase 5: Self Keep-Alive Ping ─────────────────────────────────────
    async def _keep_alive_ping():
        import aiohttp

        base_url = settings.RENDER_EXTERNAL_URL
        if not base_url:
            logger.debug(
                "[KEEP-ALIVE] RENDER_EXTERNAL_URL not set — skipping keep-alive ping"
            )
            return
        ping_url = f"{base_url.rstrip('/')}/health"
        await asyncio.sleep(60)
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.get(ping_url, timeout=aiohttp.ClientTimeout(total=10))
                logger.debug("[KEEP-ALIVE] Pinged health endpoint")
            except Exception as e:
                logger.debug(f"[KEEP-ALIVE] Ping failed: {e}")
            await asyncio.sleep(240)

    asyncio.create_task(_keep_alive_ping())
    logger.info("[STARTUP] ✅ Keep-alive ping task started")
    # ───────────────────────────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("[STARTUP] ✅ All services started")
    logger.info("=" * 60)

    yield {"pool": pool, "redis": redis_client, "primary_app": primary_app}

    # Shutdown
    logger.info("[SHUTDOWN] Nexus Bot stopping...")
    for bot_id, app in registry_get_all().items():
        try:
            logger.info(f"[SHUTDOWN] Stopping bot ID {bot_id}...")
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error stopping bot {bot_id}: {e}")

    await db.disconnect()
    logger.info("[SHUTDOWN] ✅ Database pool disconnected")
    logger.info("[SHUTDOWN] ✅ Goodbye!")


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
# Bug #1 fix: allow_origins=["*"] with allow_credentials=True is forbidden by the CORS spec.
# Use allow_origin_regex to match any origin explicitly while still allowing credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register security middleware
from api.middleware import (InputValidationMiddleware,  # noqa: E402
                            RateLimitMiddleware, SecurityHeadersMiddleware)

_security_headers = SecurityHeadersMiddleware()
_rate_limiter = RateLimitMiddleware()
_input_validator = InputValidationMiddleware()


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    return await _security_headers(request, call_next)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    return await _rate_limiter(request, call_next)


@app.middleware("http")
async def input_validation_middleware(request: Request, call_next):
    return await _input_validator(request, call_next)


# Health check endpoint (used by keep-alive ping to prevent Render cold starts)
@app.get("/health")
async def health():
    return {"status": "ok"}


# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/miniapp/index.html")


# Bot webhooks
# Bug #12/#13 fix: Use opaque webhook secret derived from token hash instead of raw token in URL.
# The raw bot token is no longer exposed in webhook URLs or server logs.

# Deduplication cache: track recently processed update_ids to prevent double-processing.
# Uses a bounded dict keyed by (bot_id, update_id) with a max size to prevent memory leaks.
_recent_update_ids: dict[tuple[int, int], bool] = {}
_DEDUP_MAX_SIZE = 1000


@app.post("/webhook/{webhook_secret}")
async def telegram_webhook(webhook_secret: str, request: Request):
    from bot.utils.crypto import hash_token

    target_app = None
    # Match by token hash (new secure method)
    for bot_app in registry_get_all().values():
        if hash_token(bot_app.bot.token)[:32] == webhook_secret:
            target_app = bot_app
            break

    # Fallback: try matching by raw token for backward compatibility
    if not target_app:
        for bot_app in registry_get_all().values():
            if bot_app.bot.token == webhook_secret:
                target_app = bot_app
                break

    # Fallback: try matching by bot_id
    if not target_app:
        try:
            bot_id = int(webhook_secret)
            target_app = registry_get(bot_id)
        except ValueError:
            pass

    if not target_app:
        logger.warning(
            f"[WEBHOOK] No bot found for webhook secret: {webhook_secret[:10]}..."
        )
        return Response(status_code=404)

    data = await request.json()

    # Deduplicate by update_id to prevent double-processing from Telegram retries
    update_id = data.get("update_id")
    if update_id is not None:
        dedup_key = (target_app.bot.id, update_id)
        if dedup_key in _recent_update_ids:
            logger.debug(f"[WEBHOOK] Duplicate update_id={update_id} — skipping")
            return Response(status_code=200)
        # Evict oldest entries if cache is full
        if len(_recent_update_ids) >= _DEDUP_MAX_SIZE:
            # Remove the oldest half of entries
            keys_to_remove = list(_recent_update_ids.keys())[: _DEDUP_MAX_SIZE // 2]
            for k in keys_to_remove:
                _recent_update_ids.pop(k, None)
        _recent_update_ids[dedup_key] = True

    update = Update.de_json(data, target_app.bot)
    await target_app.process_update(update)
    return Response(status_code=200)


# Serve Mini App static files
miniapp_path = os.path.join(os.path.dirname(__file__), "miniapp")
if os.path.exists(miniapp_path):
    app.mount(
        "/miniapp", StaticFiles(directory=miniapp_path, html=True), name="miniapp"
    )

# Import and include API routers
try:
    # Bug #36/#37/#38 fix: Import previously unregistered routers
    from api.routes import admin, analytics
    from api.routes import antiraid as antiraid_api
    from api.routes import auth, automod, backup, billing, boost, bots
    from api.routes import bots_messages as bots_messages_api
    from api.routes import broadcast, channel_gate, channels
    from api.routes import debug as debug_api
    from api.routes import (engagement, events, events_new, games, groups,
                            log_channel, me, member_stats, members, messages)
    from api.routes import moderation as moderation_api
    from api.routes import modules
    from api.routes import notes as notes_api
    from api.routes import photos as photos_api
    from api.routes import reports, roles, scheduler
    from api.routes import session as session_api
    from api.routes import stats, text_config, webhooks
    from api.routes.antiraid import global_router as antiraid_global_router

    # Core API routers (need prefix since routes don't include it)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
    app.include_router(bots.router, prefix="/api/bots", tags=["bots"])

    # Routes with full paths defined in the router (no prefix needed)
    app.include_router(automod.router, tags=["automod"])
    # Bug #2 fix: Register events.py router for SSE query-param endpoint
    app.include_router(events.router, prefix="/api/events", tags=["sse"])
    app.include_router(events_new.router, tags=["events_new"])
    app.include_router(scheduler.router, tags=["scheduler"])
    app.include_router(log_channel.router, tags=["log_channel"])
    app.include_router(moderation_api.router, tags=["moderation"])

    # Routes that need prefix
    app.include_router(me.router, prefix="/api/me", tags=["me"])

    # Analytics routes
    app.include_router(analytics.router, tags=["analytics"])

    # Backup routes
    app.include_router(backup.router, tags=["backup"])

    # Additional routes
    app.include_router(stats.router, tags=["stats"])
    app.include_router(admin.router, tags=["admin"])
    app.include_router(billing.router, tags=["billing"])
    app.include_router(boost.router, tags=["boost"])

    # Engagement routes
    app.include_router(engagement.router, tags=["engagement"])

    # Group-related routes with internal prefixes (prefix already defined in router)
    app.include_router(members.router)  # prefix="/api/groups/{chat_id}"
    app.include_router(messages.router)  # prefix="/api/groups/{chat_id}/messages"
    app.include_router(roles.router)  # prefix="/api/groups"
    app.include_router(reports.router)  # prefix="/api/groups/{chat_id}/reports"
    app.include_router(webhooks.router)  # prefix="/api/groups"
    app.include_router(text_config.router)  # prefix="/api/groups"
    app.include_router(modules.router)  # prefix="/api/groups"
    app.include_router(games.router)  # prefix="/api/groups"
    app.include_router(
        channel_gate.router
    )  # prefix="/api/groups/{chat_id}/channel-gate"

    # Other routes with internal prefixes
    app.include_router(broadcast.router)  # prefix="/api/broadcast"
    app.include_router(channels.router)  # prefix="/api/channels"
    app.include_router(member_stats.router)  # prefix="/api/me"
    app.include_router(antiraid_api.router)  # prefix="/api/groups/{chat_id}/antiraid"
    app.include_router(antiraid_global_router)  # /api/antiraid/banlist
    app.include_router(notes_api.router)  # prefix="/api/groups/{chat_id}/notes"
    app.include_router(session_api.router)  # /api/session/convert

    # Bug #36 fix: Register photos router (was never included)
    app.include_router(photos_api.router, tags=["photos"])
    # Bug #37 fix: Register bots_messages router (was never included)
    app.include_router(bots_messages_api.router, tags=["bot-messages"])
    # Bug #38 fix: Register debug router only when DEBUG=True
    if settings.DEBUG:
        app.include_router(debug_api.router, tags=["debug"])
        logger.info("[STARTUP] Debug routes ENABLED (DEBUG=True)")
    else:
        logger.info("[STARTUP] Debug routes disabled (DEBUG=False)")

    from api.routes import pins as pins_api

    app.include_router(pins_api.router)  # prefix="/api/groups/{chat_id}/pins"

    # v21 New API routes
    from api.routes import federation as federation_api
    from api.routes import i18n as i18n_api
    from api.routes import users as users_api

    # Bug #39 fix: Register both federation routers (main + legacy)
    app.include_router(
        federation_api.router, prefix="/api/federation", tags=["federation"]
    )
    app.include_router(federation_api.legacy_router, tags=["federation"])
    app.include_router(users_api.router, prefix="/api/users", tags=["users"])
    app.include_router(i18n_api.router, prefix="/api/i18n", tags=["i18n"])

    # Register new API routes (captcha, night_mode, name_history, community_vote)
    from api.routes import captcha as captcha_api
    from api.routes import community_vote as community_vote_api
    from api.routes import name_history as name_history_api
    from api.routes import night_mode as night_mode_api

    app.include_router(captcha_api.router, tags=["captcha"])
    app.include_router(night_mode_api.router, tags=["night_mode"])
    app.include_router(name_history_api.router, tags=["name_history"])
    app.include_router(community_vote_api.router, tags=["community_vote"])

    # Custom Commands Builder API
    from api.routes import custom_commands as custom_commands_api

    app.include_router(custom_commands_api.router, tags=["custom_commands"])
    logger.info("[STARTUP] Custom Commands API route registered")

    logger.info("[STARTUP] ✅ All v21 API routes registered")

    # Ticket / Support System API routes
    from api.routes import tickets as tickets_api

    app.include_router(tickets_api.router, tags=["tickets"])
    logger.info("[STARTUP] ✅ Ticket support system API route registered")

    # Eight New Features — Analytics Dashboard route
    from api.routes import analytics_dashboard as analytics_dashboard_api

    app.include_router(analytics_dashboard_api.router, tags=["analytics_dashboard"])
    logger.info("[STARTUP] ✅ Analytics Dashboard route registered")

except ImportError as e:
    logger.warning(f"Failed to load API routers: {e}")
