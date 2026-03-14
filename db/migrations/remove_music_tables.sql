-- Clean removal of all music-related tables
-- Safe to run even if tables don't exist

DROP TABLE IF EXISTS music_userbot_assignments CASCADE;
DROP TABLE IF EXISTS music_settings CASCADE;
DROP TABLE IF EXISTS music_sessions CASCADE;
DROP TABLE IF EXISTS music_queues CASCADE;
DROP TABLE IF EXISTS music_userbots CASCADE;

-- Remove music columns from any other tables if they exist
ALTER TABLE groups
    DROP COLUMN IF EXISTS music_enabled,
    DROP COLUMN IF EXISTS dj_role_id;
