-- File: db/migrations/add_billing_tables.sql
--
-- Creates tables for billing subscriptions and payment events
-- This supports the new plan-based billing system

-- Billing subscriptions table
CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    plan VARCHAR NOT NULL,
    telegram_charge_id TEXT UNIQUE,
    stars_paid INT NOT NULL,
    plan_expires_at TIMESTAMPTZ NOT NULL,
    auto_renew BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for looking up owner's active subscription
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_owner
  ON billing_subscriptions(owner_id, plan_expires_at);

-- Index for looking up by charge ID (webhook verification)
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_charge
  ON billing_subscriptions(telegram_charge_id);

-- Payment events table (audit trail for all payments)
CREATE TABLE IF NOT EXISTS payment_events (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    event_type VARCHAR NOT NULL,  -- 'subscription', 'purchase', 'refund', 'bonus_stars_spend', 'promo_redemption'
    item_type VARCHAR,            -- 'basic', 'starter', 'pro', 'unlimited', or feature item types
    stars_paid INT DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for querying payment history
CREATE INDEX IF NOT EXISTS idx_payment_events_owner
  ON payment_events(owner_id, created_at DESC);

-- Stars purchases table (for individual feature purchases - legacy support)
CREATE TABLE IF NOT EXISTS stars_purchases (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    telegram_charge_id TEXT UNIQUE NOT NULL,
    item_type VARCHAR NOT NULL,
    stars_paid INT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for active feature entitlements
CREATE INDEX IF NOT EXISTS idx_stars_purchases_active
  ON stars_purchases(owner_id, item_type, expires_at);

-- Promo codes table
CREATE TABLE IF NOT EXISTS promo_codes (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR UNIQUE NOT NULL,
    reward_type VARCHAR NOT NULL,  -- 'bonus_stars', 'feature_unlock', 'group_slot', 'clone_slot'
    reward_value INT DEFAULT 0,
    reward_feature VARCHAR,
    reward_days INT DEFAULT 30,
    max_uses INT DEFAULT 1,
    current_uses INT DEFAULT 0,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for looking up active codes
CREATE INDEX IF NOT EXISTS idx_promo_codes_code
  ON promo_codes(code) WHERE is_active = TRUE;

-- Promo redemptions table
CREATE TABLE IF NOT EXISTS promo_redemptions (
    id BIGSERIAL PRIMARY KEY,
    code_id INT REFERENCES promo_codes(id),
    owner_id BIGINT NOT NULL,
    redeemed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(code_id, owner_id)
);

-- Index for tracking redemptions
CREATE INDEX IF NOT EXISTS idx_promo_redemptions_owner
  ON promo_redemptions(owner_id);

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL UNIQUE,
    bonus_stars INT DEFAULT 0,
    rewarded BOOLEAN DEFAULT FALSE,
    rewarded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for looking up referral rewards
CREATE INDEX IF NOT EXISTS idx_referrals_referrer
  ON referrals(referrer_id, rewarded);

-- Index for checking if user was referred
CREATE INDEX IF NOT EXISTS idx_referrals_referred
  ON referrals(referred_id);

-- Bonus stars balance table
CREATE TABLE IF NOT EXISTS bonus_stars_balance (
    owner_id BIGINT PRIMARY KEY,
    balance INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bonus stars ledger (all transactions)
CREATE TABLE IF NOT EXISTS bonus_stars (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    amount INT NOT NULL,  -- positive for grants, negative for spends
    reason VARCHAR,
    granted_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for ledger queries
CREATE INDEX IF NOT EXISTS idx_bonus_stars_owner
  ON bonus_stars(owner_id, created_at DESC);
