-- ── Raid members tracking ─────────────────────────────────────────────────
-- Records individual users who joined during an anti-raid session
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
