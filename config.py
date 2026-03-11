import os
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
