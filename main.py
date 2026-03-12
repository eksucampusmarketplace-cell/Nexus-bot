import os
import logging
import sys
import asyncio
import time
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update

from config import settings
from db.client import db
from bot.factory import create_application
from bot.registry import register as registry_register, get as registry_get, get_all as registry_get_all, get_summary
from bot.utils.crypto import encrypt_token, hash_token, decrypt_token
import db.ops.bots as db_ops_bots

# Validate settings before starting
settings.validate_required_settings()

# Structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%%Y-%%m-%%d %%H:%%M:%%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

fastapi_app = FastAPI(title="Nexus Bot API")

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    # Primary bot
    primary_token = settings.PRIMARY_BOT_TOKEN
    primary_app = create_application(primary_token, is_primary=True)
    primary_app.bot_data["db_pool"] = pool

    await primary_app.initialize()
    await primary_app.start()
    primary_me = await primary_app.bot.get_me()

    primary_webhook = f"{settings.RENDER_EXTERNAL_URL}/webhook/{primary_me.id}"
    await primary_app.bot.set_webhook(
        url=primary_webhook,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

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

    # Recover clones
    active_clones = await db_ops_bots.get_all_active_bots(pool)
    # Filter out primary from clone recovery
    clones_only = [c for c in active_clones if not c["is_primary"]]

    logger.info(f"[STARTUP] Recovering {len(clones_only)} clone(s)...")
    recovered = dead = 0

    for clone in clones_only:
        try:
            token = decrypt_token(clone["token_encrypted"])

            # Verify token still valid
            async with httpx.AsyncClient(timeout=8.0) as client:
                me_resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                me_data = me_resp.json()

            if not me_data.get("ok"):
                raise ValueError(f"Token rejected: {me_data.get('description')}")

            clone_app = create_application(token, is_primary=False)
            clone_app.bot_data["db_pool"] = pool
            await clone_app.initialize()
            await clone_app.start()

            # Re-register webhook (Render URL may differ from last deploy)
            wh_url = f"{settings.RENDER_EXTERNAL_URL}/webhook/{clone['bot_id']}"
            await clone_app.bot.set_webhook(url=wh_url, drop_pending_updates=False)
            await db_ops_bots.update_bot_status(pool, clone["bot_id"], "active", webhook_active=True)

            await registry_register(clone["bot_id"], clone_app)
            logger.info(f"[STARTUP]   ✅ Recovered @{clone['username']} (id={clone['bot_id']})")
            recovered += 1

        except Exception as e:
            await db_ops_bots.update_bot_status(
                pool, clone["bot_id"], "dead",
                death_reason=str(e), webhook_active=False
            )
            logger.warning(f"[STARTUP]   ❌ Dead clone @{clone['username']} (id={clone['bot_id']}): {e}")
            dead += 1

    logger.info(f"[STARTUP] Recovery complete | recovered={recovered} | dead={dead}")
    logger.info(f"[STARTUP] Total bots in registry: {registry_register.__self__.count() if hasattr(registry_register, '__self__') else 'N/A'}")
    logger.info("=" * 60)

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


# Routes
from api.routes import groups, members, debug, bots, music

fastapi_app.include_router(groups.router)
fastapi_app.include_router(members.router)
fastapi_app.include_router(debug.router)
fastapi_app.include_router(bots.router)
fastapi_app.include_router(music.router)


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
    with open("webapp/index.html", "r") as f:
        return f.read()


@fastapi_app.post("/webhook/{bot_id}")
async def webhook(bot_id: int, request: Request):
    """
    Receives all Telegram updates for all bots.
    Routes each update to the correct PTB Application by bot_id.
    ALWAYS returns HTTP 200 — non-200 causes Telegram to retry indefinitely.
    """
    import httpx
    start_ms = time.monotonic() * 1000

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
