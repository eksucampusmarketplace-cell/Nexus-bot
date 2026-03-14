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
        logger.info("[STARTUP] ✅ Redis connected")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Failed to connect to Redis: {e}")
        redis_client = None

    # Primary bot
    primary_token = settings.PRIMARY_BOT_TOKEN

    # Validate token format before attempting to initialize
    token_pattern = r"^\d{8,12}:[\w-]{35,50}$"
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

        logger.info("[STARTUP] Initializing primary bot...")
        await primary_app.initialize()
        logger.info("[STARTUP] Starting primary bot...")
        await primary_app.start()

        # Brief pause to ensure bot is fully ready
        await asyncio.sleep(0.5)

        # Verify bot is properly initialized
        logger.info("[STARTUP] Fetching bot information from Telegram...")
        try:
            primary_me = await primary_app.bot.get_me()
        except AttributeError:
            primary_me = primary_app.bot.get_me()

        if not primary_me or primary_me.id == 0:
            raise ValueError("Bot initialization failed: get_me() returned invalid bot object.")

        logger.info(
            f"[STARTUP] ✅ Primary bot @{primary_me.username} (ID: {primary_me.id}) is online"
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
        )
        await registry_register(primary_me.id, primary_app)

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
                logger.info(f"[STARTUP] ✅ Started clone bot @{me.username} (ID: {me.id})")
            except Exception as ce:
                logger.error(f"[STARTUP] ⚠️ Failed to start clone {clone_row['bot_id']}: {ce}")
                continue
    except Exception as e:
        logger.error(f"[STARTUP] ❌ Failed to load clones: {e}")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/miniapp/index.html")


# Bot webhooks
@app.post("/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, request: Request):
    target_app = None
    for app in registry_get_all().values():
        if app.bot.token == bot_token:
            target_app = app
            break

    # Fallback: try matching by bot_id (for webhooks set with bot_id only)
    if not target_app:
        try:
            bot_id = int(bot_token)
            target_app = registry_get(bot_id)
        except ValueError:
            pass

    if not target_app:
        logger.warning(f"[WEBHOOK] No bot found for token/bot_id: {bot_token[:10]}...")
        return Response(status_code=404)

    data = await request.json()
    update = Update.de_json(data, target_app.bot)
    await target_app.process_update(update)
    return Response(status_code=200)


# Serve Mini App static files
miniapp_path = os.path.join(os.path.dirname(__file__), "miniapp")
if os.path.exists(miniapp_path):
    app.mount("/miniapp", StaticFiles(directory=miniapp_path, html=True), name="miniapp")

# Import and include API routers
try:
    from api.routes import (
        auth,
        automod,
        bots,
        broadcast,
        channel_gate,
        channels,
        engagement,
        events,
        events_new,
        games,
        groups,
        log_channel,
        me,
        member_stats,
        members,
        messages,
    )
    from api.routes import moderation as moderation_api
    from api.routes import (
        modules,
        reports,
        roles,
        scheduler,
        text_config,
        webhooks,
    )

    # Core API routers (need prefix since routes don't include it)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
    app.include_router(bots.router, prefix="/api/bots", tags=["bots"])

    # Routes with full paths defined in the router (no prefix needed)
    app.include_router(automod.router, tags=["automod"])
    app.include_router(events.router, tags=["events"])
    app.include_router(events_new.router, tags=["events_new"])
    app.include_router(scheduler.router, tags=["scheduler"])
    app.include_router(log_channel.router, tags=["log_channel"])
    app.include_router(moderation_api.router, tags=["moderation"])

    # Routes that need prefix
    app.include_router(me.router, prefix="/api/me", tags=["me"])

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
    app.include_router(channel_gate.router)  # prefix="/api/groups/{chat_id}/channel-gate"

    # Other routes with internal prefixes
    app.include_router(broadcast.router)  # prefix="/api/broadcast"
    app.include_router(channels.router)  # prefix="/api/channels"
    app.include_router(member_stats.router)  # prefix="/api/me"
except ImportError as e:
    logger.warning(f"Failed to load API routers: {e}")
