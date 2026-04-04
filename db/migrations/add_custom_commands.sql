-- ── Custom Commands Builder ──────────────────────────────────────────────────
-- Allows group admins to create custom bot commands with triggers, conditions,
-- actions, and variable substitution — entirely through the mini app.

-- Main custom commands table
CREATE TABLE IF NOT EXISTS custom_commands (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    enabled         BOOLEAN DEFAULT TRUE,
    created_by      BIGINT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    execution_count BIGINT DEFAULT 0,
    cooldown_secs   INT DEFAULT 0,
    last_executed   TIMESTAMPTZ,
    priority        INT DEFAULT 0,
    UNIQUE (chat_id, name)
);

CREATE INDEX IF NOT EXISTS idx_custom_commands_chat
    ON custom_commands(chat_id, enabled);

-- Triggers that activate a custom command
CREATE TABLE IF NOT EXISTS command_triggers (
    id          BIGSERIAL PRIMARY KEY,
    command_id  BIGINT NOT NULL REFERENCES custom_commands(id) ON DELETE CASCADE,
    trigger_type TEXT NOT NULL,
    -- 'command' = /cmd, 'keyword' = contains word, 'regex' = regex match,
    -- 'new_member' = on join, 'left_member' = on leave,
    -- 'message' = any message, 'exact' = exact text match,
    -- 'has_attachment' = has photo/video/document, 'has_photo' = has photo,
    -- 'has_video' = has video, 'has_document' = has document,
    -- 'has_voice' = has voice note, 'has_sticker' = has sticker,
    -- 'has_link' = contains URL, 'forwarded' = is forwarded
    trigger_value TEXT NOT NULL DEFAULT '',
    -- e.g. the command name, keyword, or regex pattern
    case_sensitive BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_command_triggers_cmd
    ON command_triggers(command_id);

-- Actions that execute when a command is triggered
CREATE TABLE IF NOT EXISTS command_actions (
    id          BIGSERIAL PRIMARY KEY,
    command_id  BIGINT NOT NULL REFERENCES custom_commands(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    -- 'reply' = send text, 'delete' = delete trigger msg,
    -- 'warn' = warn user, 'mute' = mute user, 'ban' = ban user,
    -- 'kick' = kick user, 'pin' = pin message, 'react' = add reaction,
    -- 'set_variable' = set a variable value, 'send_photo' = send photo,
    -- 'send_audio' = send audio, 'send_video' = send video,
    -- 'send_document' = send document, 'send_voice' = send voice note,
    -- 'send_location' = send location, 'send_venue' = send venue,
    -- 'send_contact' = send contact, 'forward' = forward to another chat,
    -- 'promote' = promote to admin, 'demote' = remove admin,
    -- 'unmute' = unmute user, 'unban' = unban user,
    -- 'webhook' = call external webhook
    action_config JSONB DEFAULT '{}',
    -- type-specific config, e.g. {"text": "Hello {user.name}!", "parse_mode": "HTML"}
    sort_order  INT DEFAULT 0,
    condition   JSONB DEFAULT NULL,
    -- optional condition: {"type": "role_check", "role": "admin"}
    -- or {"type": "variable_check", "var": "warned", "op": ">=", "value": 3}
    -- or {"type": "reply_check"} - requires reply to message
    delay_secs  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_command_actions_cmd
    ON command_actions(command_id, sort_order);

-- Variables scoped to a command or group
CREATE TABLE IF NOT EXISTS command_variables (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    command_id  BIGINT REFERENCES custom_commands(id) ON DELETE CASCADE,
    -- NULL command_id = group-level variable
    var_name    TEXT NOT NULL,
    var_value   TEXT DEFAULT '',
    var_type    TEXT DEFAULT 'string',
    -- 'string' | 'number' | 'boolean' | 'list'
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, command_id, var_name)
);

CREATE INDEX IF NOT EXISTS idx_command_variables_chat
    ON command_variables(chat_id, command_id);

-- Rate limiting for custom commands
CREATE TABLE IF NOT EXISTS command_rate_limits (
    chat_id     BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    command_id  BIGINT NOT NULL REFERENCES custom_commands(id) ON DELETE CASCADE,
    last_used   TIMESTAMPTZ DEFAULT NOW(),
    use_count   INT DEFAULT 1,
    PRIMARY KEY (chat_id, user_id, command_id)
);
