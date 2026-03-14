-- ── XP & Levels ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS member_xp (
    chat_id             BIGINT NOT NULL,
    user_id             BIGINT NOT NULL,
    bot_id              BIGINT NOT NULL,
    xp                  INTEGER DEFAULT 0,
    level               INTEGER DEFAULT 1,
    total_messages      INTEGER DEFAULT 0,
    last_message_at     TIMESTAMPTZ,
    last_xp_at          TIMESTAMPTZ,
    last_daily_checkin  DATE,
    streak_days         INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, bot_id)
);

CREATE TABLE IF NOT EXISTS xp_transactions (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    bot_id      BIGINT NOT NULL,
    amount      INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    given_by    BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS level_config (
    chat_id             BIGINT NOT NULL,
    bot_id              BIGINT NOT NULL,
    level               INTEGER NOT NULL,
    xp_required         INTEGER NOT NULL,
    title               TEXT,
    unlock_description  TEXT,
    PRIMARY KEY (chat_id, bot_id, level)
);

CREATE TABLE IF NOT EXISTS level_rewards (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    level           INTEGER NOT NULL,
    reward_type     TEXT NOT NULL,
    reward_value    TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS xp_settings (
    chat_id                 BIGINT NOT NULL,
    bot_id                  BIGINT NOT NULL,
    enabled                 BOOLEAN DEFAULT TRUE,
    xp_per_message          INTEGER DEFAULT 1,
    xp_per_daily            INTEGER DEFAULT 10,
    xp_per_game_win         INTEGER DEFAULT 5,
    xp_per_game_play        INTEGER DEFAULT 1,
    xp_admin_grant          INTEGER DEFAULT 20,
    message_cooldown_s      INTEGER DEFAULT 60,
    level_up_announce       BOOLEAN DEFAULT TRUE,
    level_up_message        TEXT DEFAULT '🎉 {mention} reached Level {level}! {title}',
    double_xp_active        BOOLEAN DEFAULT FALSE,
    double_xp_until         TIMESTAMPTZ,
    PRIMARY KEY (chat_id, bot_id)
);

-- ── Reputation System ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS member_reputation (
    chat_id         BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    rep_score       INTEGER DEFAULT 0,
    total_given     INTEGER DEFAULT 0,
    total_received  INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, bot_id)
);

CREATE TABLE IF NOT EXISTS rep_transactions (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    from_user_id    BIGINT NOT NULL,
    to_user_id      BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    amount          INTEGER DEFAULT 1,
    reason          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rep_daily_limits (
    chat_id     BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    bot_id      BIGINT NOT NULL,
    date        DATE NOT NULL,
    given_count INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, bot_id, date)
);

-- ── Badges ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS badges (
    id                  BIGSERIAL PRIMARY KEY,
    bot_id              BIGINT NOT NULL,
    chat_id             BIGINT,
    name                TEXT NOT NULL,
    emoji               TEXT NOT NULL,
    description         TEXT,
    condition_type      TEXT NOT NULL,
    condition_value     INTEGER DEFAULT 0,
    is_rare             BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS member_badges (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    bot_id      BIGINT NOT NULL,
    badge_id    BIGINT REFERENCES badges(id),
    earned_at   TIMESTAMPTZ DEFAULT NOW(),
    granted_by  BIGINT
);

-- ── Weekly Newsletter ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS newsletter_config (
    chat_id                 BIGINT NOT NULL,
    bot_id                  BIGINT NOT NULL,
    enabled                 BOOLEAN DEFAULT TRUE,
    send_day                INTEGER DEFAULT 0,
    send_hour_utc           INTEGER DEFAULT 9,
    include_top_members     BOOLEAN DEFAULT TRUE,
    include_top_messages    BOOLEAN DEFAULT TRUE,
    include_new_members     BOOLEAN DEFAULT TRUE,
    include_leaderboard     BOOLEAN DEFAULT TRUE,
    include_milestones      BOOLEAN DEFAULT TRUE,
    custom_intro            TEXT,
    PRIMARY KEY (chat_id, bot_id)
);

CREATE TABLE IF NOT EXISTS newsletter_history (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    message_id      BIGINT,
    stats_snapshot  JSONB
);

-- ── Cross-Group Network ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS group_networks (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    owner_user_id   BIGINT NOT NULL,
    owner_bot_id    BIGINT NOT NULL,
    invite_code     TEXT UNIQUE NOT NULL,
    is_public       BOOLEAN DEFAULT FALSE,
    member_count    INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS network_members (
    network_id  BIGINT REFERENCES group_networks(id),
    chat_id     BIGINT NOT NULL,
    bot_id      BIGINT NOT NULL,
    role        TEXT DEFAULT 'member',
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (network_id, chat_id)
);

CREATE TABLE IF NOT EXISTS network_announcements (
    id              BIGSERIAL PRIMARY KEY,
    network_id      BIGINT REFERENCES group_networks(id),
    from_chat_id    BIGINT NOT NULL,
    sent_by         BIGINT NOT NULL,
    message_text    TEXT NOT NULL,
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    delivered_to    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS network_xp (
    network_id              BIGINT REFERENCES group_networks(id),
    user_id                 BIGINT NOT NULL,
    total_xp                INTEGER DEFAULT 0,
    contributing_groups     INTEGER DEFAULT 0,
    last_updated            TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (network_id, user_id)
);

-- ── Milestones ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS group_milestones (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    bot_id          BIGINT NOT NULL,
    milestone_type  TEXT NOT NULL,
    milestone_value INTEGER NOT NULL,
    reached_at      TIMESTAMPTZ DEFAULT NOW(),
    announced       BOOLEAN DEFAULT FALSE
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_member_xp_chat_level
    ON member_xp(chat_id, bot_id, level DESC, xp DESC);
CREATE INDEX IF NOT EXISTS idx_member_xp_user
    ON member_xp(user_id, bot_id);
CREATE INDEX IF NOT EXISTS idx_xp_transactions_chat
    ON xp_transactions(chat_id, bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_rep_chat
    ON member_reputation(chat_id, bot_id, rep_score DESC);
CREATE INDEX IF NOT EXISTS idx_member_badges_user
    ON member_badges(chat_id, user_id, bot_id);
CREATE INDEX IF NOT EXISTS idx_network_members_network
    ON network_members(network_id);
CREATE INDEX IF NOT EXISTS idx_network_xp_leaderboard
    ON network_xp(network_id, total_xp DESC);
