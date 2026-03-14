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
import glob
import logging
import os
import re

log = logging.getLogger("migrate")

CREATE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS migrations_log (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


def split_sql_statements(sql: str) -> list:
    """
    Split SQL into individual statements, handling:
    - JSON/JSONB values with semicolons inside
    - Multiple ADD COLUMN in single ALTER TABLE
    - Comments
    - Arrays and other complex values
    - Dollar-quoted strings ($$ or $tag$)
    """
    # Remove comments
    lines = []
    for line in sql.splitlines():
        # Remove -- comments but preserve line for statement tracking
        if "--" in line:
            line = line[: line.index("--")]
        lines.append(line)
    sql = "\n".join(lines)

    statements = []
    current_stmt = []
    brace_level = 0
    in_single_quote = False
    in_double_quote = False
    in_dollar_quote = None  # Tracks the tag: e.g., "$$" or "$body$"

    i = 0
    while i < len(sql):
        char = sql[i]

        # Handle dollar quotes
        if in_dollar_quote:
            if sql[i:].startswith(in_dollar_quote):
                tag = in_dollar_quote
                for _ in range(len(tag)):
                    current_stmt.append(sql[i])
                    i += 1
                in_dollar_quote = None
                continue
            current_stmt.append(char)
            i += 1
            continue

        if char == "$" and not in_single_quote and not in_double_quote:
            match = re.match(r"\$[a-zA-Z_0-9]*\$", sql[i:])
            if match:
                in_dollar_quote = match.group(0)
                for _ in range(len(in_dollar_quote)):
                    current_stmt.append(sql[i])
                    i += 1
                continue

        # Track quote states (for string literals)
        if char == "'" and not in_double_quote:
            if in_single_quote and i + 1 < len(sql) and sql[i + 1] == "'":
                # Escaped single quote
                current_stmt.append(char)
                current_stmt.append(sql[i + 1])
                i += 2
                continue
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        # Track brace level for JSON/arrays (but not inside quotes)
        elif char in "{" and not in_single_quote and not in_double_quote:
            brace_level += 1
        elif char in "}" and not in_single_quote and not in_double_quote:
            brace_level -= 1

        current_stmt.append(char)

        # Statement terminator - only at top level (not inside braces or quotes)
        if char == ";" and brace_level == 0 and not in_single_quote and not in_double_quote:
            stmt = "".join(current_stmt).strip()
            if stmt:
                statements.append(stmt)
            current_stmt = []

        i += 1

    # Add any remaining statement
    stmt = "".join(current_stmt).strip()
    if stmt:
        statements.append(stmt)

    return [s for s in statements if s]


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

                # Use proper SQL splitting that handles JSON/arrays
                statements = split_sql_statements(sql)
                for stmt in statements:
                    if stmt.strip():
                        await conn.execute(stmt)

                await conn.execute("INSERT INTO migrations_log (filename) VALUES ($1)", filename)
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
