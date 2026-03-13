#!/usr/bin/env python3
"""
Fix for add_reports migration error.

The error indicates that PostgreSQL is seeing an unclosed $$ (dollar-quoted string)
which doesn't match the current migration file. This typically happens when:

1. A previous migration attempt left the database in a bad state
2. An old version of the migration was partially executed
3. There's a cached/pending transaction still active

This script manually applies the required schema changes and marks
the migration as complete in migrations_log.
"""
import asyncio
import os
import sys

async def main():
    # Import here to avoid import errors if asyncpg not available
    try:
        import asyncpg
    except ImportError:
        print("Error: asyncpg not installed")
        print("Install it with: pip install asyncpg")
        return

    # Get connection string from environment
    conn_str = os.environ.get('SUPABASE_CONNECTION_STRING')
    if not conn_str:
        print("Error: SUPABASE_CONNECTION_STRING environment variable not set")
        print("\nTo use this script, you need to set the database connection string:")
        print("  export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'")
        print("\nOr add it to your .env file.")
        return

    print("=" * 70)
    print("Fixing add_reports migration...")
    print("=" * 70)

    conn = None
    try:
        # Connect to database
        print("\n1. Connecting to database...")
        conn = await asyncpg.connect(conn_str)
        print("   ✓ Connected")

        # Check current state
        print("\n2. Checking current database state...")

        reports_table = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'reports'
            )
        """)
        print(f"   Reports table exists: {reports_table}")

        report_count_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'report_count'
            )
        """)
        print(f"   report_count column exists: {report_count_col}")

        migration_logged = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM migrations_log
                WHERE filename = 'add_reports.sql'
            )
        """)
        print(f"   Migration in log: {migration_logged}")

        # If everything is already done, we can exit
        if migration_logged and reports_table and report_count_col:
            print("\n✅ Migration is already complete and up to date!")
            return

        print("\n3. Applying schema changes...")

        # Create reports table if needed
        if not reports_table:
            print("   Creating reports table...")
            await conn.execute("""
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
                )
            """)
            print("   ✓ Reports table created")

            # Create indexes
            print("   Creating indexes...")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_chat_id ON reports (chat_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (chat_id, status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_reporter ON reports (reporter_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_reported ON reports (reported_id)")
            print("   ✓ Indexes created")
        else:
            print("   ✓ Reports table already exists")

        # Add report_count column if needed
        if not report_count_col:
            print("   Adding report_count column to users table...")
            await conn.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS report_count INT NOT NULL DEFAULT 0
            """)
            print("   ✓ report_count column added")
        else:
            print("   ✓ report_count column already exists")

        # Mark migration as complete
        print("\n4. Updating migrations log...")
        await conn.execute("""
            INSERT INTO migrations_log (filename, applied_at)
            VALUES ('add_reports.sql', NOW())
            ON CONFLICT (filename) DO UPDATE SET applied_at = NOW()
        """)
        print("   ✓ Migration marked as complete")

        print("\n" + "=" * 70)
        print("✅ Migration fix completed successfully!")
        print("=" * 70)
        print("\nYou can now start your application normally.")

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ Error occurred")
        print("=" * 70)
        print(f"\n{type(e).__name__}: {e}")
        print("\nIf the error is about an unclosed $$ string, you may need to:")
        print("  1. Connect to your database directly (e.g., via psql or Supabase SQL editor)")
        print("  2. Check for any pending/aborted transactions")
        print("  3. Roll back any incomplete transactions")
        print("  4. Re-run this script")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
