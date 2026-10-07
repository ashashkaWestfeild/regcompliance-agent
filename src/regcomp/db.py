"""Database connection. The URL comes from DATABASE_URL (.env locally, secrets in CI/cloud).

The connection string is a secret: this module never prints or logs it, and errors report only
the host.

Guard (PROBLEMS_LOG P-058; fails closed since 7 Oct 2026): every process says once, on stderr,
which database it is connected to, and the connection is read-only at the database level
(Postgres refuses any write) unless writing there is allowed:

- live: the host named by REGCOMP_LIVE_HOST (Neon's "-pooler" host for the same endpoint counts
  as the same host), or any other remote host whose database is named REGCOMP_LIVE_DB. Writes
  only with REGCOMP_ALLOW_LIVE=1, for one approved command.
- d2: the host named by REGCOMP_D2_HOST. Writes allowed (a working copy).
- local: localhost / 127.0.0.1 / ::1 (the docker-compose database). Writes allowed.
- unlabelled: any other host. Writes only with REGCOMP_ALLOW_UNLABELLED=1 (the hosted app sets
  it, because it writes its model-call cache; a copied .env without labels stays read-only).
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


_LOCAL = {"localhost", "127.0.0.1", "::1"}


def _endpoint(host: str) -> str:
    """The host with Neon's pooler suffix removed from its first label, so the pooled and the
    direct host of one endpoint compare equal ("ep-x-pooler.region..." -> "ep-x.region...")."""
    first, dot, rest = host.lower().partition(".")
    return first.removesuffix("-pooler") + dot + rest


def _database(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def database_role(url: str, env=os.environ) -> str:
    """'live', 'd2', 'local' or 'unlabelled' (see the module docstring)."""
    host = _endpoint(safe_host(url))
    live = env.get("REGCOMP_LIVE_HOST", "").strip()
    d2 = env.get("REGCOMP_D2_HOST", "").strip()
    if live and host == _endpoint(live):  # live first: a mislabelled host fails closed
        return "live"
    if d2 and host == _endpoint(d2):
        return "d2"
    if host in _LOCAL:
        return "local"
    live_db = env.get("REGCOMP_LIVE_DB", "").strip()
    if live_db and _database(url) == live_db:
        return "live"  # same database name on an unknown host: treat it as live
    return "unlabelled"


def read_only(role: str, env=os.environ) -> bool:
    """True when this connection must refuse writes."""
    if role == "live":
        return env.get("REGCOMP_ALLOW_LIVE", "").strip() != "1"
    if role == "unlabelled":
        return env.get("REGCOMP_ALLOW_UNLABELLED", "").strip() != "1"
    return False


def live_read_only(role: str, env=os.environ) -> bool:
    """Kept for callers of the first guard: the live part of read_only."""
    return role == "live" and read_only(role, env)


def connect(autocommit: bool = False) -> psycopg.Connection:
    url = database_url()
    role = database_role(url)
    locked = read_only(role)
    if role not in _announced:
        _announced.add(role)
        note = {
            "live": " (read-only; set REGCOMP_ALLOW_LIVE=1 for an approved write)"
            if locked
            else " (WRITES ALLOWED: REGCOMP_ALLOW_LIVE=1)",
            "d2": "",
            "local": "",
            "unlabelled": f" ({safe_host(url)}, no label; read-only unless"
            " REGCOMP_ALLOW_UNLABELLED=1)"
            if locked
            else f" ({safe_host(url)}, no label; writes allowed by REGCOMP_ALLOW_UNLABELLED=1)",
        }[role]
        print(f"database: {role}{note}", file=sys.stderr, flush=True)
    kwargs = {"options": "-c default_transaction_read_only=on"} if locked else {}
    try:
        return psycopg.connect(url, autocommit=autocommit, connect_timeout=30, **kwargs)
    except psycopg.OperationalError as e:
        # libpq messages can echo parts of the conninfo; keep only the first line and the host.
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise RuntimeError(f"cannot connect to {safe_host(url)}: {first_line}") from None
