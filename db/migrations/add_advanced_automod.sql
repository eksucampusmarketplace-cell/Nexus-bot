-- ── Per-rule time windows ─────────────────────────────────────────────────
-- Each lock can have an optional active time window
-- e.g. link lock only active from 23:30 to 08:10
CREATE TABLE IF NOT EXISTS rule_time_windows (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    rule_key    TEXT NOT NULL,
    -- matches lock key: link|website|username|photo|video|sticker|
    -- gif|forward|forward_channel|text|voice|file|software|poll|
    -- slash|no_caption|emoji_only|emoji|game|english|arabic_farsi|
    -- reply|external_reply|bot|unofficial_tg|hashtag|location|
    -- phone|audio|spoiler
    start_time  TIME NOT NULL,   -- HH:MM in group timezone
    end_time    TIME NOT NULL,   -- HH:MM in group timezone
    -- end_time < start_time means spans midnight
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, rule_key)
);

-- ── Per-violation custom penalties ───────────────────────────────────────
-- Override default penalty for specific rule violations
CREATE TABLE IF NOT EXISTS rule_penalties (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    rule_key    TEXT NOT NULL,
    penalty     TEXT NOT NULL,
    -- delete | silence | kick | ban
    -- silence/ban can have duration
    duration_hours INT DEFAULT 0,
    -- 0 = permanent for ban, instant for silence
    -- 1000 = permanent silence
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, rule_key)
);

-- ── Silent time slots ─────────────────────────────────────────────────────
-- Up to 3 silent time slots per group per day
CREATE TABLE IF NOT EXISTS silent_times (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    slot            INT NOT NULL CHECK (slot IN (1,2,3)),
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    -- Custom texts
    start_text      TEXT DEFAULT '',
    end_text        TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, slot)
);

-- ── Duplicate message tracking ────────────────────────────────────────────
-- Stores recent message hashes for duplicate detection
CREATE TABLE IF NOT EXISTS message_hashes (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    msg_hash    TEXT NOT NULL,
    -- MD5 of normalized message text
    user_id     BIGINT NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_msg_hashes_chat_time
    ON message_hashes(chat_id, sent_at DESC);

-- ── REGEX patterns ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regex_patterns (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    pattern     TEXT NOT NULL,
    -- Python re-compatible pattern
    penalty     TEXT DEFAULT 'delete',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Necessary words ───────────────────────────────────────────────────────
-- Every message must contain at least one word from this list
CREATE TABLE IF NOT EXISTS necessary_words (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    word        TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    UNIQUE (chat_id, word)
);

-- ── Rule priority ordering ────────────────────────────────────────────────
-- Drag-and-drop order for rule evaluation
CREATE TABLE IF NOT EXISTS rule_priority (
    chat_id     BIGINT NOT NULL,
    rule_order  JSONB NOT NULL DEFAULT '[]',
    -- ["link","website","photo","video",...]
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id)
);

-- ── Self-destruct settings per group ─────────────────────────────────────
-- Already in group_settings but adding explicit column
ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS self_destruct_enabled  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS self_destruct_minutes  INT DEFAULT 2,
    ADD COLUMN IF NOT EXISTS lock_admins            BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS unofficial_tg_lock     BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS bot_inviter_ban        BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS duplicate_limit        INT DEFAULT 0,
    -- 0 = disabled
    ADD COLUMN IF NOT EXISTS duplicate_window_mins  INT DEFAULT 60,
    ADD COLUMN IF NOT EXISTS min_words              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_words              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS min_lines              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_lines              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS min_chars              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_chars              INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS necessary_words_active BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS regex_active           BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS timed_locks            JSONB DEFAULT '{}';
    -- { "image": {"start":"08:00","end":"12:00"} }

-- ── Rule templates ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rule_templates (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    -- "Gaming" | "Study" | "Crypto" | "News" | "Support" | "Custom"
    description TEXT,
    settings    JSONB NOT NULL,
    -- Full settings object to apply
    is_builtin  BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Insert built-in templates
INSERT INTO rule_templates (name, description, settings) VALUES
(
    'Gaming',
    'Relaxed rules for gaming communities',
    '{
        "locks": {"link":false,"website":false,"sticker":false,"gif":false},
        "min_words": 0,
        "duplicate_limit": 5,
        "duplicate_window_mins": 10,
        "warn_on_violation": true,
        "max_warnings": 5
    }'::jsonb
),
(
    'Study',
    'Strict rules for study/educational groups',
    '{
        "locks": {"sticker":true,"gif":true,"game":true,"emoji_only":true},
        "min_words": 3,
        "duplicate_limit": 2,
        "duplicate_window_mins": 30,
        "necessary_words_active": false,
        "warn_on_violation": true,
        "max_warnings": 3
    }'::jsonb
),
(
    'Crypto',
    'Anti-scam rules for crypto communities',
    '{
        "locks": {"link":true,"website":true,"forward":true,"unofficial_tg":true},
        "bot_inviter_ban": true,
        "warn_on_violation": false,
        "default_penalty": "ban"
    }'::jsonb
),
(
    'News Channel Group',
    'Comments group for news channels',
    '{
        "locks": {"link":true,"forward_channel":false,"bot":true},
        "min_words": 2,
        "duplicate_limit": 3,
        "warn_on_violation": true,
        "max_warnings": 3
    }'::jsonb
),
(
    'Support',
    'Customer support group settings',
    '{
        "locks": {"sticker":true,"gif":true,"game":true},
        "necessary_words_active": false,
        "warn_on_violation": true,
        "self_destruct_enabled": false,
        "max_warnings": 5
    }'::jsonb
),
(
    'Strict',
    'Maximum enforcement — zero tolerance',
    '{
        "locks": {"link":true,"website":true,"forward":true,"sticker":true,
                  "gif":true,"game":true,"unofficial_tg":true,"bot":true},
        "duplicate_limit": 1,
        "min_words": 2,
        "warn_on_violation": false,
        "default_penalty": "kick"
    }'::jsonb
)
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_rule_time_windows_chat
    ON rule_time_windows(chat_id, rule_key);
CREATE INDEX IF NOT EXISTS idx_rule_penalties_chat
    ON rule_penalties(chat_id, rule_key);
CREATE INDEX IF NOT EXISTS idx_silent_times_chat
    ON silent_times(chat_id, is_active);
