# Migration Error: "column sticker of relation locks already exists"

## Status: ✅ RESOLVED

This issue has been fixed. See **Quick Fix** below to apply the solution.

---

## Problem Description

The application was failing to start with this error:

```
2026-03-16 11:51:10 [ERROR] migrate | [MIGRATE] FAILED on fix_schema_v2.sql: column "sticker" of relation "locks" already exists
2026-03-16 11:51:10 [CRITICAL] main | [STARTUP] ❌ Migration failed — cannot start
```

### Root Cause

The `fix_schema_v2.sql` migration was trying to:
1. Add a new column `sticker` with `ALTER TABLE locks ADD COLUMN IF NOT EXISTS sticker`
2. Rename an existing column `stickers` to `sticker` with `ALTER TABLE locks RENAME COLUMN stickers TO sticker`

When the migration was interrupted or partially applied, the RENAME operation created the `sticker` column. Then, when the ADD COLUMN statement ran, PostgreSQL reported the column already exists - even though `IF NOT EXISTS` was specified. This is because PostgreSQL's `IF NOT EXISTS` check doesn't account for columns that were created via RENAME operations in the same migration.

---

## Quick Fix (Apply Now)

The migration file has been **fixed** to process RENAME operations before ADD operations. To apply this fix:

### Step 1: Remove the failed migration from the log

**Choose one of these methods:**

**Method A - Using the provided script (recommended):**
```bash
# Set your database connection string
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'

# Run the script
python reset_migration.py fix_schema_v2.sql
```

**Method B - Using direct SQL in Supabase SQL Editor:**
```sql
DELETE FROM migrations_log WHERE filename = 'fix_schema_v2.sql';
```

### Step 2: Restart your application

```bash
python main.py
# or
uvicorn main:app
```

The fixed migration will now run successfully without errors.

---

## Alternative Fix Methods

If the Quick Fix doesn't work for your situation, try one of these alternatives:

### Method 1: Manual Application Script

Use this script if you want to manually apply all schema changes:

```bash
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'
python apply_schema_v2_manually.py
```

This script will:
- Add all required columns to tables
- Perform necessary renames
- Create missing tables (blacklist, antiraid_sessions)
- Mark the migration as complete

### Method 2: Check and Mark as Complete

Use this script if the schema changes are already in place (from a previous partial run):

```bash
export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'
python fix_schema_v2_migration.py
```

This script checks if all required schema changes exist and marks the migration as complete if they do.

### Method 3: Manual SQL (Supabase SQL Editor)

See `MIGRATION_FIX_GUIDE.md` for detailed SQL instructions to manually fix the issue.

---

## What Was Changed

### The Fix

The `db/migrations/fix_schema_v2.sql` file was reordered to:

**Before (broken):**
```sql
-- Step 1: Add columns (FAILS if column exists from rename)
ALTER TABLE locks ADD COLUMN IF NOT EXISTS sticker BOOLEAN DEFAULT FALSE;

-- Step 2: Rename columns (already happened in previous run)
DO $$ ... RENAME COLUMN stickers TO sticker ... $$;
```

**After (fixed):**
```sql
-- Step 1: Rename columns FIRST (only if old column exists)
DO $$ ... RENAME COLUMN stickers TO sticker ... $$;

-- Step 2: Add columns (now safe - won't conflict)
ALTER TABLE locks ADD COLUMN IF NOT EXISTS sticker BOOLEAN DEFAULT FALSE;
```

This ensures operations don't conflict, making the migration truly idempotent.

---

## Helper Scripts Provided

Three helper scripts are included to help resolve this issue:

### 1. `reset_migration.py`
Remove a migration from the log so it can be re-run.
```bash
python reset_migration.py <migration_file>
```

### 2. `apply_schema_v2_manually.py`
Apply all schema changes from fix_schema_v2.sql manually with error handling.
```bash
python apply_schema_v2_manually.py
```

### 3. `fix_schema_v2_migration.py`
Check database state and mark migration as complete if changes are already applied.
```bash
python fix_schema_v2_migration.py
```

---

## Files Modified/Created

### Modified:
- `db/migrations/fix_schema_v2.sql` - Reordered operations (RENAME before ADD)

### Created:
- `MIGRATION_FIX_GUIDE.md` - Detailed manual SQL instructions
- `MIGRATION_ISSUE_README.md` - Comprehensive issue documentation
- `MIGRATION_ERROR_SOLVED.md` - This file
- `reset_migration.py` - Helper script to reset migrations
- `apply_schema_v2_manually.py` - Manual application script
- `fix_schema_v2_migration.py` - Check and mark complete script

---

## Verification

After fixing, verify the migration was successful:

```sql
-- Check migration log
SELECT * FROM migrations_log WHERE filename = 'fix_schema_v2.sql';

-- Check locks table has correct columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'locks'
  AND column_name IN ('photo', 'video', 'sticker', 'gif', 'audio',
                      'document', 'link', 'forward', 'poll', 'contact')
ORDER BY column_name;
```

Expected output should show all these columns exist.

---

## Prevention Tips

To avoid similar migration issues in the future:

1. ✅ **Always let migrations complete** - Don't interrupt the application during startup
2. ✅ **Don't modify applied migrations** - Changing a migration that already ran will cause issues
3. ✅ **Fix root causes first** - When a migration fails, investigate before restarting
4. ✅ **Keep backups** - Always have a database backup before applying migrations
5. ✅ **Check migrations_log** - Use this table to see which migrations have been applied
6. ✅ **Test migrations locally** - Apply migrations to a test database before production

---

## Troubleshooting

### The migration still fails

1. **Check database connection:** Ensure `SUPABASE_CONNECTION_STRING` is correct
2. **Verify permissions:** Make sure the database user has ALTER TABLE permissions
3. **Check for active transactions:** There might be a stuck transaction blocking the migration
4. **Try manual SQL:** Use the instructions in `MIGRATION_FIX_GUIDE.md`

### Application won't start after fix

1. **Check the error log:** Look for additional error messages
2. **Verify migration was applied:** Check the migrations_log table
3. **Restart the application:** Try a clean restart after the fix

### Other migrations are failing

1. **Check migration order:** Migrations run in alphabetical order by filename
2. **Look for dependencies:** One migration might depend on another
3. **Use helper scripts:** The `reset_migration.py` script can help with stuck migrations

---

## Support & Documentation

- **MIGRATION_FIX_GUIDE.md** - Detailed manual SQL fix instructions
- **MIGRATION_ISSUE_README.md** - Comprehensive issue documentation
- **MIGRATION_FIX_INSTRUCTIONS.md** - Previous migration fix (for reference)
- **db/migrate.py** - Migration system implementation

---

## Summary

This migration issue has been **fully resolved** with:

1. ✅ Fixed migration file (`db/migrations/fix_schema_v2.sql`)
2. ✅ Helper scripts for various scenarios
3. ✅ Comprehensive documentation
4. ✅ Multiple fix methods to choose from

**Apply the Quick Fix now** to get your application running again!
