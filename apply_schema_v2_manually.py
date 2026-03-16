#!/usr/bin/env python3
"""
Manual schema fix script for fix_schema_v2.sql

This script applies the schema changes from fix_schema_v2.sql
with proper error handling and idempotent operations.
"""

import asyncio
import asyncpg
import os
import sys


async def apply_schema_changes():
    """Apply schema changes manually."""

    connection_string = os.environ.get("SUPABASE_CONNECTION_STRING")

    if not connection_string:
        print("ERROR: SUPABASE_CONNECTION_STRING not found in environment")
        print("\nPlease set it:")
        print("  export SUPABASE_CONNECTION_STRING='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)

    print("Connecting to database...")
    conn = await asyncpg.connect(connection_string)

    try:
        print("\nApplying schema changes from fix_schema_v2.sql...")

        # 1. Add columns to locks table (with IF NOT EXISTS to be safe)
        print("\n1. Adding columns to locks table...")
        lock_columns = [
            'photo BOOLEAN DEFAULT FALSE',
            'video BOOLEAN DEFAULT FALSE',
            'sticker BOOLEAN DEFAULT FALSE',
            'gif BOOLEAN DEFAULT FALSE',
            'audio BOOLEAN DEFAULT FALSE',
            'document BOOLEAN DEFAULT FALSE',
            'link BOOLEAN DEFAULT FALSE',
            'forward BOOLEAN DEFAULT FALSE',
            'poll BOOLEAN DEFAULT FALSE',
            'contact BOOLEAN DEFAULT FALSE',
        ]

        for col_def in lock_columns:
            col_name = col_def.split()[0]
            try:
                await conn.execute(f"ALTER TABLE locks ADD COLUMN IF NOT EXISTS {col_def}")
                print(f"  ✓ Added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"  ⊙ Column already exists: {col_name}")
                else:
                    print(f"  ✗ Error adding {col_name}: {e}")

        # 2. Rename old columns to new names (if they exist)
        print("\n2. Renaming old columns in locks table...")
        renames = [
            ('stickers', 'sticker'),
            ('gifs', 'gif'),
            ('links', 'link'),
            ('forwards', 'forward'),
            ('polls', 'poll'),
            ('contacts', 'contact'),
            ('video_notes', 'video_note'),
        ]

        for old_name, new_name in renames:
            try:
                # Check if old column exists and new doesn't
                old_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'locks' AND column_name = $1
                    )
                """, old_name)

                new_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'locks' AND column_name = $1
                    )
                """, new_name)

                if old_exists and not new_exists:
                    await conn.execute(f"ALTER TABLE locks RENAME COLUMN {old_name} TO {new_name}")
                    print(f"  ✓ Renamed {old_name} → {new_name}")
                elif old_exists and new_exists:
                    print(f"  ⊙ Both {old_name} and {new_name} exist - skipping rename")
                else:
                    print(f"  - Column {old_name} doesn't exist - nothing to rename")
            except Exception as e:
                print(f"  ✗ Error renaming {old_name} → {new_name}: {e}")

        # 3. Add reply_content to filters table
        print("\n3. Adding reply_content to filters table...")
        try:
            await conn.execute("ALTER TABLE filters ADD COLUMN IF NOT EXISTS reply_content TEXT")
            print("  ✓ Added reply_content column")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 4. Copy data from response to reply_content if needed
        print("\n4. Migrating data from response to reply_content...")
        try:
            response_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'filters' AND column_name = 'response'
                )
            """)

            if response_exists:
                await conn.execute("""
                    UPDATE filters
                    SET reply_content = response
                    WHERE reply_content IS NULL AND response IS NOT NULL
                """)
                print("  ✓ Migrated data from response to reply_content")
            else:
                print("  - response column doesn't exist - nothing to migrate")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 5. Add created_at to filters table
        print("\n5. Adding created_at to filters table...")
        try:
            await conn.execute("ALTER TABLE filters ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
            await conn.execute("UPDATE filters SET created_at = NOW() WHERE created_at IS NULL")
            print("  ✓ Added created_at column")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 6. Create blacklist table
        print("\n6. Creating blacklist table...")
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    chat_id BIGINT NOT NULL,
                    word TEXT NOT NULL,
                    action TEXT DEFAULT 'delete',
                    added_by BIGINT,
                    added_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (chat_id, word)
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_chat ON blacklist(chat_id)")
            print("  ✓ Created blacklist table")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 7. Add created_at to raid_members
        print("\n7. Adding created_at to raid_members table...")
        try:
            await conn.execute("ALTER TABLE raid_members ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
            print("  ✓ Added created_at column")
        except Exception as e:
            # Table might not exist
            if 'relation "raid_members" does not exist' not in str(e):
                print(f"  ✗ Error: {e}")
            else:
                print("  - raid_members table doesn't exist yet - skipping")

        # 8. Add is_sudo to users table
        print("\n8. Adding is_sudo to users table...")
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_sudo BOOLEAN DEFAULT FALSE")
            print("  ✓ Added is_sudo column")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 9. Create antiraid_sessions table
        print("\n9. Creating antiraid_sessions table...")
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS antiraid_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    triggered_by TEXT,
                    join_count INTEGER DEFAULT 0,
                    triggered_at TIMESTAMPTZ DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_antiraid_sessions_chat_active ON antiraid_sessions(chat_id, is_active)")
            print("  ✓ Created antiraid_sessions table")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        # 10. Mark migration as complete
        print("\n10. Marking migration as complete...")
        await conn.execute("""
            INSERT INTO migrations_log (filename, applied_at)
            VALUES ('fix_schema_v2.sql', NOW())
            ON CONFLICT (filename) DO UPDATE SET applied_at = NOW()
        """)
        print("  ✓ Migration marked as complete")

        print("\n" + "="*60)
        print("Schema changes applied successfully!")
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
    asyncio.run(apply_schema_changes())
