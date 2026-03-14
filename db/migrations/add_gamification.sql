-- Gamification system: XP, levels, badges, streaks
-- Run this migration to add gamification columns to users table

ALTER TABLE users ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS badges JSONB DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_days INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_date DATE;

-- XP thresholds view for efficient leaderboard queries
CREATE OR REPLACE VIEW user_levels AS
SELECT 
    user_id, 
    chat_id, 
    first_name, 
    username,
    xp, 
    level,
    (xp - (level * level * 100)) AS xp_in_level,
    ((level+1) * (level+1) * 100 - level * level * 100) AS xp_needed
FROM users;

-- Index for fast leaderboard queries
CREATE INDEX IF NOT EXISTS idx_users_xp ON users(chat_id, xp DESC);
CREATE INDEX IF NOT EXISTS idx_users_level ON users(chat_id, level DESC);
