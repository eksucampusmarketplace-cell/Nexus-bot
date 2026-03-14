-- Add updated_at column to bots table and make owner_user_id nullable
ALTER TABLE bots ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE bots ALTER COLUMN owner_user_id DROP NOT NULL;
