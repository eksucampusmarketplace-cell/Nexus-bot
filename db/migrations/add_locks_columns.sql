-- Add lock_* columns to groups table for automod settings
-- These are used to store individual lock settings in the groups table
-- IDEMPOTENT - safe to run multiple times

-- Media locks
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_photo BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_video BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_sticker BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_gif BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_voice BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_audio BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_document BOOLEAN DEFAULT FALSE;

-- Communication locks
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_link BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_forward BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_poll BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_contact BOOLEAN DEFAULT FALSE;

-- Additional content locks
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_username BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_bot_inviter BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_website BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_channel BOOLEAN DEFAULT FALSE;

-- Content filters
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_porn BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_hashtag BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_unofficial_tg BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS lock_userbots BOOLEAN DEFAULT FALSE;

-- Anti-flood settings
ALTER TABLE groups ADD COLUMN IF NOT EXISTS antiflood BOOLEAN DEFAULT FALSE;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS antiflood_limit INTEGER DEFAULT 5;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS antiflood_window INTEGER DEFAULT 10;
ALTER TABLE groups ADD COLUMN IF NOT EXISTS antiflood_action TEXT DEFAULT 'mute';

-- Anti-spam settings
ALTER TABLE groups ADD COLUMN IF NOT EXISTS antispam BOOLEAN DEFAULT FALSE;

-- Also ensure locks table has all the required columns
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

-- Rename old column names if they exist (for backward compatibility)
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'stickers') THEN ALTER TABLE locks RENAME COLUMN stickers TO sticker; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'gifs') THEN ALTER TABLE locks RENAME COLUMN gifs TO gif; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'links') THEN ALTER TABLE locks RENAME COLUMN links TO link; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'forwards') THEN ALTER TABLE locks RENAME COLUMN forwards TO forward; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'polls') THEN ALTER TABLE locks RENAME COLUMN polls TO poll; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'contacts') THEN ALTER TABLE locks RENAME COLUMN contacts TO contact; END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'video_notes') THEN ALTER TABLE locks RENAME COLUMN video_notes TO video_note; END IF; END $$;
