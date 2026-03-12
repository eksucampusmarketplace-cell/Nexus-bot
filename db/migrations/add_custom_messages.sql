-- Custom messages per group
-- Stores only the BODY of each message (footer is always appended by code)
CREATE TABLE IF NOT EXISTS group_custom_messages (
    id          BIGSERIAL PRIMARY KEY,
    group_id    BIGINT NOT NULL,
    message_key TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated_by  BIGINT,          -- user_id of the admin who last changed it
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (group_id, message_key)
);

CREATE INDEX IF NOT EXISTS idx_custom_messages_group
    ON group_custom_messages(group_id);

COMMENT ON TABLE group_custom_messages IS
    'Custom message overrides per group. Body only — footer always appended by code.';
