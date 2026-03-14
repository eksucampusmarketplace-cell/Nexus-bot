-- Add group limit and access policy to existing bots table
-- Note: group_limit = 0 means unlimited (only for primary bots), 1-20 is the allowed range for clone bots
ALTER TABLE bots
  ADD COLUMN IF NOT EXISTS group_limit            INT DEFAULT 1 CHECK (group_limit BETWEEN 0 AND 20),
  ADD COLUMN IF NOT EXISTS group_access_policy    TEXT DEFAULT 'blocked'
                                                  CHECK (group_access_policy IN ('open','approval','blocked')),
  ADD COLUMN IF NOT EXISTS bot_add_notifications  BOOLEAN DEFAULT FALSE;

-- Tracks every group a clone bot has been added to
CREATE TABLE IF NOT EXISTS clone_bot_groups (
    id              BIGSERIAL PRIMARY KEY,
    bot_id          BIGINT NOT NULL,             -- bots.bot_id
    chat_id         BIGINT NOT NULL,             -- Telegram group chat_id
    chat_title      TEXT,
    added_by        BIGINT NOT NULL,             -- user_id of who added the bot
    added_by_name   TEXT,
    is_owner_group  BOOLEAN DEFAULT FALSE,       -- true if added_by = clone owner
    is_active       BOOLEAN DEFAULT TRUE,        -- false when bot is removed from group
    access_status   TEXT DEFAULT 'pending'
                    CHECK (access_status IN ('active','pending','denied','left')),
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    left_at         TIMESTAMPTZ,
    UNIQUE (bot_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_bot    ON clone_bot_groups(bot_id);
CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_chat   ON clone_bot_groups(chat_id);
CREATE INDEX IF NOT EXISTS idx_clone_bot_groups_active ON clone_bot_groups(bot_id, is_active);
