-- Migration: add_ml_pipeline.sql
-- Goal: Phase 1 tables for ML analytics and signal collection
-- v22 FIX: Made idempotent with column existence checks for existing bot_stats_daily tables

-- spam_signals table - new in v22
CREATE TABLE IF NOT EXISTS spam_signals (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    chat_id      BIGINT NOT NULL,
    message_text TEXT,
    signal_type  TEXT NOT NULL,
    -- 'community_vote' | 'fed_ban' | 'pattern_match' | 'mod_action' | 'risk_score' | 'ml_classifier'
    label        TEXT NOT NULL,
    -- 'spam' | 'ham' | 'uncertain'
    confidence   FLOAT DEFAULT 1.0,
    -- 1.0 = certain, 0.5 = uncertain
    metadata     JSONB,
    -- extra context: {scam_type, vote_count, action_type, ...}
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_spam_signals_label ON spam_signals(label, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spam_signals_user  ON spam_signals(user_id);

-- user_risk_scores table - new in v22
CREATE TABLE IF NOT EXISTS user_risk_scores (
    user_id      BIGINT PRIMARY KEY,
    risk_score   INT DEFAULT 0,
    -- 0-100. >70=flag, >90=auto-action
    last_scored  TIMESTAMPTZ DEFAULT NOW(),
    score_breakdown JSONB,
    -- {account_age:30, no_photo:20, ban_history:40, ...}
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- bot_stats_hourly table - new in v22
CREATE TABLE IF NOT EXISTS bot_stats_hourly (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    hour         TIMESTAMPTZ NOT NULL,
    message_count INT DEFAULT 0,
    spam_detected INT DEFAULT 0,
    members_joined INT DEFAULT 0,
    members_left   INT DEFAULT 0,
    bans_issued    INT DEFAULT 0,
    warns_issued   INT DEFAULT 0,
    UNIQUE(chat_id, hour)
);
CREATE INDEX IF NOT EXISTS idx_hourly_chat ON bot_stats_hourly(chat_id, hour DESC);

-- bot_stats_daily - may already exist from add_games_expansion.sql with (date, bot_id) schema
-- v22 FIX: Use ALTER TABLE ADD COLUMN IF NOT EXISTS instead of CREATE TABLE
-- to avoid conflicts with existing tables that have different columns

-- First create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS bot_stats_daily (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    day          DATE NOT NULL,
    message_count INT DEFAULT 0,
    spam_detected INT DEFAULT 0,
    members_joined INT DEFAULT 0,
    members_left   INT DEFAULT 0,
    bans_issued    INT DEFAULT 0,
    warns_issued   INT DEFAULT 0,
    top_spammer_user_ids BIGINT[],
    most_active_hour INT,
    churn_rate   FLOAT DEFAULT 0.0,
    UNIQUE(chat_id, day)
);

-- Add columns if they don't exist (for tables created by older migrations with different schema)
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS day DATE;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS message_count INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS spam_detected INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS members_joined INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS members_left INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS bans_issued INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS warns_issued INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS top_spammer_user_ids BIGINT[];
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS most_active_hour INT;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS churn_rate FLOAT DEFAULT 0.0;

-- Also ensure legacy columns exist for backward compatibility
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS date DATE;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS bot_id BIGINT;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS commands_count INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS music_plays INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS games_played INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS new_groups INT DEFAULT 0;
ALTER TABLE bot_stats_daily ADD COLUMN IF NOT EXISTS active_users INT DEFAULT 0;

-- Create index ONLY if chat_id column exists (guarded by DO $$ block)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'bot_stats_daily' AND column_name = 'chat_id') THEN
        CREATE INDEX IF NOT EXISTS idx_daily_chat ON bot_stats_daily(chat_id, day DESC);
    END IF;
END $$;

-- Create legacy indexes if those columns exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'bot_stats_daily' AND column_name = 'date') THEN
        CREATE INDEX IF NOT EXISTS idx_bot_stats_date ON bot_stats_daily(date DESC);
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'bot_stats_daily' AND column_name = 'bot_id') THEN
        CREATE INDEX IF NOT EXISTS idx_bot_stats_bot ON bot_stats_daily(bot_id);
    END IF;
END $$;
