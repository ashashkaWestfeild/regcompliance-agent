"""Apply db/schema.sql to the database in DATABASE_URL, once.

    uv run python scripts/db_init.py            # apply if the schema is not there yet
    uv run python scripts/db_init.py --status   # report only

Safe to re-run: it checks for the schema first and never drops anything.
"""

import argparse
import sys
from pathlib import Path

from regcomp.db import connect, database_url, safe_host

EXPECTED_TABLES = {
    "bank_profile",
    "document",
    "clause",
    "obligation",
    "control",
    "evidence",
    "mapping",
    "control_test",
    "change_event",
    "clause_diff",
    "gap",
    "remediation",
    "review_override",
    "embedding",
}


def status(conn) -> tuple[str, str | None, set[str]]:
    server = conn.execute("SHOW server_version").fetchone()[0]
    vector = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    return server, vector[0] if vector else None, tables


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    print(f"database host: {safe_host(database_url())}")
    with connect(autocommit=True) as conn:
        server, vector, tables = status(conn)
        present = EXPECTED_TABLES & tables
        print(
            f"postgres {server}; pgvector {vector or 'not installed'}; "
            f"schema tables {len(present)}/{len(EXPECTED_TABLES)}"
        )
        if args.status:
            return 0
        if present == EXPECTED_TABLES:
            print("schema already applied; nothing to do")
            return 0
        if present:
            print(
                f"partial schema found ({sorted(present)}); refusing to guess, fix manually",
                file=sys.stderr,
            )
            return 1
        conn.execute(Path("db/schema.sql").read_text(encoding="utf-8"))
        server, vector, tables = status(conn)
        missing = EXPECTED_TABLES - tables
        print(f"applied: pgvector {vector}; missing tables: {sorted(missing) or 'none'}")
        return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
