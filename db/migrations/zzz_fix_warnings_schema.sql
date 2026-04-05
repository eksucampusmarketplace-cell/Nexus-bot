-- Migration: Fix warnings table schema
-- This migration ensures the warnings table has the correct column names
-- regardless of installation order of previous migrations.
-- The zzz prefix ensures this runs last.

DO $$
BEGIN
    -- Rename by_user_id → issued_by if the old column exists
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

-- Add issued_by column if it doesn't exist (for fresh installs)
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

-- Add is_active column if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'warnings' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE warnings ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        NULL;
END $$;

-- Ensure issued_at column exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'warnings' AND column_name = 'issued_at'
    ) THEN
        ALTER TABLE warnings ADD COLUMN issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
EXCEPTION
    WHEN duplicate_column THEN
        NULL;
END $$;
