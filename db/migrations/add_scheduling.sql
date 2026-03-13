-- ── Scheduled messages ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scheduled_messages (
    id             BIGSERIAL PRIMARY KEY,
    chat_id        BIGINT NOT NULL,
    content        TEXT NOT NULL,
    media_type     TEXT,
    media_file_id  TEXT,
    schedule_type  TEXT NOT NULL,
    scheduled_at   TIMESTAMPTZ,
    interval_mins  INT,
    cron_expr      TEXT,
    days_of_week   INT[],
    time_of_day    TIME,
    timezone       TEXT DEFAULT 'UTC',
    last_sent_at   TIMESTAMPTZ,
    next_send_at   TIMESTAMPTZ,
    send_count     INT DEFAULT 0,
    max_sends      INT DEFAULT 0,
    is_active      BOOLEAN DEFAULT TRUE,
    pin_after_send BOOLEAN DEFAULT FALSE,
    created_by     BIGINT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_msgs_next
    ON scheduled_messages(next_send_at, is_active)
    WHERE is_active = TRUE;

-- ── Group password ────────────────────────────────────────────────────────
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS group_password          TEXT,
    ADD COLUMN IF NOT EXISTS password_kick_on_fail   BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS password_attempts       INT DEFAULT 3,
    ADD COLUMN IF NOT EXISTS password_timeout_mins   INT DEFAULT 5;

-- ── Password challenge sessions ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS password_challenges (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    attempts     INT DEFAULT 0,
    passed       BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    UNIQUE (chat_id, user_id)
);

-- ── Report system ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    reporter_id  BIGINT NOT NULL,
    reported_id  BIGINT,
    message_id   INT,
    reason       TEXT DEFAULT '',
    status       TEXT DEFAULT 'open',
    reviewed_by  BIGINT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_chat
    ON reports(chat_id, status, created_at DESC);

-- ── Pinned message tracking ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pinned_messages (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    message_id   INT NOT NULL,
    pinned_by    BIGINT,
    pinned_at    TIMESTAMPTZ DEFAULT NOW(),
    is_current   BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_pinned_msgs_chat
    ON pinned_messages(chat_id, is_current);
