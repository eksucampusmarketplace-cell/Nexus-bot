import os
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from config import settings
from db.client import db
from bot.factory import create_bot_app
from api.routes import groups, members, debug
import hashlib

# Validate settings before starting
settings.validate_required_settings()

# Structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

bot_apps = []
db_available = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_available
    
    # STARTUP
    try:
        await db.connect()
        db_available = True
        logger.info("Database connection established successfully")
    except Exception as e:
        db_available = False
        logger.error(f"Failed to connect to database: {e}")
        logger.error("Application will start without database functionality")
        # Don't raise - allow the app to start for health checks
    
    # Only start bots if database is available
    if db_available:
        tokens = settings.all_tokens
        for i, token in enumerate(tokens):
            try:
                bot_app = create_bot_app(token)
                await bot_app.initialize()
                await bot_app.start()
                
                # Set webhook
                webhook_path = f"/webhook/{i}"
                webhook_url = f"{settings.webhook_url}{webhook_path}"
                await bot_app.bot.set_webhook(url=webhook_url)
                logger.info(f"Bot {i} webhook set to {webhook_url}")
                
                bot_apps.append(bot_app)
                
                # Verify bot
                me = await bot_app.bot.get_me()
                logger.info(f"Bot {i} started as @{me.username}")
            except Exception as e:
                logger.error(f"Failed to start bot {i}: {e}")
    else:
        logger.warning("Skipping bot initialization due to database unavailability")

    yield
    # SHUTDOWN
    for bot_app in bot_apps:
        await bot_app.stop()
        await bot_app.shutdown()
    await db.disconnect()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(groups.router)
app.include_router(members.router)
app.include_router(debug.router)

@app.get("/", response_class=JSONResponse)
async def health():
    db_status = "connected" if (db.pool and db_available) else "disconnected"
    return {
        "status": "ok",
        "bots": len(bot_apps),
        "db": db_status,
        "ready": db_available
    }

@app.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    with open("webapp/index.html", "r") as f:
        return f.read()

@app.post("/webhook/{bot_index}")
async def telegram_webhook(bot_index: int, request: Request):
    if bot_index >= len(bot_apps):
        return Response(status_code=404)
    
    data = await request.json()
    from telegram import Update
    update = Update.de_json(data, bot_apps[bot_index].bot)
    await bot_apps[bot_index].process_update(update)
    return Response(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
