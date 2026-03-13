"""
db/migrate.py

Run all pending migrations in order.
Called at bot startup BEFORE the scheduler or any handler starts.

Usage:
    python -m db.migrate
    or imported and called: await run_migrations(pool)

Migration files: db/migrations/*.sql
Executed in filename order (alphabetical).
Tracks applied migrations in a migrations_log table.

Logs prefix: [MIGRATE]
"""

import asyncio
import logging
import os
import glob

log = logging.getLogger("migrate")

CREATE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS migrations_log (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


async def run_migrations(pool):
    """
    Apply all .sql files in db/migrations/ that haven't been applied yet.
    Safe to call on every startup — skips already-applied files.
    """
    async with pool.acquire() as conn:
        await conn.execute(CREATE_LOG_TABLE)

        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        files = sorted(glob.glob(os.path.join(migration_dir, "*.sql")))

        if not files:
            log.warning("[MIGRATE] No migration files found in db/migrations/")
            return

        applied_rows = await conn.fetch("SELECT filename FROM migrations_log")
        applied = set(r["filename"] for r in applied_rows)

        for filepath in files:
            filename = os.path.basename(filepath)
            if filename in applied:
                log.debug(f"[MIGRATE] Skip (already applied): {filename}")
                continue

            log.info(f"[MIGRATE] Applying: {filename}")
            try:
                with open(filepath, "r") as f:
                    sql = f.read()

                def _strip_comments(s):
                    lines = [l for l in s.splitlines() if not l.strip().startswith("--")]
                    return "\n".join(lines).strip()

                statements = [
                    _strip_comments(s) for s in sql.split(";")
                    if _strip_comments(s)
                ]
                for stmt in statements:
                    await conn.execute(stmt)

                await conn.execute(
                    "INSERT INTO migrations_log (filename) VALUES ($1)",
                    filename
                )
                log.info(f"[MIGRATE] Applied: {filename}")

            except Exception as e:
                log.error(f"[MIGRATE] FAILED on {filename}: {e}")
                log.error("[MIGRATE] Stopping — fix this migration before continuing")
                raise


if __name__ == "__main__":
    import asyncpg

    async def main():
        db = await asyncpg.create_pool(
            os.environ["SUPABASE_CONNECTION_STRING"],
            statement_cache_size=0,
        )
        await run_migrations(db)
        await db.close()
        print("Migrations complete.")

    asyncio.run(main())
