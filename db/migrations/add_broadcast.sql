-- Track users who PM the bot
CREATE TABLE IF NOT EXISTS bot_pms (
    bot_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (bot_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_pms_bot ON bot_pms(bot_id);

-- Track broadcast tasks
CREATE TABLE IF NOT EXISTS broadcast_tasks (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,      -- user_id of the person who started it
    bot_id BIGINT NOT NULL,        -- which bot is sending (primary or clone)
    target_type TEXT NOT NULL,     -- 'pms', 'groups', 'all'
    content TEXT NOT NULL,
    media_file_id TEXT,
    media_type TEXT,               -- photo | video | animation | document
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'paused', 'failed', 'cancelled'
    total_targets INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_broadcast_tasks_bot ON broadcast_tasks(bot_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_tasks_status ON broadcast_tasks(status) WHERE status IN ('pending', 'running');
