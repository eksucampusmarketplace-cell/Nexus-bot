# Migration Fix Guide - fix_schema_v2.sql

## Problem

The application fails to start with this error:

```
[ERROR] migrate | [MIGRATE] FAILED on fix_schema_v2.sql: column "sticker" of relation "locks" already exists
[CRITICAL] main | [STARTUP] ❌ Migration failed — cannot start
```

## Root Cause

The `fix_schema_v2.sql` migration attempts to:
1. Add new columns (sticker, gif, link, etc.) to the `locks` table
2. Rename old columns (stickers → sticker, etc.)

The problem is that when a previous migration attempt was interrupted or partially applied, the rename operations may have already occurred, creating the "sticker" column. Then when the migration tries to `ADD COLUMN IF NOT EXISTS sticker`, it fails because PostgreSQL's `IF NOT EXISTS` check doesn't account for the fact that the column was created via a rename.

## Solution

We've fixed the migration file to execute the RENAME operations FIRST, before attempting to ADD the columns. This prevents the conflict.

### Option 1: Apply the Fixed Migration (Recommended)

The `fix_schema_v2.sql` file has been updated to perform renames before adds. To apply it:

1. **If you have database access, remove the failed migration log:**

   ```sql
   DELETE FROM migrations_log WHERE filename = 'fix_schema_v2.sql';
   ```

2. **Restart your application** - it will now run the fixed migration successfully.

### Option 2: Manual Fix via Python Script

If Option 1 doesn't work, use the provided Python script:

```bash
# Ensure SUPABASE_CONNECTION_STRING is set in your environment
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'

# Run the manual fix script
python apply_schema_v2_manually.py
```

This script:
- Applies all schema changes with proper error handling
- Marks the migration as complete in `migrations_log`
- Reports which changes were applied

### Option 3: Manual SQL Fix

If you have direct database access (via Supabase SQL Editor or psql):

1. **Remove the migration log entry:**

   ```sql
   DELETE FROM migrations_log WHERE filename = 'fix_schema_v2.sql';
   ```

2. **Apply the migration manually:**

   ```sql
   -- Step 1: Rename old columns to new names (if they exist)
   DO $$
   BEGIN
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'stickers') THEN
           ALTER TABLE locks RENAME COLUMN stickers TO sticker;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'gifs') THEN
           ALTER TABLE locks RENAME COLUMN gifs TO gif;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'links') THEN
           ALTER TABLE locks RENAME COLUMN links TO link;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'forwards') THEN
           ALTER TABLE locks RENAME COLUMN forwards TO forward;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'polls') THEN
           ALTER TABLE locks RENAME COLUMN polls TO poll;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'contacts') THEN
           ALTER TABLE locks RENAME COLUMN contacts TO contact;
       END IF;
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'locks' AND column_name = 'video_notes') THEN
           ALTER TABLE locks RENAME COLUMN video_notes TO video_note;
       END IF;
   END $$;

   -- Step 2: Add new columns (with IF NOT EXISTS)
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

   -- Step 3: Fix filters table
   ALTER TABLE filters ADD COLUMN IF NOT EXISTS reply_content TEXT;
   DO $$
   BEGIN
       IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'filters' AND column_name = 'response') THEN
           UPDATE filters SET reply_content = response WHERE reply_content IS NULL;
       END IF;
   END $$;
   ALTER TABLE filters ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
   UPDATE filters SET created_at = NOW() WHERE created_at IS NULL;

   -- Step 4: Create blacklist table
   CREATE TABLE IF NOT EXISTS blacklist (
       chat_id BIGINT NOT NULL,
       word TEXT NOT NULL,
       action TEXT DEFAULT 'delete',
       added_by BIGINT,
       added_at TIMESTAMPTZ DEFAULT NOW(),
       PRIMARY KEY (chat_id, word)
   );
   CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON blacklist(chat_id);

   -- Step 5: Add created_at to raid_members
   ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

   -- Step 6: Add is_sudo to users
   ALTER TABLE users ADD COLUMN IF NOT EXISTS is_sudo BOOLEAN DEFAULT FALSE;

   -- Step 7: Create antiraid_sessions
   CREATE TABLE IF NOT EXISTS antiraid_sessions (
       id BIGSERIAL PRIMARY KEY,
       chat_id BIGINT NOT NULL,
       triggered_by TEXT,
       join_count INTEGER DEFAULT 0,
       triggered_at TIMESTAMPTZ DEFAULT NOW(),
       is_active BOOLEAN DEFAULT TRUE
   );
   CREATE INDEX IF NOT EXISTS idx_antiraid_sessions_chat_active ON antiraid_sessions(chat_id, is_active);
   ```

3. **Mark the migration as complete:**

   ```sql
   INSERT INTO migrations_log (filename, applied_at)
   VALUES ('fix_schema_v2.sql', NOW())
   ON CONFLICT (filename) DO UPDATE SET applied_at = NOW();
   ```

4. **Restart your application.**

## Verification

After applying the fix, verify the migration was successful:

```sql
-- Check migration log
SELECT * FROM migrations_log WHERE filename = 'fix_schema_v2.sql';

-- Check locks table has correct columns
SELECT column_name FROM information_schema.columns
WHERE table_name = 'locks'
ORDER BY ordinal_position;
```

Expected columns in `locks` table (among others):
- photo, video, sticker, gif, audio, document, link, forward, poll, contact

## Preventing Future Issues

1. Always let migrations complete fully before stopping the application
2. Don't modify migration files that have already been applied
3. If a migration fails, fix the root cause before restarting
4. Keep backups of your database before major changes

## Additional Tools

Two Python scripts are provided to help fix this issue:

- **`fix_schema_v2_migration.py`** - Checks the current database state and marks the migration as complete if schema changes are already in place
- **`apply_schema_v2_manually.py`** - Applies all schema changes manually with proper error handling

Use these if the SQL fixes don't work for your situation.
