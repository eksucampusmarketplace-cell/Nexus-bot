-- Global Trust Score System - Cross-group reputation tracking

-- Main global trust table - one score per user across ALL groups
CREATE TABLE IF NOT EXISTS global_user_trust (
    user_id BIGINT PRIMARY KEY,
    trust_score INTEGER DEFAULT 50,
    -- 0-100 score, 50 is neutral
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- History of all trust score changes
CREATE TABLE IF NOT EXISTS global_trust_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    old_score INTEGER NOT NULL,
    new_score INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,
    -- positive or negative
    reason TEXT NOT NULL,
    -- e.g. 'positive_rep', 'raid_victim', 'spam', 'manual_override'
    group_id BIGINT,
    -- optional group that triggered the change
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trust-based access control rules per group
CREATE TABLE IF NOT EXISTS trust_gates (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    required_tier TEXT NOT NULL,
    -- low, medium, high, trusted
    gate_type TEXT NOT NULL,
    -- role_assignment, giveaway_entry, feature_unlock, command_access
    gate_value TEXT,
    -- role_id, giveaway_id, feature_name, command_name
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, bot_id, gate_type, gate_value)
);

-- Trust tier rewards that groups can configure
CREATE TABLE IF NOT EXISTS trust_rewards (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    tier TEXT NOT NULL,
    -- low, medium, high, trusted
    reward_type TEXT NOT NULL,
    -- role, title, badge, xp_bonus, feature
    reward_value TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(chat_id, bot_id, tier, reward_type)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_global_trust_score ON global_user_trust(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_global_trust_history_user ON global_trust_history(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trust_gates_chat ON trust_gates(chat_id, bot_id);
CREATE INDEX IF NOT EXISTS idx_trust_rewards_chat ON trust_rewards(chat_id, bot_id, tier);
