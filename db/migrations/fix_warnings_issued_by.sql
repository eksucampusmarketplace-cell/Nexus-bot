-- Migration: Fix warnings table column name
-- The warnings table was created with 'by_user_id' in add_games_expansion.sql
-- but the code expects 'issued_by' column. This migration renames the column.

-- Rename by_user_id to issued_by if the column exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'warnings' AND column_name = 'by_user_id'
    ) THEN
        ALTER TABLE warnings RENAME COLUMN by_user_id TO issued_by;
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        -- issued_by already exists
        NULL;
END $$;

-- Add is_active column if missing (for consistency with other moderation tables)
ALTER TABLE warnings ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Ensure issued_by column exists (for new installations that may not have by_user_id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'warnings' AND column_name = 'issued_by'
    ) THEN
        ALTER TABLE warnings ADD COLUMN issued_by BIGINT;
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        NULL;
END $$;