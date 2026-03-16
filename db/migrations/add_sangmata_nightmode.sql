-- ============================================
-- Sangmata (Name History) + Night Mode Migration v21
-- ============================================

-- User name history (tracks all name changes)
CREATE TABLE IF NOT EXISTS user_name_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    source_chat_id BIGINT,  -- where the change was detected
    snapshot_id UUID  -- links to user_snapshots
);

-- User snapshots (full profile at a point in time)
CREATE TABLE IF NOT EXISTS user_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    photo_id TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    source_chat_id BIGINT
);

-- User history opt-out
CREATE TABLE IF NOT EXISTS user_history_optout (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL UNIQUE,
    opted_out_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT
);

-- Indexes for name history
CREATE INDEX IF NOT EXISTS idx_name_history_user ON user_name_history(user_id);
CREATE INDEX IF NOT EXISTS idx_name_history_changed ON user_name_history(changed_at);
CREATE INDEX IF NOT EXISTS idx_user_snapshots_user ON user_snapshots(user_id);

-- Night mode configuration is stored in groups.settings JSONB:
-- night_mode: {
--   enabled: bool,
--   start_time: "23:00",
--   end_time: "07:00",
--   timezone: "UTC",
--   custom_message: string,
--   restored_permissions: json  -- saved original permissions
-- }

-- Night mode log
CREATE TABLE IF NOT EXISTS night_mode_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT NOT NULL,
    action TEXT NOT NULL,  -- restricted, restored
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    start_time TEXT,  -- scheduled start
    end_time TEXT,    -- scheduled end
    permissions_snapshot JSONB  -- the permissions that were applied/restored
);

CREATE INDEX IF NOT EXISTS idx_night_mode_log_chat ON night_mode_log(chat_id);
CREATE INDEX IF NOT EXISTS idx_night_mode_log_triggered ON night_mode_log(triggered_at);
