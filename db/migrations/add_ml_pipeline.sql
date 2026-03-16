-- Migration: add_ml_pipeline.sql
-- Goal: Phase 1 tables for ML analytics and signal collection

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

CREATE TABLE IF NOT EXISTS user_risk_scores (
    user_id      BIGINT PRIMARY KEY,
    risk_score   INT DEFAULT 0,
    -- 0-100. >70=flag, >90=auto-action
    last_scored  TIMESTAMPTZ DEFAULT NOW(),
    score_breakdown JSONB,
    -- {account_age:30, no_photo:20, ban_history:40, ...}
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

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
CREATE INDEX IF NOT EXISTS idx_daily_chat ON bot_stats_daily(chat_id, day DESC);
