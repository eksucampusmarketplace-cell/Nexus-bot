-- Fix duplicate tables and VIEW/TABLE conflicts from add_billing_tables.sql
-- and add_stars_economy.sql running in alphabetical order.

-- bonus_stars_balance was created as a TABLE in add_billing_tables.sql but
-- add_stars_economy.sql tried to create it as a VIEW. Drop the table and
-- replace with the correct VIEW so balance is always computed from the ledger.
DROP TABLE IF EXISTS bonus_stars_balance;
CREATE OR REPLACE VIEW bonus_stars_balance AS
SELECT owner_id, COALESCE(SUM(amount), 0) AS balance
FROM bonus_stars
GROUP BY owner_id;

-- Ensure referrals table has the referred_at column (add_billing_tables.sql
-- used created_at, add_stars_economy.sql used referred_at).
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS referred_at TIMESTAMPTZ DEFAULT NOW();

-- Ensure promo_codes.reward_feature column exists (add_billing_tables.sql
-- defined it as VARCHAR but add_stars_economy.sql used TEXT DEFAULT '').
ALTER TABLE promo_codes ALTER COLUMN reward_feature SET DEFAULT '';
UPDATE promo_codes SET reward_feature = '' WHERE reward_feature IS NULL;

-- Ensure community_quest_progress has a single primary key (the table was
-- declared with both id BIGSERIAL PRIMARY KEY and PRIMARY KEY(quest_id, user_id)).
-- The composite PK on (quest_id, user_id) is the correct unique constraint.
ALTER TABLE community_quest_progress DROP CONSTRAINT IF EXISTS community_quest_progress_pkey;
ALTER TABLE community_quest_progress ADD PRIMARY KEY (quest_id, user_id);

-- Ensure xp leaderboard orders by xp only (level column may differ from
-- recalculated value if old data existed before the level formula fix).
UPDATE member_xp SET level = (
    CASE
        WHEN xp < 100 THEN 1
        WHEN xp < 250 THEN 2
        WHEN xp < 500 THEN 3
        WHEN xp < 900 THEN 4
        ELSE 5
    END
) WHERE level != (
    CASE
        WHEN xp < 100 THEN 1
        WHEN xp < 250 THEN 2
        WHEN xp < 500 THEN 3
        WHEN xp < 900 THEN 4
        ELSE 5
    END
) AND xp < 900;
