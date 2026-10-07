"""Reviewer decisions: validated before anything is written."""

import pytest

from regcomp.review import DECISIONS, decide


def test_decisions_and_their_effects_are_fixed():
    assert set(DECISIONS) == {"confirm", "dismiss", "resolve", "accept"}
    assert DECISIONS["confirm"] == ("open", "high", None)
    assert DECISIONS["dismiss"][2] == "covered"  # a false alarm corrects the verdict
    assert DECISIONS["accept"][0] == "accepted" and DECISIONS["resolve"][0] == "closed"


def test_a_decision_needs_a_known_action_a_reviewer_and_a_reason():
    with pytest.raises(ValueError, match="unknown decision"):
        decide(None, "g1", "delete", "A. Reviewer", "because")
    with pytest.raises(ValueError, match="reviewer name and a reason"):
        decide(None, "g1", "dismiss", "", "because")
    with pytest.raises(ValueError, match="reviewer name and a reason"):
        decide(None, "g1", "dismiss", "A. Reviewer", "  ")


def test_reviewer_code_check():
    from regcomp.reviewer_code import code_matches

    assert code_matches("s3cret-code", "s3cret-code")
    assert not code_matches("wrong", "s3cret-code")
    assert not code_matches("", "s3cret-code")
    assert not code_matches("anything", "")  # no code configured: always a simulation
    assert not code_matches("", "")


class _Conn:
    """Records statements; the gap is open, with no mapping."""

    def __init__(self):
        self.sql = []

    def transaction(self):
        import contextlib

        return contextlib.nullcontext()

    def execute(self, sql, params=None):
        self.sql.append(sql)
        row = ("open", "review", None, None, None, None, {})
        return type("C", (), {"fetchone": lambda _self: row})()


def test_a_decision_locks_the_gap_row_before_reading_its_status():
    conn = _Conn()
    out = decide(conn, "g1", "confirm", "A. Reviewer", "planted gap")
    assert "FOR UPDATE OF g" in conn.sql[0]  # read and lock in one statement
    assert conn.sql[1].startswith("UPDATE gap SET status")
    assert out["status"] == "open -> open" and out["tier"] == "review -> high"
