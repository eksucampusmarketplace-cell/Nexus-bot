import os
import logging
import sys
import asyncio
import time
import httpx
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from telegram import Update

from config import settings
from db.client import db
from bot.factory import create_application
from bot.registry import register as registry_register, get as registry_get, get_all as registry_get_all
from bot.utils.crypto import encrypt_token, hash_token, decrypt_token
import db.ops.bots as db_ops_bots

# Validate settings before starting
settings.validate_required_settings()

# Structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
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

    # Run all pending migrations before anything else
    try:
        from db.migrate import run_migrations
        logger.info("[STARTUP] Running database migrations...")
        await run_migrations(pool)
        logger.info("[STARTUP] ✅ Migrations complete")
    except Exception as e:
        logger.critical(f"[STARTUP] ❌ Migration failed — cannot start: {e}")
        raise

    # Initialize Redis for music service
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("[STARTUP] ✅ Redis connected")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Failed to connect to Redis: {e}")
        redis_client = None

    # Initialize lazy manager for Pyrogram clients
    try:
        from bot.userbot.lazy_manager import LazyClientManager
        lazy_manager = LazyClientManager(pool)
        await lazy_manager.start()
        logger.info("[STARTUP] ✅ LazyClientManager started")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Failed to start LazyClientManager: {e}")
        lazy_manager = None

    # Initialize music player tables
    try:
        import db.ops.music_new as db_music
        await db_music.create_music_tables(pool)
        logger.info("[STARTUP] ✅ Music player tables initialized")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Failed to create music tables: {e}")
        # Continue startup even if music tables fail

    # Run stars economy migration
    try:
        migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_stars_economy.sql")
        if os.path.exists(migration_path):
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            await pool.execute(migration_sql)
            logger.info("[STARTUP] ✅ Stars economy tables migrated")
    except Exception as e:
        logger.debug(f"[STARTUP] Stars economy migration info: {e}")

    # Run anti-raid and captcha migration
    try:
        ar_migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_antiraid_captcha.sql")
        if os.path.exists(ar_migration_path):
            with open(ar_migration_path, 'r') as f:
                ar_migration_sql = f.read()
            await pool.execute(ar_migration_sql)
            logger.info("[STARTUP] ✅ Anti-raid and CAPTCHA tables migrated")
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Anti-raid and CAPTCHA migration failed: {e}")

    # Run scheduling migration
    try:
        sched_migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_scheduling.sql")
        if os.path.exists(sched_migration_path):
            with open(sched_migration_path, 'r') as f:
                sched_migration_sql = f.read()
            await pool.execute(sched_migration_sql)
            logger.info("[STARTUP] ✅ Scheduling tables migrated")
    except Exception as e:
        logger.debug(f"[STARTUP] Scheduling migration info: {e}")

    # Run log channel migration
    try:
        log_migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_log_channel.sql")
        if os.path.exists(log_migration_path):
            with open(log_migration_path, 'r') as f:
                log_migration_sql = f.read()
            await pool.execute(log_migration_sql)
            logger.info("[STARTUP] ✅ Log channel tables migrated")
    except Exception as e:
        logger.debug(f"[STARTUP] Log channel migration info: {e}")

    # Run reports migration
    try:
        reports_migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_reports.sql")
        if os.path.exists(reports_migration_path):
            with open(reports_migration_path, 'r') as f:
                reports_migration_sql = f.read()
            await pool.execute(reports_migration_sql)
            logger.info("[STARTUP] ✅ Reports tables migrated")
    except Exception as e:
        logger.debug(f"[STARTUP] Reports migration info: {e}")

    # Run webhooks migration
    try:
        webhooks_migration_path = os.path.join(os.path.dirname(__file__), "db", "migrations", "add_webhooks.sql")
        if os.path.exists(webhooks_migration_path):
            with open(webhooks_migration_path, 'r') as f:
                webhooks_migration_sql = f.read()
            await pool.execute(webhooks_migration_sql)
            logger.info("[STARTUP] ✅ Webhooks tables migrated")
    except Exception as e:
        logger.debug(f"[STARTUP] Webhooks migration info: {e}")

    # Primary bot
    primary_token = settings.PRIMARY_BOT_TOKEN

    # Validate token format before attempting to initialize
    # Telegram tokens: bot_id (up to 12 digits now):secret (35-45 chars)
    token_pattern = r'^\d{8,12}:[\w-]{35,50}$'
    if not re.match(token_pattern, primary_token):
        logger.error(
            f"[STARTUP] ❌ Invalid PRIMARY_BOT_TOKEN format. "
            f"Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz (bot ID: 8-12 digits, token: 35-50 chars). "
            f"Please check your environment variables."
        )
        raise ValueError("Invalid bot token format. Bot tokens should be in format: BOT_ID:TOKEN")

    try:
        primary_app = create_application(primary_token, is_primary=True)
        primary_app.bot_data["db_pool"] = pool
        primary_app.bot_data["db"] = pool
        primary_app.bot_data["redis"] = redis_client
        primary_app.bot_data["lazy_manager"] = lazy_manager

        logger.info("[STARTUP] Initializing primary bot...")
        await primary_app.initialize()
        logger.info("[STARTUP] Starting primary bot...")
        await primary_app.start()

        # Brief pause to ensure bot is fully ready
        await asyncio.sleep(0.5)

        # Verify bot is properly initialized - use async get_me() if available
        logger.info("[STARTUP] Fetching bot information from Telegram...")
        try:
            primary_me = await primary_app.bot.get_me()
        except AttributeError:
            # Fall back to sync method
            primary_me = primary_app.bot.get_me()

        if not primary_me or primary_me.id == 0:
            raise ValueError(
                f"Bot initialization failed: get_me() returned invalid bot object (id={getattr(primary_me, 'id', 'None') if primary_me else 'None'}). "
                f"This usually means the bot token is invalid or the bot cannot connect to Telegram."
            )

        logger.info(f"[STARTUP] Primary bot ready: @{primary_me.username} (id={primary_me.id})")

        primary_webhook = f"{settings.RENDER_EXTERNAL_URL}/webhook/{primary_me.id}"
        logger.info(f"[STARTUP] Setting webhook: {primary_webhook}")
        await primary_app.bot.set_webhook(
            url=primary_webhook,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        logger.info("[STARTUP] Webhook configured successfully")
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Failed to initialize primary bot: {e}", exc_info=True)
        raise

    # Upsert primary bot record in DB
    existing_primary = await db_ops_bots.get_bot_by_token_hash(pool, hash_token(primary_token))
    if not existing_primary:
        await db_ops_bots.insert_bot(pool, {
            "bot_id": primary_me.id,
            "username": primary_me.username,
            "display_name": primary_me.first_name,
            "token_encrypted": encrypt_token(primary_token),
            "token_hash": hash_token(primary_token),
            "owner_user_id": settings.OWNER_ID,
            "webhook_url": primary_webhook,
            "is_primary": True,
            "status": "active",
            "webhook_active": True,
        })
        logger.info(f"[STARTUP] ✅ Primary bot record created in DB")
    else:
        logger.info(f"[STARTUP] ✅ Primary bot already exists in DB")

    await registry_register(primary_me.id, primary_app)
    logger.info(f"[STARTUP] ✅ Primary bot @{primary_me.username} (id={primary_me.id}) live | webhook={primary_webhook}")

    # No music worker for primary bot - music is handled by separate music_service.py

    # Recover clones
    active_clones = await db_ops_bots.get_all_active_bots(pool)
    # Filter out primary from clone recovery
    clones_only = [c for c in active_clones if not c["is_primary"]]

    logger.info(f"[STARTUP] Recovering {len(clones_only)} clone(s)...")
    recovered = dead = 0

    for clone in clones_only:
        try:
            token = decrypt_token(clone["token_encrypted"])

            # Verify token still valid via Telegram API
            async with httpx.AsyncClient(timeout=8.0) as client:
                me_resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                me_data = me_resp.json()

            if not me_data.get("ok"):
                raise ValueError(f"Token rejected: {me_data.get('description')}")

            clone_app = create_application(token, is_primary=False)
            clone_app.bot_data["db_pool"] = pool
            clone_app.bot_data["db"] = pool
            clone_app.bot_data["redis"] = redis_client
            clone_app.bot_data["lazy_manager"] = lazy_manager
            await clone_app.initialize()
            await clone_app.start()

            # Brief pause to ensure bot is fully ready
            await asyncio.sleep(0.3)

            # Verify bot ID matches what's in the database
            try:
                clone_me = await clone_app.bot.get_me()
            except AttributeError:
                clone_me = clone_app.bot.get_me()

            if not clone_me or clone_me.id != clone["bot_id"]:
                raise ValueError(
                    f"Clone bot ID mismatch: expected {clone['bot_id']}, got {getattr(clone_me, 'id', 'None')}. "
                    f"This usually means the token has changed or the bot is different."
                )

            # Re-register webhook (Render URL may differ from last deploy)
            wh_url = f"{settings.RENDER_EXTERNAL_URL}/webhook/{clone['bot_id']}"
            await clone_app.bot.set_webhook(url=wh_url, drop_pending_updates=False)
            await db_ops_bots.update_bot_status(pool, clone["bot_id"], "active", webhook_active=True)

            await registry_register(clone["bot_id"], clone_app)
            logger.info(f"[STARTUP]   ✅ Recovered @{clone['username']} (id={clone['bot_id']})")
            recovered += 1

            # No music worker for clone bots - music is handled by separate music_service.py

        except Exception as e:
            await db_ops_bots.update_bot_status(
                pool, clone["bot_id"], "dead",
                death_reason=str(e), webhook_active=False
            )
            logger.warning(f"[STARTUP]   ❌ Dead clone @{clone['username']} (id={clone['bot_id']}): {e}")
            dead += 1

    logger.info(f"[STARTUP] Recovery complete | recovered={recovered} | dead={dead}")
    logger.info(f"[STARTUP] Total bots in registry: {registry_get_all().__len__()}")
    logger.info("=" * 60)

    # Start scheduled post runner
    from bot.tasks.scheduler import scheduled_post_runner
    asyncio.create_task(scheduled_post_runner(pool, registry_get))

    # Start Nexus scheduler (repeat messages + silent times)
    try:
        from bot.scheduler.engine import NexusScheduler
        nexus_scheduler = NexusScheduler(bot=primary_app.bot, db=pool)
        await nexus_scheduler.start()
        logger.info("[STARTUP] ✅ NexusScheduler started")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ NexusScheduler failed to start: {e}")

    # Start broadcast worker
    try:
        from bot.utils.broadcast_engine import BroadcastEngine
        import bot.utils.broadcast_engine
        b_engine = BroadcastEngine(pool)
        bot.utils.broadcast_engine.broadcast_engine = b_engine
        
        async def broadcast_worker():
            from db.ops.broadcast import get_pending_broadcast_tasks
            while True:
                try:
                    tasks = await get_pending_broadcast_tasks(pool)
                    for t in tasks:
                        await b_engine.start_broadcast(t['id'])
                except Exception as e:
                    logger.error(f"[STARTUP] Broadcast worker error: {e}")
                await asyncio.sleep(30)
        
        asyncio.create_task(broadcast_worker())
        logger.info("[STARTUP] ✅ Broadcast worker started")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Broadcast worker failed to start: {e}")

    yield

    # Shutdown
    logger.info("[SHUTDOWN] Stopping all bots...")
    for bot_id, ptb_app in registry_get_all().items():
        try:
            await ptb_app.stop()
            await ptb_app.shutdown()
            logger.info(f"[SHUTDOWN] Stopped bot_id={bot_id}")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error stopping bot_id={bot_id}: {e}")
    await db.disconnect()
    logger.info("[SHUTDOWN] Complete")

fastapi_app = FastAPI(title="Nexus Bot API", lifespan=lifespan)

# Add GZip compression for responses > 1KB to reduce bandwidth
fastapi_app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,  # Only compress responses larger than 1KB
    compresslevel=6,    # Good balance between speed and compression
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from api.routes import groups, members, debug, bots, music, modules, analytics, channels, text_config, me, member_stats, events, bots_messages, broadcast
from api.routes.reports import router as reports_router
from api.routes.boost import router as boost_router
from api.routes.channel_gate import router as channel_gate_router
from api.routes.messages import router as messages_router
from api.routes.music_auth import router as music_auth_router
from api.routes.auth import router as auth_router
from api.routes.admin import router as admin_router
from api.routes.billing import router as billing_router
from api.routes import automod as automod_router
from api.routes.scheduler import router as scheduler_router
from api.routes.log_channel import router as log_channel_router
from api.routes.webhooks import router as webhooks_router

fastapi_app.include_router(groups.router)
fastapi_app.include_router(members.router)
fastapi_app.include_router(debug.router)
fastapi_app.include_router(bots.router)
fastapi_app.include_router(bots_messages.router)
fastapi_app.include_router(music.router)
fastapi_app.include_router(modules.router)
fastapi_app.include_router(analytics.router)
fastapi_app.include_router(channels.router)
fastapi_app.include_router(text_config.router)
fastapi_app.include_router(boost_router)
fastapi_app.include_router(channel_gate_router)
fastapi_app.include_router(me.router)
fastapi_app.include_router(member_stats.router)
fastapi_app.include_router(messages_router)
fastapi_app.include_router(music_auth_router)
fastapi_app.include_router(auth_router)
fastapi_app.include_router(admin_router)
fastapi_app.include_router(billing_router)
fastapi_app.include_router(events.router)
fastapi_app.include_router(broadcast.router)
fastapi_app.include_router(automod_router.router)
fastapi_app.include_router(scheduler_router)
fastapi_app.include_router(log_channel_router)
fastapi_app.include_router(reports_router)
fastapi_app.include_router(webhooks_router)

# Serve miniapp static files
miniapp_dir = os.path.join(os.path.dirname(__file__), "miniapp")
if os.path.exists(miniapp_dir):
    fastapi_app.mount("/miniapp", StaticFiles(directory=miniapp_dir, html=True), name="miniapp")

# Serve webapp static files (for legacy React version)
webapp_dir = os.path.join(os.path.dirname(__file__), "webapp")
if os.path.exists(webapp_dir):
    fastapi_app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")


@fastapi_app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon - redirect to miniapp icon if available."""
    favicon_path = os.path.join(os.path.dirname(__file__), "miniapp", "favicon.ico")
    if os.path.exists(favicon_path):
        return RedirectResponse(url="/miniapp/favicon.ico")
    return Response(status_code=204)  # No content


@fastapi_app.get("/", response_class=JSONResponse)
async def health():
    db_status = "connected" if (db.pool) else "disconnected"
    return {
        "status": "ok",
        "bots": len(registry_get_all()),
        "db": db_status,
        "ready": db.pool is not None
    }


@fastapi_app.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    """Serve the Mini App HTML."""
    return RedirectResponse(url="/webapp/")


@fastapi_app.get("/miniapp", response_class=HTMLResponse)
async def serve_miniapp(request: Request):
    """New Vanilla JS Mini App entry point — redirect to trailing slash version."""
    query_params = str(request.query_params)
    url = "/miniapp/"
    if query_params:
        url += f"?{query_params}"
    return RedirectResponse(url=url)


@fastapi_app.get("/miniapp/", response_class=HTMLResponse)
async def serve_miniapp_index():
    """Serve miniapp index.html with no-cache headers (trailing slash)."""
    html_path = os.path.join(os.path.dirname(__file__), "miniapp", "index.html")
    if os.path.exists(html_path):
        from fastapi.responses import FileResponse
        return FileResponse(
            html_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma":        "no-cache",
                "Expires":       "0",
            }
        )
    return HTMLResponse("<h1>Mini App not found</h1>", status_code=404)


@fastapi_app.get("/miniapp-react", response_class=HTMLResponse)
async def serve_miniapp_react():
    """Legacy React Mini App entry point."""
    return await serve_webapp()


@fastapi_app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy_policy():
    """Serve the Privacy Policy HTML page."""
    import os
    privacy_path = os.path.join(os.path.dirname(__file__), "PRIVACY_POLICY.html")
    if os.path.exists(privacy_path):
        with open(privacy_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        # Fallback to markdown version
        privacy_md_path = os.path.join(os.path.dirname(__file__), "PRIVACY_POLICY.md")
        if os.path.exists(privacy_md_path):
            with open(privacy_md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            # Simple markdown to HTML conversion
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Privacy Policy - Nexus Bot</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
                    pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                    code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
                </style>
            </head>
            <body>
                <h1>Privacy Policy</h1>
                <pre>{md_content}</pre>
            </body>
            </html>
            """
            return html_content
    return "Privacy Policy not found. Please contact support@nexus-bot.com"


@fastapi_app.post("/webhook/{bot_id}")
async def webhook(bot_id: int, request: Request):
    """
    Receives all Telegram updates for all bots.
    Routes each update to the correct PTB Application by bot_id.
    ALWAYS returns HTTP 200 — non-200 causes Telegram to retry indefinitely.
    """
    import httpx
    start_ms = time.monotonic() * 1000

    # Validate bot_id - reject obviously invalid IDs like 0
    if bot_id == 0:
        logger.error(
            f"[WEBHOOK] Received webhook for invalid bot_id=0. "
            f"This usually means the bot token is invalid or the webhook was misconfigured. "
            f"Please check the PRIMARY_BOT_TOKEN environment variable and ensure the webhook is set correctly."
        )
        return {"ok": True, "note": "invalid_bot_id_zero"}

    ptb_app = registry_get(bot_id)

    if not ptb_app:
        logger.warning(
            f"[WEBHOOK] Update for unregistered bot | bot_id={bot_id} | "
            f"registered_bots={list(registry_get_all().keys())}"
        )
        return {"ok": True, "note": "bot_not_registered"}

    try:
        body = await request.json()
        update = Update.de_json(body, ptb_app.bot)

        logger.debug(
            f"[WEBHOOK] Received | bot_id={bot_id} | "
            f"update_id={update.update_id} | "
            f"type={_get_update_type(update)}"
        )

        # Touch last_seen in background — never block update processing
        asyncio.create_task(
            db_ops_bots.update_bot_last_seen(db.pool, bot_id)
        )

        await ptb_app.process_update(update)

        duration = (time.monotonic() * 1000) - start_ms
        logger.debug(f"[WEBHOOK] Processed | bot_id={bot_id} | duration={duration:.1f}ms")

        return {"ok": True}

    except Exception as e:
        logger.error(
            f"[WEBHOOK] Processing error | bot_id={bot_id} | error={e}",
            exc_info=True
        )
        return {"ok": True}  # Still 200 — never let Telegram retry


def _get_update_type(update: Update) -> str:
    if update.message:
        user_id = update.message.from_user.id if update.message.from_user else "unknown"
        return f"message from user_id={user_id}"
    if update.callback_query:
        return f"callback from user_id={update.callback_query.from_user.id}"
    if update.chat_member:
        return "chat_member"
    return "unknown"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=settings.PORT)


app = fastapi_app
