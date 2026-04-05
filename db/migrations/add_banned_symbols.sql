-- File: db/migrations/add_banned_symbols.sql
--
-- Creates tables for banned symbols (for username filtering)
-- This is an UltraPro feature available for Pro and Unlimited plans

-- Banned symbols for username filtering
CREATE TABLE IF NOT EXISTS banned_symbols (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT DEFAULT 'ban',
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, symbol)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_banned_symbols_chat ON banned_symbols(chat_id);

-- Banned symbol matches log (for audit)
CREATE TABLE IF NOT EXISTS banned_symbol_matches (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    matched_symbol TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    matched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_banned_symbol_matches_chat ON banned_symbol_matches(chat_id);
CREATE INDEX IF NOT EXISTS idx_banned_symbol_matches_user ON banned_symbol_matches(user_id);
