-- ── Per-Bot Group Settings ────────────────────────────────────────────────────
-- Each bot can have its own settings for a group independently of other bots.
-- This prevents settings from syncing between the main bot and clone bots
-- that are both present in the same group.
-- IDEMPOTENT - safe to run multiple times

CREATE TABLE IF NOT EXISTS bot_group_settings (
    bot_token_hash  TEXT        NOT NULL,
    chat_id         BIGINT      NOT NULL,
    settings        JSONB       DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (bot_token_hash, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_group_settings_chat
    ON bot_group_settings(chat_id);
