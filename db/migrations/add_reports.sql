-- Migration: add_reports
-- Full report system with status tracking and admin inbox

CREATE TABLE IF NOT EXISTS reports (
    id            BIGSERIAL PRIMARY KEY,
    chat_id       BIGINT      NOT NULL,
    reporter_id   BIGINT      NOT NULL,
    reported_id   BIGINT,
    message_id    BIGINT,
    reason        TEXT        NOT NULL DEFAULT '',
    status        TEXT        NOT NULL DEFAULT 'open',   -- open | resolved | dismissed
    resolved_by   BIGINT,
    resolved_at   TIMESTAMPTZ,
    resolution_note TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_chat_id   ON reports (chat_id);
CREATE INDEX IF NOT EXISTS idx_reports_status    ON reports (chat_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_reporter  ON reports (reporter_id);
CREATE INDEX IF NOT EXISTS idx_reports_reported  ON reports (reported_id);

-- Add report_count convenience column to users so the analytics API can read it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'report_count'
    ) THEN
        ALTER TABLE users ADD COLUMN report_count INT NOT NULL DEFAULT 0;
    END IF;
END $$;
