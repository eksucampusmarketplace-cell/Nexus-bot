-- ── Referral system ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS referrals (
    id              BIGSERIAL PRIMARY KEY,
    referrer_id     BIGINT NOT NULL,    -- who shared the link
    referred_id     BIGINT NOT NULL,    -- who used the link
    bonus_stars     INT DEFAULT 0,      -- stars awarded to referrer
    rewarded        BOOLEAN DEFAULT FALSE,
    -- reward fires when referred user makes first Stars purchase
    referred_at     TIMESTAMPTZ DEFAULT NOW(),
    rewarded_at     TIMESTAMPTZ,
    UNIQUE (referred_id)
    -- one referral per user
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer
    ON referrals(referrer_id);

-- ── Bonus Stars balance ───────────────────────────────────────────────────
-- Internal credits granted by Nexus admin.
-- NOT real Telegram Stars.
-- Used to unlock features exactly like Stars.
-- Shown as "⭐ X Bonus Stars" separately in Mini App.
CREATE TABLE IF NOT EXISTS bonus_stars (
    id          BIGSERIAL PRIMARY KEY,
    owner_id    BIGINT NOT NULL,
    amount      INT NOT NULL,          -- positive = grant, negative = spend
    reason      TEXT NOT NULL,
    -- "referral_reward" | "promo_code" | "admin_grant" | "purchase_spend"
    granted_by  BIGINT,                -- admin user_id if admin_grant
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bonus_stars_owner
    ON bonus_stars(owner_id, created_at DESC);

-- ── Bonus Stars balance view ──────────────────────────────────────────────
CREATE OR REPLACE VIEW bonus_stars_balance AS
SELECT owner_id, COALESCE(SUM(amount), 0) AS balance
FROM bonus_stars
GROUP BY owner_id;

-- ── Promo codes ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_codes (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
    -- case-insensitive, stored uppercase
    reward_type     TEXT NOT NULL,
    -- "bonus_stars" | "feature_unlock" | "group_slot" | "clone_slot"
    reward_value    INT DEFAULT 0,
    -- for bonus_stars: number of stars
    -- for feature_unlock: 0 (feature in reward_feature)
    reward_feature  TEXT DEFAULT '',
    -- for feature_unlock: e.g. "feat_music"
    reward_days     INT DEFAULT 30,
    -- for feature/slot unlocks: how many days
    max_uses        INT DEFAULT 1,
    -- 0 = unlimited
    current_uses    INT DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    -- NULL = never expires
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      BIGINT,            -- admin who created it
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Promo code redemptions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_redemptions (
    id          BIGSERIAL PRIMARY KEY,
    code_id     BIGINT REFERENCES promo_codes(id),
    owner_id    BIGINT NOT NULL,
    redeemed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code_id, owner_id)
    -- one redemption per user per code
);
