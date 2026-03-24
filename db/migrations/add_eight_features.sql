-- Migration: Add 8 new features
-- 1. Scheduled Messages (admin command support - table already exists)
-- 2. Richer Analytics Dashboard (uses existing tables, no new schema needed)
-- 3. Welcome Quiz
-- 4. Auto-Role by XP
-- 5. AI Auto-Moderation
-- 6. Polls with Stakes
-- 7. Federation Leaderboards
-- 8. Bot Personality Presets (uses existing persona columns)

-- ── Feature 3: Welcome Quiz ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS welcome_quiz_questions (
    id          SERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    question    TEXT NOT NULL,
    options     JSONB NOT NULL DEFAULT '[]',
    correct_idx INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN DEFAULT TRUE,
    created_by  BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_questions_chat
    ON welcome_quiz_questions (chat_id) WHERE is_active = TRUE;

-- Track pending quiz challenges
CREATE TABLE IF NOT EXISTS welcome_quiz_pending (
    id          SERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    question_id INT REFERENCES welcome_quiz_questions(id),
    message_id  BIGINT,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, user_id)
);

-- ── Feature 4: Auto-Role by XP ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auto_role_rules (
    id          SERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    bot_id      BIGINT NOT NULL,
    role_id     INT REFERENCES roles(id) ON DELETE CASCADE,
    xp_threshold INT NOT NULL DEFAULT 0,
    level_threshold INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, bot_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_auto_role_chat
    ON auto_role_rules (chat_id, bot_id) WHERE is_active = TRUE;

-- ── Feature 5: AI Auto-Moderation ───────────────────────────────────────────
ALTER TABLE groups ADD COLUMN IF NOT EXISTS ai_automod_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS ai_automod_sensitivity REAL DEFAULT 0.7;

-- ── Feature 6: Polls with Stakes ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stake_polls (
    id              SERIAL PRIMARY KEY,
    chat_id         BIGINT NOT NULL,
    creator_id      BIGINT NOT NULL,
    question        TEXT NOT NULL,
    options         JSONB NOT NULL DEFAULT '[]',
    tg_poll_id      TEXT,
    tg_message_id   BIGINT,
    min_bet         INT NOT NULL DEFAULT 1,
    max_bet         INT NOT NULL DEFAULT 100,
    status          TEXT NOT NULL DEFAULT 'open',
    winning_option  INT,
    total_pool      INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS stake_bets (
    id          SERIAL PRIMARY KEY,
    poll_id     INT REFERENCES stake_polls(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL,
    option_idx  INT NOT NULL,
    amount      INT NOT NULL,
    payout      INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(poll_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_stake_polls_chat
    ON stake_polls (chat_id) WHERE status = 'open';

-- ── Feature 7: Federation Leaderboards ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS federation_weekly_xp (
    id              SERIAL PRIMARY KEY,
    federation_id   INT,
    chat_id         BIGINT NOT NULL,
    week_start      DATE NOT NULL,
    total_xp        BIGINT DEFAULT 0,
    member_count    INT DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(federation_id, chat_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_fed_weekly_xp_week
    ON federation_weekly_xp (federation_id, week_start);
