-- Migration: add_broadcast_notes_enabled
-- Add broadcast_enabled and notes_enabled columns to groups table

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groups' AND column_name = 'broadcast_enabled'
    ) THEN
        ALTER TABLE groups ADD COLUMN broadcast_enabled BOOLEAN DEFAULT TRUE;
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        NULL;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groups' AND column_name = 'notes_enabled'
    ) THEN
        ALTER TABLE groups ADD COLUMN notes_enabled BOOLEAN DEFAULT TRUE;
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        NULL;
END $$;
