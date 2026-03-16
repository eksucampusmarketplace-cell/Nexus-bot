#!/usr/bin/env python3
"""
Fix for fix_schema_v2.sql migration error.

Problem: column "sticker" of relation "locks" already exists

This happens when the migration was partially applied - the rename operations
happened but the ADD COLUMN IF NOT EXISTS statements are failing.

Solution: Mark the migration as complete in migrations_log table, since the
schema changes are already in place.
"""

import asyncio
import asyncpg
import os
import sys


async def check_and_fix_migration():
    """Check database state and fix the migration."""

    # Get connection string from environment or .env file
    connection_string = os.environ.get("SUPABASE_CONNECTION_STRING")

    if not connection_string:
        print("ERROR: SUPABASE_CONNECTION_STRING not found in environment")
        print("\nPlease set it:")
        print("  export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)

    print("Connecting to database...")
    conn = await asyncpg.connect(connection_string)

    try:
        # Check if migration is already recorded
        result = await conn.fetchval(
            "SELECT filename FROM migrations_log WHERE filename = 'fix_schema_v2.sql'"
        )

        if result:
            print("✓ Migration 'fix_schema_v2.sql' is already recorded in migrations_log")
            print("  No action needed.")
            return

        # Check current state of locks table columns
        print("\nChecking locks table columns...")
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'locks'
            ORDER BY ordinal_position
        """)

        print(f"Found {len(columns)} columns in locks table:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")

        # Check for the new column names expected by miniapp
        expected_columns = ['photo', 'video', 'sticker', 'gif', 'audio', 'document',
                          'link', 'forward', 'poll', 'contact']

        existing_new_columns = []
        existing_old_columns = []

        for col in columns:
            col_name = col['column_name']
            if col_name in expected_columns:
                existing_new_columns.append(col_name)
            elif col_name in ['stickers', 'gifs', 'links', 'forwards', 'polls', 'contacts']:
                existing_old_columns.append(col_name)

        print(f"\nNew format columns found: {existing_new_columns}")
        print(f"Old format columns found: {existing_old_columns}")

        # If new columns exist, the schema changes are already in place
        if existing_new_columns:
            print("\n✓ Schema changes appear to be already applied")
            print("  Marking migration as complete...")

            await conn.execute(
                "INSERT INTO migrations_log (filename, applied_at) VALUES ($1, NOW())",
                'fix_schema_v2.sql'
            )
            print("✓ Migration marked as complete in migrations_log")

        else:
            print("\n✗ New columns not found - migration may not have been applied at all")
            print("  This might indicate a different issue.")
            sys.exit(1)

        # Verify other expected schema changes
        print("\nVerifying other schema changes...")

        # Check filters table for reply_content column
        has_reply_content = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'filters' AND column_name = 'reply_content'
            )
        """)
        print(f"  - filters.reply_content: {'✓' if has_reply_content else '✗'}")

        # Check filters table for created_at column
        filters_created_at = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'filters' AND column_name = 'created_at'
            )
        """)
        print(f"  - filters.created_at: {'✓' if filters_created_at else '✗'}")

        # Check blacklist table
        has_blacklist = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'blacklist'
            )
        """)
        print(f"  - blacklist table: {'✓' if has_blacklist else '✗'}")

        # Check antiraid_sessions table
        has_antiraid = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'antiraid_sessions'
            )
        """)
        print(f"  - antiraid_sessions table: {'✓' if has_antiraid else '✗'}")

        # Check users table for is_sudo
        has_is_sudo = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'is_sudo'
            )
        """)
        print(f"  - users.is_sudo: {'✓' if has_is_sudo else '✗'}")

        print("\n" + "="*60)
        print("Migration fix complete!")
        print("="*60)
        print("\nYou can now start your application normally:")
        print("  python main.py")
        print("  or")
        print("  uvicorn main:app")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_and_fix_migration())
