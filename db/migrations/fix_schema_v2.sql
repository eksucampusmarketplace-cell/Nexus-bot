-- ── Schema Fixes v2 ─────────────────────────────────────────────────────────
-- Fixes lock column names, filters schema, and adds created_at columns
-- IDEMPOTENT - safe to run multiple times

-- Fix locks table column names (align with miniapp expectations)
-- The miniapp uses: photo, video, sticker, gif, voice, audio, document, link, forward, poll, contact
ALTER TABLE locks ADD COLUMN IF NOT EXISTS photo BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS video BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS sticker BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS gif BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS audio BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS document BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS link BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS forward BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS poll BOOLEAN DEFAULT FALSE;
ALTER TABLE locks ADD COLUMN IF NOT EXISTS contact BOOLEAN DEFAULT FALSE;

-- Keep old columns for backward compatibility
-- (media, stickers, gifs, links, forwards, polls, games, voice, video_notes, contacts)

-- Fix filters table - ensure correct column names
-- The API uses 'reply_content' not 'response'
ALTER TABLE filters ADD COLUMN IF NOT EXISTS reply_content TEXT;

-- Copy data from old response column if exists and reply_content is null
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'filters' AND column_name = 'response') THEN
        UPDATE filters SET reply_content = response WHERE reply_content IS NULL;
    END IF;
END $$;

-- Ensure created_at exists on filters
ALTER TABLE filters ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
UPDATE filters SET created_at = NOW() WHERE created_at IS NULL;

-- Create blacklist table if not exists (for proper blacklist enforcement)
CREATE TABLE IF NOT EXISTS blacklist (
    chat_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    action TEXT DEFAULT 'delete',
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, word)
);

CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON blacklist(chat_id);

-- Add created_at to raid_members if not exists
ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- Add is_sudo support to users table for owner identification
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_sudo BOOLEAN DEFAULT FALSE;

-- Ensure antiraid_sessions table exists (for startup crash fix)
CREATE TABLE IF NOT EXISTS antiraid_sessions (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    triggered_by TEXT,
    join_count INTEGER DEFAULT 0,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_antiraid_sessions_chat_active ON antiraid_sessions(chat_id, is_active);

-- Safe RENAME blocks for Fix 5
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'stickers') THEN ALTER TABLE locks RENAME COLUMN stickers TO sticker; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'gifs') THEN ALTER TABLE locks RENAME COLUMN gifs TO gif; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'links') THEN ALTER TABLE locks RENAME COLUMN links TO link; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'forwards') THEN ALTER TABLE locks RENAME COLUMN forwards TO forward; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'polls') THEN ALTER TABLE locks RENAME COLUMN polls TO poll; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'contacts') THEN ALTER TABLE locks RENAME COLUMN contacts TO contact; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'video_notes') THEN ALTER TABLE locks RENAME COLUMN video_notes TO video_note; END IF; END $$;
