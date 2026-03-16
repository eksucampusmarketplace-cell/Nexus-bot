# Migration Issue Resolution - fix_schema_v2.sql

## Summary

The application was failing to start due to a migration error: `column "sticker" of relation "locks" already exists`.

This issue has been **resolved** by:

1. **Fixed the migration file** (`db/migrations/fix_schema_v2.sql`) - Renamed columns are now processed BEFORE adding new columns
2. **Created helper scripts** - Three Python scripts to help resolve the issue in production environments
3. **Created documentation** - Comprehensive guides for manual fixes

## Quick Fix (Recommended)

The migration file has been fixed. To apply the fix:

### Step 1: Remove the failed migration from the log

**Option A - Using the provided script (easiest):**

```bash
# Set your database connection string
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'

# Reset the migration
python reset_migration.py fix_schema_v2.sql
```

**Option B - Using direct SQL:**

```sql
DELETE FROM migrations_log WHERE filename = 'fix_schema_v2.sql';
```

### Step 2: Restart your application

The fixed migration will now run successfully:

```bash
python main.py
# or
uvicorn main:app
```

---

## Alternative Fixes

If the above doesn't work, use one of these methods:

### Method 1: Manual Application Script

```bash
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'
python apply_schema_v2_manually.py
```

This script applies all schema changes manually and marks the migration as complete.

### Method 2: Check and Mark as Complete

If the schema changes are already in place (from a previous partial run):

```bash
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'
python fix_schema_v2_migration.py
```

This script checks if the changes are already applied and marks the migration as complete.

### Method 3: Manual SQL

See `MIGRATION_FIX_GUIDE.md` for detailed SQL instructions.

---

## What Was Changed?

### Problem

The original `fix_schema_v2.sql` attempted to:
1. `ADD COLUMN IF NOT EXISTS sticker` → FAILED (column already exists from rename)
2. `RENAME COLUMN stickers TO sticker` → Already happened in previous run

PostgreSQL's `IF NOT EXISTS` check doesn't account for columns created via RENAME, causing a conflict.

### Solution

Reordered the migration to:
1. **First**: Rename old columns (stickers → sticker, etc.) - Only if they exist
2. **Then**: Add new columns with `IF NOT EXISTS` - Now safe because renames happened first

This ensures the operations don't conflict, making the migration truly idempotent.

---

## Helper Scripts Provided

### 1. `reset_migration.py`

Remove a migration from the log so it can be re-run.

```bash
python reset_migration.py <migration_file>
```

Example:
```bash
python reset_migration.py fix_schema_v2.sql
```

### 2. `apply_schema_v2_manually.py`

Apply all schema changes from fix_schema_v2.sql manually with error handling.

```bash
export SUPABASE_CONNECTION_STRING='postgresql://...'
python apply_schema_v2_manually.py
```

### 3. `fix_schema_v2_migration.py`

Check database state and mark migration as complete if changes are already applied.

```bash
export SUPABASE_CONNECTION_STRING='postgresql://...'
python fix_schema_v2_migration.py
```

---

## Files Created/Modified

### Modified:
- `db/migrations/fix_schema_v2.sql` - Reordered operations (RENAME before ADD)

### Created:
- `MIGRATION_FIX_GUIDE.md` - Detailed guide with SQL instructions
- `MIGRATION_ISSUE_README.md` - This file
- `reset_migration.py` - Helper script to reset migrations
- `apply_schema_v2_manually.py` - Manual application script
- `fix_schema_v2_migration.py` - Check and mark complete script

---

## Verification

After fixing, verify the migration was successful:

```sql
-- Check migration log
SELECT * FROM migrations_log WHERE filename = 'fix_schema_v2.sql';

-- Check locks table structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'locks'
ORDER BY ordinal_position;
```

Expected columns in `locks` table include:
- photo, video, sticker, gif, audio, document, link, forward, poll, contact

---

## Prevention Tips

1. **Always let migrations complete** - Don't interrupt the application during startup
2. **Don't modify applied migrations** - Changing a migration that already ran will cause issues
3. **Fix root causes first** - When a migration fails, investigate before restarting
4. **Keep backups** - Always have a database backup before applying migrations
5. **Use the migration log** - Check `migrations_log` table to see what's been applied

---

## Getting Help

If you continue to have issues:

1. Check the error logs carefully for details
2. Use the helper scripts to diagnose the database state
3. Try the manual SQL method in `MIGRATION_FIX_GUIDE.md`
4. Verify your `SUPABASE_CONNECTION_STRING` is correct
5. Ensure you have proper permissions to modify the database

---

## Related Documentation

- `MIGRATION_FIX_GUIDE.md` - Detailed manual SQL instructions
- `MIGRATION_FIX_INSTRUCTIONS.md` - Previous migration fix (for reference)
- `db/migrate.py` - Migration system implementation
- `db/migrations/` - All migration SQL files
