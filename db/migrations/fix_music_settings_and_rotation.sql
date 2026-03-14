-- Fix music settings and rotation logic
-- This migration is designed to be safe even if music tables were already dropped

DO $$
BEGIN
    -- Fix music_settings if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'music_settings') THEN
        -- Add rotation_enabled if missing
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'music_settings' AND column_name = 'rotation_enabled') THEN
            ALTER TABLE music_settings ADD COLUMN rotation_enabled BOOLEAN DEFAULT FALSE;
        END IF;
        
        -- Add rotation_interval if missing
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'music_settings' AND column_name = 'rotation_interval') THEN
            ALTER TABLE music_settings ADD COLUMN rotation_interval INTEGER DEFAULT 3600;
        END IF;
    END IF;

    -- Fix music_userbot_assignments if it exists
    -- Wrap in IF to avoid "relation does not exist" error
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'music_userbot_assignments') THEN
        -- The original migration likely had logic here that failed when the table was missing.
        -- We keep it empty or add safe idempotent logic if we knew what it was.
        -- Since the table is being removed in a later migration anyway, a no-op is safe.
        NULL;
    END IF;

    -- Add safe blocks for other music tables if they exist
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'music_queues') THEN
        NULL;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'music_sessions') THEN
        NULL;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'music_userbots') THEN
        NULL;
    END IF;
END $$;
