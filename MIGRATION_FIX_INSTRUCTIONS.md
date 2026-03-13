# Fix for add_reports Migration Error

## Problem

The application fails to start with this error:

```
[ERROR] migrate | [MIGRATE] FAILED on add_reports.sql: unterminated dollar-quoted string at or near "$$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'report_count'
    ) THEN
        ALTER TABLE users ADD COLUMN report_count INT NOT NULL DEFAULT 0"
```

## Root Cause

The error shows PostgreSQL is trying to execute a PL/pgSQL DO block with `$$` (dollar-quoted string) delimiters, but the current `add_reports.sql` file uses the modern `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` syntax.

This typically happens when:
1. A previous migration attempt left the database in a bad state
2. An incomplete transaction or pending query is still active on the database
3. An old version of the migration file was partially executed

## Solution

Run the provided `fix_reports_migration.py` script to manually apply the required schema changes and mark the migration as complete.

### Steps:

1. **Set your database connection string:**

   If you have a `.env` file, ensure it contains:
   ```
   SUPABASE_CONNECTION_STRING=postgresql://user:password@host:5432/dbname
   ```

   Or set it temporarily:
   ```bash
   export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'
   ```

2. **Run the fix script:**

   ```bash
   python fix_reports_migration.py
   ```

   The script will:
   - Check current database state
   - Create the `reports` table (if it doesn't exist)
   - Add the `report_count` column to `users` table (if it doesn't exist)
   - Mark the migration as complete in `migrations_log`

3. **Start your application:**

   After the script completes successfully, you can start your app normally:
   ```bash
   # Or whatever your normal start command is
   python main.py
   # or
   uvicorn main:app
   ```

## Alternative: Manual Database Fix

If the script doesn't work (e.g., due to database connection issues), you can fix it manually using the Supabase SQL editor or psql:

### 1. Check and create the reports table:

```sql
-- Check if table exists
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'reports'
);

-- Create table if it doesn't exist
CREATE TABLE IF NOT EXISTS reports (
    id            BIGSERIAL PRIMARY KEY,
    chat_id       BIGINT      NOT NULL,
    reporter_id   BIGINT      NOT NULL,
    reported_id   BIGINT,
    message_id    BIGINT,
    reason        TEXT        NOT NULL DEFAULT '',
    status        TEXT        NOT NULL DEFAULT 'open',
    resolved_by   BIGINT,
    resolved_at   TIMESTAMPTZ,
    resolution_note TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_reports_chat_id ON reports (chat_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (chat_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_reporter ON reports (reporter_id);
CREATE INDEX IF NOT EXISTS idx_reports_reported ON reports (reported_id);
```

### 2. Add the report_count column:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS report_count INT NOT NULL DEFAULT 0;
```

### 3. Mark the migration as complete:

```sql
INSERT INTO migrations_log (filename, applied_at)
VALUES ('add_reports.sql', NOW())
ON CONFLICT (filename) DO UPDATE SET applied_at = NOW();
```

## If You Still Get the "unterminated dollar-quoted string" Error

This indicates there's an incomplete transaction or pending query in the database. You need to:

1. **Connect to your database directly:**
   - Use the Supabase SQL Editor in the dashboard
   - OR use `psql` command line tool

2. **Check for and terminate any active transactions:**

   ```sql
   -- Check for active connections/transactions
   SELECT * FROM pg_stat_activity
   WHERE state IN ('idle in transaction', 'active');

   -- If you see any, you may need to terminate them
   -- (be careful with this in production!)
   -- SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <problematic_pid>;
   ```

3. **Check for prepared statements or cached query plans:**

   ```sql
   -- This might be an issue with pgbouncer/Supabase
   -- Try connecting directly to the database instead of through pgbouncer
   ```

4. **After cleaning up, run the fix script again:**

   ```bash
   python fix_reports_migration.py
   ```

## Verification

After fixing, verify the migration is complete:

```sql
-- Check migration log
SELECT * FROM migrations_log WHERE filename = 'add_reports.sql';

-- Check reports table
SELECT COUNT(*) FROM reports;

-- Check report_count column
SELECT COUNT(*) FROM users WHERE report_count IS NOT NULL;
```

## Preventing Future Issues

The migration system in `db/migrate.py` is designed to be safe and idempotent. However, if you manually modify migration files or interrupt migrations, issues can occur. To prevent this:

1. Always let migrations complete fully before stopping the application
2. Don't modify migration files that have already been applied
3. If a migration fails, fix the root cause before restarting
4. Keep backups of your database before major changes
