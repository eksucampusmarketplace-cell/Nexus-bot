-- Add risk free field to music_userbots table
ALTER TABLE music_userbots ADD COLUMN IF NOT EXISTS risk_free INTEGER DEFAULT 0;
ALTER TABLE music_userbots ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;
ALTER TABLE music_userbots ADD COLUMN IF NOT EXISTS ban_reason TEXT;
