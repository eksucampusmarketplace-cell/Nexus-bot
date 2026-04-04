-- Add trust_score column to users table for TrustNet
-- Used by bot/utils/trust_score.py for per-user trust calculation

ALTER TABLE users ADD COLUMN IF NOT EXISTS trust_score INTEGER DEFAULT 50;

CREATE INDEX IF NOT EXISTS idx_users_trust_score ON users(trust_score);
CREATE INDEX IF NOT EXISTS idx_users_trust_chat ON users(chat_id, trust_score DESC);
