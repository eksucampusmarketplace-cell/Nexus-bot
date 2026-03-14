-- ── XP & Levels ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS member_xp (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    total_messages INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    last_xp_at TIMESTAMPTZ,
    -- rate limiting: 1 XP per message, max 1 per minute
    last_daily_checkin DATE,
    streak_days INTEGER DEFAULT 0,
    -- consecutive daily checkins
    PRIMARY KEY (chat_id, user_id, bot_id)
);

-- XP transaction log (for audit and undo)
CREATE TABLE IF NOT EXISTS xp_transactions (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    -- positive or negative
    reason TEXT NOT NULL,
    -- message | daily | game_win | admin_grant | admin_remove | penalty
    given_by BIGINT,
    -- admin user_id if manually granted
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Level configuration per group (admins can customize)
CREATE TABLE IF NOT EXISTS level_config (
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    level INTEGER NOT NULL,
    xp_required INTEGER NOT NULL,
    -- XP needed to reach this level from level 1
    title TEXT,
    -- custom title awarded at this level
    unlock_description TEXT,
    -- what this level unlocks, shown in /levels
    PRIMARY KEY (chat_id, bot_id, level)
);

-- Level rewards (what happens when member reaches a level)
CREATE TABLE IF NOT EXISTS level_rewards (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    level INTEGER NOT NULL,
    reward_type TEXT NOT NULL,
    -- title | role | command | announcement | badge
    reward_value TEXT,
    -- the title text, role_id, command name, badge_id
    is_active BOOLEAN DEFAULT TRUE
);

-- XP settings per group
CREATE TABLE IF NOT EXISTS xp_settings (
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    xp_per_message INTEGER DEFAULT 1,
    xp_per_daily INTEGER DEFAULT 10,
    xp_per_game_win INTEGER DEFAULT 5,
    xp_per_game_play INTEGER DEFAULT 1,
    xp_admin_grant INTEGER DEFAULT 20,
    -- max admin can give at once
    message_cooldown_s INTEGER DEFAULT 60,
    -- seconds between XP-earning messages
    level_up_announce BOOLEAN DEFAULT TRUE,
    -- announce in group when member levels up
    level_up_message TEXT DEFAULT '🎉 {mention} reached Level {level}! {title}',
    double_xp_active BOOLEAN DEFAULT FALSE,
    double_xp_until TIMESTAMPTZ,
    PRIMARY KEY (chat_id, bot_id)
);

-- ── Reputation System ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS member_reputation (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    rep_score INTEGER DEFAULT 0,
    total_given INTEGER DEFAULT 0,
    -- how many +rep this user has given others
    total_received INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, bot_id)
);

-- Rep transaction log
CREATE TABLE IF NOT EXISTS rep_transactions (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    from_user_id BIGINT NOT NULL,
    to_user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    amount INTEGER DEFAULT 1,
    -- +1 or -1
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily rep limit tracking
CREATE TABLE IF NOT EXISTS rep_daily_limits (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    date DATE NOT NULL,
    given_count INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id, bot_id, date)
);

-- ── Badges ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS badges (
    id BIGSERIAL PRIMARY KEY,
    bot_id BIGINT NOT NULL,
    chat_id BIGINT,
    -- NULL = global badge, set = group-specific
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    description TEXT,
    condition_type TEXT NOT NULL,
    -- level | rep | streak | messages | game_wins |
    -- admin_grant | first_join | manual
    condition_value INTEGER DEFAULT 0,
    -- e.g. reach level 10, earn 100 rep, 30 day streak
    is_rare BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS member_badges (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    badge_id BIGINT REFERENCES badges(id),
    earned_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by BIGINT
    -- admin user_id if manually granted
);

-- ── Weekly Newsletter ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS newsletter_config (
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    send_day INTEGER DEFAULT 0,
    -- 0=Sunday, 1=Monday ... 6=Saturday
    send_hour_utc INTEGER DEFAULT 9,
    -- hour in UTC to send
    include_top_members BOOLEAN DEFAULT TRUE,
    include_top_messages BOOLEAN DEFAULT TRUE,
    include_new_members BOOLEAN DEFAULT TRUE,
    include_leaderboard BOOLEAN DEFAULT TRUE,
    include_milestones BOOLEAN DEFAULT TRUE,
    custom_intro TEXT,
    -- optional custom intro text
    PRIMARY KEY (chat_id, bot_id)
);

CREATE TABLE IF NOT EXISTS newsletter_history (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    message_id BIGINT,
    -- telegram message ID of sent newsletter
    stats_snapshot JSONB
    -- snapshot of stats at time of sending
);

-- ── Cross-Group Network ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS group_networks (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_user_id BIGINT NOT NULL,
    owner_bot_id BIGINT NOT NULL,
    invite_code TEXT UNIQUE NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    -- public networks show in discovery
    member_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS network_members (
    network_id BIGINT REFERENCES group_networks(id),
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    role TEXT DEFAULT 'member',
    -- owner | admin | member
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (network_id, chat_id)
);

-- Cross-group announcements
CREATE TABLE IF NOT EXISTS network_announcements (
    id BIGSERIAL PRIMARY KEY,
    network_id BIGINT REFERENCES group_networks(id),
    from_chat_id BIGINT NOT NULL,
    sent_by BIGINT NOT NULL,
    message_text TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_to INTEGER DEFAULT 0
    -- count of groups it was delivered to
);

-- Unified network leaderboard
CREATE TABLE IF NOT EXISTS network_xp (
    network_id BIGINT REFERENCES group_networks(id),
    user_id BIGINT NOT NULL,
    total_xp INTEGER DEFAULT 0,
    -- sum of XP across all groups in network
    contributing_groups INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (network_id, user_id)
);

-- ── Milestones ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS group_milestones (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    milestone_type TEXT NOT NULL,
    -- member_count | total_messages | total_xp_earned
    milestone_value INTEGER NOT NULL,
    -- e.g. 100 members, 1000 messages
    reached_at TIMESTAMPTZ DEFAULT NOW(),
    announced BOOLEAN DEFAULT FALSE
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
