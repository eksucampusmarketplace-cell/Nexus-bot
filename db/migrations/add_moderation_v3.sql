-- Warnings
CREATE TABLE IF NOT EXISTS warnings (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    reason TEXT,
    issued_by BIGINT NOT NULL,
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);
ALTER TABLE warnings ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE warnings ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Mutes (timed)
CREATE TABLE IF NOT EXISTS mutes (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    muted_by BIGINT NOT NULL,
    reason TEXT,
    muted_at TIMESTAMPTZ DEFAULT NOW(),
    unmute_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (chat_id, user_id)
);
ALTER TABLE mutes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE mutes ADD COLUMN IF NOT EXISTS unmute_at TIMESTAMPTZ;

-- Bans (timed)
CREATE TABLE IF NOT EXISTS bans (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    banned_by BIGINT NOT NULL,
    reason TEXT,
    banned_at TIMESTAMPTZ DEFAULT NOW(),
    unban_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (chat_id, user_id)
);
ALTER TABLE bans ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE bans ADD COLUMN IF NOT EXISTS unban_at TIMESTAMPTZ;

-- Group rules
CREATE TABLE IF NOT EXISTS group_rules (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    rules_text TEXT,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Message filters (keyword auto-reply)
CREATE TABLE IF NOT EXISTS filters (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    keyword TEXT NOT NULL,
    response TEXT NOT NULL,
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (chat_id, keyword)
);

-- Blacklisted words
CREATE TABLE IF NOT EXISTS blacklist (
    chat_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    action TEXT DEFAULT 'delete',
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, word)
);

-- Locked permissions per group
CREATE TABLE IF NOT EXISTS locks (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    media BOOLEAN DEFAULT FALSE,
    stickers BOOLEAN DEFAULT FALSE,
    gifs BOOLEAN DEFAULT FALSE,
    links BOOLEAN DEFAULT FALSE,
    forwards BOOLEAN DEFAULT FALSE,
    polls BOOLEAN DEFAULT FALSE,
    games BOOLEAN DEFAULT FALSE,
    voice BOOLEAN DEFAULT FALSE,
    video_notes BOOLEAN DEFAULT FALSE,
    contacts BOOLEAN DEFAULT FALSE
);

-- Admin action log
CREATE TABLE IF NOT EXISTS mod_logs (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    target_id BIGINT,
    target_name TEXT,
    admin_id BIGINT NOT NULL,
    admin_name TEXT,
    reason TEXT,
    duration TEXT,
    done_at TIMESTAMPTZ DEFAULT NOW()
);

-- Warn settings per group
CREATE TABLE IF NOT EXISTS warn_settings (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    max_warns INTEGER DEFAULT 3,
    warn_action TEXT DEFAULT 'mute',
    warn_duration TEXT DEFAULT '1h',
    reset_on_kick BOOLEAN DEFAULT TRUE
);

-- Custom admin titles
CREATE TABLE IF NOT EXISTS admin_titles (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    set_by BIGINT,
    set_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_warnings_chat_user ON warnings(chat_id, user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_mod_logs_chat ON mod_logs(chat_id, done_at DESC);
CREATE INDEX IF NOT EXISTS idx_filters_chat ON filters(chat_id);
CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON blacklist(chat_id);

-- Antiraid settings per group
CREATE TABLE IF NOT EXISTS antiraid_settings (
    chat_id BIGINT PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    threshold_yellow INTEGER DEFAULT 5,
    threshold_orange INTEGER DEFAULT 10,
    threshold_red INTEGER DEFAULT 20,
    threshold_critical INTEGER DEFAULT 50,
    action_yellow TEXT DEFAULT 'alert',
    action_orange TEXT DEFAULT 'captcha',
    action_red TEXT DEFAULT 'lockdown',
    action_critical TEXT DEFAULT 'lockdown_ban',
    lockdown_duration INTEGER DEFAULT 300,
    lockdown_restricts_all BOOLEAN DEFAULT TRUE,
    ban_suspicious_on_raid BOOLEAN DEFAULT FALSE,
    min_account_age_days INTEGER DEFAULT 0,
    block_no_photo BOOLEAN DEFAULT FALSE,
    block_no_username BOOLEAN DEFAULT FALSE,
    block_similar_names BOOLEAN DEFAULT TRUE,
    slowmode_seconds INTEGER DEFAULT 30,
    notify_admins BOOLEAN DEFAULT TRUE,
    notify_log_channel BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Raid incident log
CREATE TABLE IF NOT EXISTS raid_incidents (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    peak_threat_level TEXT DEFAULT 'green',
    peak_joins_per_minute INTEGER DEFAULT 0,
    total_raiders INTEGER DEFAULT 0,
    action_taken TEXT,
    resolved_by BIGINT,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS peak_threat_level TEXT DEFAULT 'green';
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS peak_joins_per_minute INTEGER DEFAULT 0;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS total_raiders INTEGER DEFAULT 0;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS action_taken TEXT;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS resolved_by BIGINT;
ALTER TABLE raid_incidents ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;

-- Individual raiders tracked per incident
CREATE TABLE IF NOT EXISTS raid_members (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT REFERENCES raid_incidents(id),
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    suspicion_score INTEGER DEFAULT 0,
    action_taken TEXT,
    account_age_days INTEGER,
    had_photo BOOLEAN,
    had_bio BOOLEAN,
    had_username BOOLEAN
);

-- Lockdown state per group
CREATE TABLE IF NOT EXISTS lockdown_state (
    chat_id BIGINT PRIMARY KEY,
    is_active BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMPTZ,
    started_by BIGINT,
    reason TEXT,
    auto_unlock_at TIMESTAMPTZ,
    previous_permissions JSONB,
    incident_id BIGINT REFERENCES raid_incidents(id)
);
ALTER TABLE lockdown_state ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE;
ALTER TABLE lockdown_state ADD COLUMN IF NOT EXISTS previous_permissions JSONB;
ALTER TABLE lockdown_state ADD COLUMN IF NOT EXISTS incident_id BIGINT REFERENCES raid_incidents(id);

-- Global ban list (raiders banned from one group, flagged for others)
CREATE TABLE IF NOT EXISTS raid_ban_list (
    user_id BIGINT PRIMARY KEY,
    flagged_at TIMESTAMPTZ DEFAULT NOW(),
    flagged_by_chat BIGINT,
    reason TEXT,
    suspicion_score INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);
ALTER TABLE raid_ban_list ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE raid_ban_list ADD COLUMN IF NOT EXISTS suspicion_score INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_raid_incidents_chat
    ON raid_incidents(chat_id, is_active);
CREATE INDEX IF NOT EXISTS idx_raid_members_incident
    ON raid_members(incident_id);
CREATE INDEX IF NOT EXISTS idx_raid_members_chat_user
    ON raid_members(chat_id, user_id);
CREATE INDEX IF NOT EXISTS idx_raid_ban_list_active
    ON raid_ban_list(user_id, is_active);
