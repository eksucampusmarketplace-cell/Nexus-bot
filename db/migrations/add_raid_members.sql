-- ── Raid members tracking ─────────────────────────────────────────────────
-- Records individual users who joined during an anti-raid session
-- Self-creates antiraid_sessions to prevent startup crash

-- Ensure antiraid_sessions exists first (self-contained migration)
CREATE TABLE IF NOT EXISTS antiraid_sessions (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    triggered_by TEXT,
    join_count   INTEGER DEFAULT 0,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_antiraid_sessions_chat_active ON antiraid_sessions(chat_id, is_active);

-- Now create raid_members with foreign key
CREATE TABLE IF NOT EXISTS raid_members (
    id         BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES antiraid_sessions(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL,
    username   TEXT,
    first_name TEXT,
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    was_banned BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raid_members_session
    ON raid_members(session_id);

CREATE INDEX IF NOT EXISTS idx_raid_members_user
    ON raid_members(user_id);
