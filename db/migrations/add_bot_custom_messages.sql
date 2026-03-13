-- Bot-wide custom messages
CREATE TABLE IF NOT EXISTS bot_custom_messages (
    id          BIGSERIAL PRIMARY KEY,
    bot_id      BIGINT NOT NULL,
    message_key TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated_by  BIGINT,          -- user_id of the owner who last changed it
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (bot_id, message_key)
);

CREATE INDEX IF NOT EXISTS idx_bot_custom_messages_bot
    ON bot_custom_messages(bot_id);

COMMENT ON TABLE bot_custom_messages IS
    'Custom message overrides per bot. Body only — footer always appended by code.';
