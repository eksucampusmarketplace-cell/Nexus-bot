-- ── Log channel config ────────────────────────────────────────────────────
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS log_channel_id     BIGINT,
    ADD COLUMN IF NOT EXISTS log_categories     JSONB DEFAULT '{
        "ban": true,
        "mute": true,
        "warn": true,
        "kick": true,
        "delete": true,
        "join": false,
        "leave": false,
        "raid": true,
        "captcha": true,
        "filter": true,
        "blocklist": true,
        "settings": true,
        "pin": true,
        "report": true,
        "note": false,
        "schedule": false,
        "password": true,
        "import_export": true
    }'::jsonb,
    ADD COLUMN IF NOT EXISTS log_include_preview BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS log_include_userid  BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS inline_mode_enabled BOOLEAN DEFAULT FALSE;

-- ── Activity event log (persistent, queryable) ────────────────────────────
CREATE TABLE IF NOT EXISTS activity_log (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    bot_id       BIGINT NOT NULL,
    event_type   TEXT NOT NULL,
    actor_id     BIGINT,
    target_id    BIGINT,
    actor_name   TEXT,
    target_name  TEXT,
    details      JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_chat_time
    ON activity_log(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_type
    ON activity_log(chat_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_target
    ON activity_log(chat_id, target_id, created_at DESC);

-- ── Inline query log ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inline_queries (
    id          BIGSERIAL PRIMARY KEY,
    bot_id      BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    query       TEXT NOT NULL,
    result_type TEXT,
    chosen      BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
