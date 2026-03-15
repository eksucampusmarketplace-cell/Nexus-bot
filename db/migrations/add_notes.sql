-- Migration: add_notes
-- Notes system for storing and retrieving group notes

CREATE TABLE IF NOT EXISTS notes (
    id        BIGSERIAL PRIMARY KEY,
    chat_id   BIGINT    NOT NULL,
    name      TEXT      NOT NULL,
    content   TEXT,
    file_id   TEXT,
    media_type TEXT,
    buttons   JSONB DEFAULT '[]'::jsonb,
    added_by  BIGINT,
    added_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, name)
);

CREATE INDEX IF NOT EXISTS idx_notes_chat ON notes(chat_id);
