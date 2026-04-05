-- Community Economy System - Per-group virtual currency and shop

-- Economy config per group
CREATE TABLE IF NOT EXISTS community_economy_config (
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    currency_name TEXT DEFAULT 'coins',
    currency_symbol TEXT DEFAULT '🪙',
    enabled BOOLEAN DEFAULT FALSE,
    xp_to_currency_rate INTEGER DEFAULT 1,
    -- How much currency per XP earned
    stars_exchange_rate INTEGER DEFAULT 100,
    -- How much currency per Telegram Star
    daily_bonus INTEGER DEFAULT 10,
    -- Daily login bonus amount
    min_tip INTEGER DEFAULT 1,
    -- Minimum tip amount
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, bot_id)
);

-- User currency balances
CREATE TABLE IF NOT EXISTS community_currency (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    balance INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    last_daily_claim TIMESTAMPTZ,
    last_message_earn TIMESTAMPTZ,
    PRIMARY KEY (chat_id, user_id, bot_id)
);

-- Transaction history
CREATE TABLE IF NOT EXISTS community_transactions (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    -- positive = earned, negative = spent
    transaction_type TEXT NOT NULL,
    -- earn, spend, bonus, purchase, admin_grant, tip
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shop items per group
CREATE TABLE IF NOT EXISTS community_shop_items (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    -- role, badge, xp_boost, feature, title
    item_value TEXT,
    -- role_id, badge_id, boost_amount, feature_name, title_text
    emoji TEXT DEFAULT '🎁',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quests system
CREATE TABLE IF NOT EXISTS community_quests (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    quest_type TEXT NOT NULL,
    -- message_count, invite_count, daily_login, reaction_give, custom
    target_value INTEGER NOT NULL,
    reward_amount INTEGER NOT NULL,
    reward_type TEXT NOT NULL,
    -- currency, xp, badge
    is_repeatable BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User quest progress
CREATE TABLE IF NOT EXISTS community_quest_progress (
    id BIGSERIAL,
    quest_id BIGINT REFERENCES community_quests(id),
    user_id BIGINT NOT NULL,
    progress_value INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (quest_id, user_id)
);

-- Tip/transfer between users
CREATE TABLE IF NOT EXISTS community_tips (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    from_user_id BIGINT NOT NULL,
    to_user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_community_currency_balance ON community_currency(chat_id, bot_id, balance DESC);
CREATE INDEX IF NOT EXISTS idx_community_transactions_user ON community_transactions(chat_id, user_id, bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_community_shop_items_active ON community_shop_items(chat_id, bot_id, is_active);
CREATE INDEX IF NOT EXISTS idx_community_quests_active ON community_quests(chat_id, bot_id, is_active);
CREATE INDEX IF NOT EXISTS idx_community_quest_progress ON community_quest_progress(quest_id, user_id);