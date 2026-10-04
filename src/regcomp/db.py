"""Database connection. The URL comes from DATABASE_URL (.env locally, secrets in CI/cloud).

The connection string is a secret: this module never prints or logs it, and errors report only
the host.

Guard (PROBLEMS_LOG P-058): local .env files name the live and the d2 database hosts
(REGCOMP_LIVE_HOST, REGCOMP_D2_HOST; hostnames only). Every process says once, on stderr, which
database it is connected to. A connection to the live host is read-only at the database level
(Postgres refuses any write) unless REGCOMP_ALLOW_LIVE=1 is set for that one command. A host with
no label (the hosted app, CI) is not restricted.
"""

import os
import sys
from urllib.parse import urlsplit

import psycopg
from dotenv import load_dotenv

_announced: set[str] = set()


def database_url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL is missing or malformed (expected postgresql://...)")
    return url


def safe_host(url: str) -> str:
    """Host only, for messages; never the credentials."""
    return urlsplit(url).hostname or "?"


def database_role(url: str, env=os.environ) -> str:
    """'live', 'd2' or 'unlabelled', from the host names in REGCOMP_LIVE_HOST / REGCOMP_D2_HOST."""
    host = safe_host(url)
    if host == env.get("REGCOMP_LIVE_HOST", "").strip():
        return "live"
    if host == env.get("REGCOMP_D2_HOST", "").strip():
        return "d2"
    return "unlabelled"


def live_read_only(role: str, env=os.environ) -> bool:
    """True when this connection must refuse writes: the live database without the opt-in."""
    return role == "live" and env.get("REGCOMP_ALLOW_LIVE", "").strip() != "1"


def connect(autocommit: bool = False) -> psycopg.Connection:
    url = database_url()
    role = database_role(url)
    read_only = live_read_only(role)
    if role not in _announced:
        _announced.add(role)
        note = {
            "live": " (read-only; set REGCOMP_ALLOW_LIVE=1 for an approved write)"
            if read_only
            else " (WRITES ALLOWED: REGCOMP_ALLOW_LIVE=1)",
            "d2": "",
            "unlabelled": f" ({safe_host(url)}, no label)",
        }[role]
        print(f"database: {role}{note}", file=sys.stderr, flush=True)
    kwargs = {"options": "-c default_transaction_read_only=on"} if read_only else {}
    try:
        return psycopg.connect(url, autocommit=autocommit, connect_timeout=30, **kwargs)
    except psycopg.OperationalError as e:
        # libpq messages can echo parts of the conninfo; keep only the first line and the host.
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise RuntimeError(f"cannot connect to {safe_host(url)}: {first_line}") from None
