-- ── Anti-raid config ──────────────────────────────────────────────────────
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS antiraid_enabled        BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS antiraid_mode           TEXT DEFAULT 'restrict',
    -- restrict | ban | captcha
    ADD COLUMN IF NOT EXISTS antiraid_threshold      INT DEFAULT 10,
    -- joins per minute to trigger
    ADD COLUMN IF NOT EXISTS antiraid_duration_mins  INT DEFAULT 15,
    -- how long lockdown lasts (0 = manual unlock)
    ADD COLUMN IF NOT EXISTS auto_antiraid_enabled   BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auto_antiraid_threshold INT DEFAULT 15,
    ADD COLUMN IF NOT EXISTS captcha_enabled         BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS captcha_mode            TEXT DEFAULT 'button',
    -- button | math | text
    ADD COLUMN IF NOT EXISTS captcha_timeout_mins    INT DEFAULT 5,
    ADD COLUMN IF NOT EXISTS captcha_kick_on_timeout BOOLEAN DEFAULT TRUE;

-- ── Active anti-raid sessions ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS antiraid_sessions (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_by TEXT DEFAULT 'auto',
    -- 'auto' | 'manual' | admin user_id
    ends_at      TIMESTAMPTZ,
    -- NULL = manual unlock required
    is_active    BOOLEAN DEFAULT TRUE,
    join_count   INT DEFAULT 0
    -- joins counted during this session
);

CREATE INDEX IF NOT EXISTS idx_antiraid_sessions_chat
    ON antiraid_sessions(chat_id, is_active);

-- ── Recent join tracking for anti-raid detection ──────────────────────────
CREATE TABLE IF NOT EXISTS recent_joins (
    id       BIGSERIAL PRIMARY KEY,
    chat_id  BIGINT NOT NULL,
    user_id  BIGINT NOT NULL,
    joined_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recent_joins_chat_time
    ON recent_joins(chat_id, joined_at DESC);

-- ── CAPTCHA challenges ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS captcha_challenges (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    challenge_id TEXT NOT NULL UNIQUE,
    -- random UUID for callback_data
    mode         TEXT NOT NULL,
    answer       TEXT NOT NULL,
    -- correct answer (button label / math result / text phrase)
    message_id   INT,
    -- bot's challenge message to delete on pass
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    passed       BOOLEAN DEFAULT FALSE,
    attempts     INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_captcha_chat_user
    ON captcha_challenges(chat_id, user_id, passed);

-- ── Approval system ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approved_members (
    chat_id      BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    approved_by  BIGINT,
    approved_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_approved_members_chat
    ON approved_members(chat_id);

-- ── Join/leave event log (for live feed) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS member_events (
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    username   TEXT,
    full_name  TEXT,
    event_type TEXT NOT NULL,
    -- join | leave | ban | kick | captcha_pass | captcha_fail |
    -- approve | unapprove | raid_join
    meta       JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_member_events_chat
    ON member_events(chat_id, created_at DESC);
