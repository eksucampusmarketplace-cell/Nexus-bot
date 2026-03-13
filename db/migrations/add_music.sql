-- Userbot accounts for music (main bot pool + clone bot accounts)
CREATE TABLE IF NOT EXISTS music_userbots (
    id              BIGSERIAL PRIMARY KEY,
    owner_bot_id    BIGINT NOT NULL,
    -- For main bot: 0 (shared pool)
    -- For clone bot: the clone's bot_id
    phone           TEXT,
    session_string  TEXT NOT NULL,         -- Pyrogram session, encrypted at rest
    tg_user_id      BIGINT,                -- resolved Telegram user ID
    tg_username     TEXT,
    tg_name         TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    risk_fee        INT DEFAULT 0,         -- Monthly fee in Stars
    is_banned       BOOLEAN DEFAULT FALSE, -- Banned from using service
    ban_reason      TEXT,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    UNIQUE (owner_bot_id, tg_user_id)
);

-- Per-group queue
CREATE TABLE IF NOT EXISTS music_queues (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,       -- which bot instance owns this queue
    position        INT NOT NULL DEFAULT 0,
    url             TEXT NOT NULL,
    title           TEXT DEFAULT 'Unknown',
    duration        INT DEFAULT 0,         -- seconds
    thumbnail       TEXT,
    source          TEXT DEFAULT 'unknown',
    -- youtube|soundcloud|spotify|direct|voice
    requested_by    BIGINT NOT NULL,
    requested_by_name TEXT,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    played          BOOLEAN DEFAULT FALSE,
    UNIQUE (chat_id, bot_id, position)
);

-- Per-group playback session state
CREATE TABLE IF NOT EXISTS music_sessions (
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    is_playing      BOOLEAN DEFAULT FALSE,
    is_paused       BOOLEAN DEFAULT FALSE,
    is_looping      BOOLEAN DEFAULT FALSE,
    volume          INT DEFAULT 100,
    current_track   BIGINT REFERENCES music_queues(id) ON DELETE SET NULL,
    np_message_id   BIGINT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, bot_id)
);

-- Music settings per group
CREATE TABLE IF NOT EXISTS music_settings (
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    play_mode       TEXT DEFAULT 'all'
                    CHECK (play_mode IN ('all','admins')),
    -- 'all' = anyone can /play
    -- 'admins' = only admins can /play
    dj_role_id      BIGINT,                -- optional: specific role that can /play
    announce_tracks BOOLEAN DEFAULT TRUE,  -- post now-playing card on each track
    userbot_id      BIGINT REFERENCES music_userbots(id) ON DELETE SET NULL,
    PRIMARY KEY (chat_id, bot_id)
);

CREATE INDEX IF NOT EXISTS idx_music_queue ON music_queues(chat_id, bot_id, played, position);
CREATE INDEX IF NOT EXISTS idx_music_userbots ON music_userbots(owner_bot_id, is_active);
CREATE INDEX IF NOT EXISTS idx_music_sessions ON music_sessions(chat_id, bot_id);
CREATE INDEX IF NOT EXISTS idx_music_settings ON music_settings(chat_id, bot_id);
