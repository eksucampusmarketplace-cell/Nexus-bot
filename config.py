import sys
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    MAIN_BOT_USERNAME: str = (
        ""  # Username for support redirects (auto-detected on startup if empty)
    )
    SUPPORT_GROUP_ID: int = 0  # Internal alerts channel (0 = disabled)
    DOCS_URL: Optional[str] = None  # Documentation link for help messages
    MINI_APP_URL: Optional[str] = (
        None  # Base URL for the Mini App (if not set, defaults to RENDER_EXTERNAL_URL/miniapp)
    )
    PRIVACY_POLICY_URL: Optional[str] = (
        None  # Link to Privacy Policy (if not set, uses GitHub/inline)
    )

    # ── Alert Settings ────────────────────────────────────────────────────────
    ALERT_ON_ERRORS: bool = True  # Post errors to support group
    ALERT_ON_NEW_CLONES: bool = True  # Post new clone registrations
    ALERT_ON_DEAD_CLONES: bool = True  # Post when clone token becomes invalid

    # ── Redis Configuration ──────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Memory Management ──────────────────────────────────────────────────
    MEMORY_WARN_MB: int = 800
    MEMORY_CRITICAL_MB: int = 1200

    # ── Telegram MTProto API (for session generator) ──────────────────────
    TG_API_ID: Optional[int] = None  # From my.telegram.org/apps
    TG_API_HASH: Optional[str] = None  # From my.telegram.org/apps

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

        if (
            not self.SUPABASE_SERVICE_KEY
            or self.SUPABASE_SERVICE_KEY == "your_supabase_service_key"
        ):
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
            print(
                "\nPlease set these environment variables in your Render dashboard:",
                file=sys.stderr,
            )
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
            base = self.MINI_APP_URL
        elif self.RENDER_EXTERNAL_URL:
            base = f"{self.RENDER_EXTERNAL_URL.rstrip('/')}/miniapp"
        else:
            return None
        return self._append_version(base)

    def _append_version(self, url: str) -> str:
        """Append a cache-busting version param using RENDER_GIT_COMMIT or a static marker."""
        import os as _os

        commit = _os.environ.get("RENDER_GIT_COMMIT", "")
        version = commit[:8] if commit else "1"
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}v={version}"


settings = Settings()
