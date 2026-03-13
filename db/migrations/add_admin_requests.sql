-- Migration: add_admin_requests
-- System for users to request admin help by mentioning @admins

CREATE TABLE IF NOT EXISTS admin_requests (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT      NOT NULL,
    user_id         BIGINT      NOT NULL,
    message_id      BIGINT      NOT NULL,
    message_text    TEXT        NOT NULL,
    reply_to_msg_id BIGINT,
    status          TEXT        NOT NULL DEFAULT 'open',  -- open | responding | closed
    responded_by    BIGINT,
    response_text   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_requests_chat_id   ON admin_requests (chat_id);
CREATE INDEX IF NOT EXISTS idx_admin_requests_status    ON admin_requests (chat_id, status);
CREATE INDEX IF NOT EXISTS idx_admin_requests_user_id   ON admin_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_admin_requests_created_at ON admin_requests (created_at DESC);

-- Track per-user request frequency for rate limiting
ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_request_count INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_admin_request_at TIMESTAMPTZ;

-- Group settings for @admins feature
ALTER TABLE groups ADD COLUMN IF NOT EXISTS admin_requests_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS admin_requests_rate_limit INT NOT NULL DEFAULT 3;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS admin_requests_rate_period INT NOT NULL DEFAULT 3600;  -- seconds
