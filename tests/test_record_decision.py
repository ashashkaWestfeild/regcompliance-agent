"""A simulated decision is rolled back as a whole; a real one is committed (7 Oct fix)."""

import psycopg
import pytest

from regcomp.record_decision import record


class _Tx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.depth += 1
        self.conn.events.append("begin" if self.conn.depth == 1 else "savepoint")

    def __exit__(self, kind, exc, tb):
        self.conn.depth -= 1
        outer = self.conn.depth == 0
        if kind is None:
            self.conn.events.append("commit" if outer else "release")
            return False
        self.conn.events.append("rollback" if outer else "rollback to savepoint")
        return kind is psycopg.Rollback  # psycopg swallows Rollback, re-raises anything else


class _Conn:
    """psycopg's transaction semantics: the outermost block commits, inner ones are savepoints."""

    def __init__(self, status="open"):
        self.depth, self.events, self.status = 0, [], status

    def transaction(self):
        return _Tx(self)

    def execute(self, sql, params=None):
        row = (self.status, "review", None, None, None, None, {})
        return type("C", (), {"fetchone": lambda _self: row})()


def test_a_simulation_is_rolled_back_as_a_whole():
    conn = _Conn()
    out = record(conn, "g1", "confirm", "A. Reviewer", "check", save=False)
    assert conn.events == ["begin", "savepoint", "release", "rollback"]
    assert out["tier"] == "review -> high"  # what it would have done


def test_a_real_decision_is_committed():
    conn = _Conn()
    record(conn, "g1", "confirm", "A. Reviewer", "check", save=True)
    assert conn.events == ["begin", "savepoint", "release", "commit"]


def test_a_refused_decision_writes_nothing():
    conn = _Conn(status="closed")
    with pytest.raises(ValueError, match="gap is closed"):
        record(conn, "g1", "confirm", "A. Reviewer", "check", save=True)
    assert conn.events[-1] == "rollback"
