-- Migration: Games Expansion (Sounds, New Games, Stats, Improvements)

-- Daily challenge tracking
CREATE TABLE IF NOT EXISTS daily_challenges (
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    date DATE NOT NULL,
    game_type TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    streak INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, chat_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_challenges_date ON daily_challenges(date);
CREATE INDEX IF NOT EXISTS idx_daily_challenges_user ON daily_challenges(user_id, chat_id);

-- Would you rather choices
CREATE TABLE IF NOT EXISTS wyr_choices (
    question_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,
    choice INTEGER NOT NULL, -- 1 or 2
    chat_id BIGINT NOT NULL,
    chosen_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (question_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_wyr_choices_question ON wyr_choices(question_id);
CREATE INDEX IF NOT EXISTS idx_wyr_choices_chat ON wyr_choices(chat_id);

-- Game high scores
CREATE TABLE IF NOT EXISTS game_scores (
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    game_type TEXT NOT NULL,
    high_score INTEGER DEFAULT 0,
    total_plays INTEGER DEFAULT 0,
    last_played TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, chat_id, game_type)
);

CREATE INDEX IF NOT EXISTS idx_game_scores_chat ON game_scores(chat_id, game_type, high_score DESC);
CREATE INDEX IF NOT EXISTS idx_game_scores_user ON game_scores(user_id);

-- Bot usage stats (daily aggregation)
CREATE TABLE IF NOT EXISTS bot_stats_daily (
    date DATE NOT NULL,
    bot_id BIGINT NOT NULL,
    commands_count INTEGER DEFAULT 0,
    music_plays INTEGER DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    new_groups INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    PRIMARY KEY (date, bot_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_stats_date ON bot_stats_daily(date DESC);
CREATE INDEX IF NOT EXISTS idx_bot_stats_bot ON bot_stats_daily(bot_id);

-- Onboarding tracking
ALTER TABLE groups ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS onboarding_step INTEGER DEFAULT 0;

-- Welcome message with media
ALTER TABLE groups ADD COLUMN IF NOT EXISTS welcome_media_file_id TEXT;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS welcome_media_type TEXT; -- 'photo', 'video', 'animation', 'sticker'

-- Auto-delete messages
ALTER TABLE groups ADD COLUMN IF NOT EXISTS auto_delete_seconds INTEGER DEFAULT 0;

-- Broadcast with media
ALTER TABLE broadcast_tasks ADD COLUMN IF NOT EXISTS media_file_id TEXT;
ALTER TABLE broadcast_tasks ADD COLUMN IF NOT EXISTS media_type TEXT; -- 'photo', 'video', 'animation'

-- Warning system improvements
-- First ensure the warnings table exists (for new installations)
CREATE TABLE IF NOT EXISTS warnings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    reason TEXT,
    by_user_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_expired BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_warnings_user_chat ON warnings(user_id, chat_id);

-- Add columns if they don't exist
ALTER TABLE warnings ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE warnings ADD COLUMN IF NOT EXISTS is_expired BOOLEAN DEFAULT FALSE;

-- Music vote skip
ALTER TABLE music_settings ADD COLUMN IF NOT EXISTS vote_skip_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE music_settings ADD COLUMN IF NOT EXISTS vote_skip_threshold INTEGER DEFAULT 51;

-- Group settings backup/restore tracking
ALTER TABLE groups ADD COLUMN IF NOT EXISTS last_backup_at TIMESTAMPTZ;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS backup_count INTEGER DEFAULT 0;

-- Command usage tracking for stats
CREATE TABLE IF NOT EXISTS command_usage (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    bot_id BIGINT NOT NULL,
    command TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    used_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_command_usage_date ON command_usage(date, bot_id, command);
CREATE INDEX IF NOT EXISTS idx_command_usage_chat ON command_usage(chat_id);

-- Comments
COMMENT ON TABLE daily_challenges IS 'Tracks user daily challenge completions and streaks';
COMMENT ON TABLE wyr_choices IS 'Tracks Would You Rather user choices for percentage calculation';
COMMENT ON TABLE game_scores IS 'High scores per user per game type per group';
COMMENT ON TABLE bot_stats_daily IS 'Daily aggregated statistics per bot';
COMMENT ON TABLE command_usage IS 'Individual command invocations for detailed stats';
