import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    PRIMARY_BOT_TOKEN: str
    CLONE_TOKENS: Optional[str] = ""
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_CONNECTION_STRING: str  # For asyncpg
    OWNER_ID: Optional[int] = None
    SKIP_AUTH: bool = False
    DEBUG: bool = False
    PORT: int = 8000
    RENDER_EXTERNAL_URL: Optional[str] = None
    CLONE_ACCESS: str = "owner_only"  # owner_only | anyone
    SECRET_KEY: Optional[str] = None  # Fernet key for token encryption
    SUPPORT_GROUP_URL: Optional[str] = None  # Optional support group link for the Mini App
    
    # ── Bot Display & Support ────────────────────────────────────────────────
    BOT_DISPLAY_NAME: str = "Nexus"  # Displayed in "Powered by {bot_name}"
    MAIN_BOT_USERNAME: str = "NexusBot"  # Username for support redirects
    SUPPORT_GROUP_ID: int = 0  # Internal alerts group (0 = disabled)
    DOCS_URL: Optional[str] = None  # Documentation link for help messages
    MINI_APP_URL: Optional[str] = None  # Base URL for the Mini App (if not set, defaults to RENDER_EXTERNAL_URL/webapp)
    
    # ── Alert Settings ────────────────────────────────────────────────────────
    ALERT_ON_ERRORS: bool = True  # Post errors to support group
    ALERT_ON_NEW_CLONES: bool = True  # Post new clone registrations
    ALERT_ON_DEAD_CLONES: bool = True  # Post when clone token becomes invalid

    # ── Music Settings ───────────────────────────────────────────────────────
    MUSIC_WORKER_COUNT: int = 1
    # How many userbot accounts the MAIN BOT uses for music
    # Each account can stream in multiple groups via PyTGCalls
    # Clone bots always use exactly 1 (their own account)

    MUSIC_MAX_QUEUE: int = 50
    MUSIC_MAX_DURATION: int = 3600  # seconds — reject tracks over 1hr
    MUSIC_IDLE_TIMEOUT: int = 180  # seconds — leave VC after idle
    MUSIC_DEFAULT_VOLUME: int = 100  # 0–200
    MUSIC_DOWNLOAD_DIR: str = "/tmp/nexus_music"
    # Temp dir for downloaded audio before streaming
    # Files deleted immediately after streaming begins

    # Pyrogram API credentials for userbot authentication
    PYROGRAM_API_ID: Optional[int] = None
    PYROGRAM_API_HASH: Optional[str] = None

    # ── Redis & Music Service ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    MUSIC_JOB_TTL: int = 3600  # seconds
    MUSIC_SERVICE_TIMEOUT: int = 10  # seconds
    MUSIC_MAX_RETRIES: int = 3
    MUSIC_YTDLP_VERSION: str = "2024.3.10"

    # ── Memory Management ──────────────────────────────────────────────────
    PYROGRAM_MAX_ACTIVE: int = 10
    LAZY_UNLOAD_TIMEOUT: int = 1800
    MEMORY_WARN_MB: int = 800
    MEMORY_CRITICAL_MB: int = 1200

    # ── Stars Economy ──────────────────────────────────────────────────────
    REFERRAL_BONUS_STARS: int = 100
    REFERRAL_REFERRED_BONUS: int = 50

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def validate_required_settings(self):
        """Validate that all required settings are properly configured."""
        missing = []
        
        if not self.PRIMARY_BOT_TOKEN or self.PRIMARY_BOT_TOKEN == "your_primary_token":
            missing.append("PRIMARY_BOT_TOKEN")
        
        if not self.SUPABASE_URL or self.SUPABASE_URL == "your_supabase_url":
            missing.append("SUPABASE_URL")
        
        if not self.SUPABASE_SERVICE_KEY or self.SUPABASE_SERVICE_KEY == "your_supabase_service_key":
            missing.append("SUPABASE_SERVICE_KEY")
        
        if not self.SUPABASE_CONNECTION_STRING or "your" in self.SUPABASE_CONNECTION_STRING.lower():
            missing.append("SUPABASE_CONNECTION_STRING")
        
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            missing.append("SECRET_KEY")
        
        if missing:
            print("=" * 60, file=sys.stderr)
            print("ERROR: Missing or invalid required environment variables:", file=sys.stderr)
            for var in missing:
                print(f"  - {var}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("\nPlease set these environment variables in your Render dashboard:", file=sys.stderr)
            print("  1. Go to your Render dashboard", file=sys.stderr)
            print("  2. Select your web service", file=sys.stderr)
            print("  3. Go to Environment tab", file=sys.stderr)
            print("  4. Add the required environment variables", file=sys.stderr)
            print("\nSee README.md for setup instructions.", file=sys.stderr)
            sys.exit(1)

    @property
    def all_tokens(self) -> List[str]:
        tokens = [self.PRIMARY_BOT_TOKEN]
        if self.CLONE_TOKENS:
            tokens.extend([t.strip() for t in self.CLONE_TOKENS.split(",") if t.strip()])
        return tokens

    @property
    def webhook_url(self) -> str:
        if not self.RENDER_EXTERNAL_URL:
            return f"http://localhost:{self.PORT}"
        return self.RENDER_EXTERNAL_URL.rstrip("/")
    
    @property
    def mini_app_url(self) -> Optional[str]:
        """Get Mini App URL - uses MINI_APP_URL if set, otherwise constructs from RENDER_EXTERNAL_URL."""
        if self.MINI_APP_URL:
            return self.MINI_APP_URL
        if self.RENDER_EXTERNAL_URL:
            return f"{self.RENDER_EXTERNAL_URL.rstrip('/')}/webapp"
        return None

settings = Settings()
