"""Database connection. The URL comes from DATABASE_URL (.env locally, secrets in CI/cloud).

The connection string is a secret: this module never prints or logs it, and errors report only
the host.
"""

import os
from urllib.parse import urlsplit

import psycopg
from dotenv import load_dotenv


def database_url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL is missing or malformed (expected postgresql://...)")
    return url


def safe_host(url: str) -> str:
    """Host only, for messages; never the credentials."""
    return urlsplit(url).hostname or "?"


def connect(autocommit: bool = False) -> psycopg.Connection:
    url = database_url()
    try:
        return psycopg.connect(url, autocommit=autocommit, connect_timeout=30)
    except psycopg.OperationalError as e:
        # libpq messages can echo parts of the conninfo; keep only the first line and the host.
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise RuntimeError(f"cannot connect to {safe_host(url)}: {first_line}") from None
