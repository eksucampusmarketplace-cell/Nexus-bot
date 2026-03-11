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

settings = Settings()
