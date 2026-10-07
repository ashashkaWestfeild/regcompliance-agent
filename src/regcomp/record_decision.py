"""Run one reviewer decision from the app, and keep it only when it may be saved.

psycopg 3 commits a `conn.transaction()` block that starts a transaction, so a rollback after
review.decide returns has nothing left to undo (found 7 Oct 2026: a simulated decision in the app
was saved). Here the decision runs inside one outer transaction; decide's own block becomes a
savepoint inside it, and a simulation rolls the whole outer transaction back.
"""

import psycopg

from regcomp.review import decide


def record(conn, gap_id: str, decision: str, reviewer: str, reason: str, save: bool) -> dict:
    """What the decision does (as review.decide reports it). Written only when save is True."""
    with conn.transaction():
        out = decide(conn, gap_id, decision, reviewer, reason)
        if not save:
            raise psycopg.Rollback()  # ends the outer block: everything above is undone
    return out
