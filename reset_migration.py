#!/usr/bin/env python3
"""
Reset a failed migration in migrations_log.

This script removes a migration from the migrations_log table so it can be re-run.
Useful when a migration failed and you've fixed the migration file.

Usage:
    python reset_migration.py fix_schema_v2.sql
"""

import asyncio
import asyncpg
import os
import sys


async def reset_migration(filename):
    """Remove a migration from migrations_log."""

    connection_string = os.environ.get("SUPABASE_CONNECTION_STRING")

    if not connection_string:
        print("ERROR: SUPABASE_CONNECTION_STRING not found in environment")
        print("\nPlease set it:")
        print("  export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)

    print("Connecting to database...")
    conn = await asyncpg.connect(connection_string)

    try:
        # Check if migration exists in log
        result = await conn.fetchval(
            "SELECT applied_at FROM migrations_log WHERE filename = $1",
            filename
        )

        if result:
            print(f"\nFound migration '{filename}' applied at {result}")

            # Confirm deletion
            confirm = input("Remove this migration from log so it can be re-run? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Aborted.")
                return

            # Delete the migration
            await conn.execute(
                "DELETE FROM migrations_log WHERE filename = $1",
                filename
            )
            print(f"✓ Removed '{filename}' from migrations_log")
            print("\nThe migration will be re-run on next application startup.")

        else:
            print(f"\nMigration '{filename}' not found in migrations_log")
            print("This migration has not been applied yet.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reset_migration.py <migration_filename>")
        print("\nExample:")
        print("  python reset_migration.py fix_schema_v2.sql")
        sys.exit(1)

    filename = sys.argv[1]
    asyncio.run(reset_migration(filename))
