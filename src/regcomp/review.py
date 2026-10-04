"""Reviewer decisions on gaps (humans in the lead).

The system opens gaps and sorts them into tiers; only a person changes what a gap *is*:

    confirm   the gap is real: it moves to (or stays in) the high-confidence tier
    dismiss   not a gap (false alarm): closed, and the mapping verdict is corrected to covered
    resolve   the gap was real and is now fixed: closed
    accept    the risk is accepted: status accepted

Every decision is stored with the reviewer's name and reason. A decision that changes the
mapping verdict is also written to review_override, the record later used to check the judge
against human corrections.
"""

from psycopg.types.json import Jsonb

DECISIONS = {
    # decision: (gap status after, tier after, mapping verdict after or None)
    "confirm": ("open", "high", None),
    "dismiss": ("closed", None, "covered"),
    "resolve": ("closed", None, None),
    "accept": ("accepted", None, None),
}


def decide(conn, gap_id: str, decision: str, reviewer: str, reason: str) -> dict:
    """Apply one reviewer decision. Raises ValueError on an unknown decision, an empty reason or
    reviewer, or a gap that is not open."""
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision!r}; use one of {', '.join(DECISIONS)}")
    if not reviewer.strip() or not reason.strip():
        raise ValueError("a reviewer name and a reason are required")
    status, tier, verdict = DECISIONS[decision]
    with conn.transaction():
        row = conn.execute(
            "SELECT g.status::text, g.tier, g.mapping_id, m.verdict::text, m.control_id,"
            " g.control_id, coalesce(g.evidence, '{}'::jsonb) FROM gap g"
            " LEFT JOIN mapping m ON m.id = g.mapping_id WHERE g.id = %s",
            (gap_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"no gap {gap_id}")
        was_status, was_tier, mapping_id, old_verdict, mapping_control, gap_control, evidence = row
        if was_status != "open":
            raise ValueError(f"gap is {was_status}, not open")
        evidence["review"] = {"decision": decision, "reviewer": reviewer, "reason": reason}
        conn.execute(
            "UPDATE gap SET status = %s, tier = coalesce(%s, tier), evidence = %s WHERE id = %s",
            (status, tier, Jsonb(evidence), gap_id),
        )
        changed = None
        if verdict and mapping_id and old_verdict != verdict:
            # a covered mapping must name a passage: the one the gap rested on, else the judge's
            control = mapping_control or gap_control
            if control is not None:
                conn.execute(
                    "INSERT INTO review_override (mapping_id, old_verdict, new_verdict, reason,"
                    " reviewer) VALUES (%s,%s,%s,%s,%s)",
                    (mapping_id, old_verdict, verdict, reason, reviewer),
                )
                conn.execute(
                    "UPDATE mapping SET verdict = %s, control_id = %s, status = 'reviewed'"
                    " WHERE id = %s",
                    (verdict, control, mapping_id),
                )
                changed = f"{old_verdict} -> {verdict}"
        elif mapping_id:
            conn.execute("UPDATE mapping SET status = 'reviewed' WHERE id = %s", (mapping_id,))
    return {
        "gap": str(gap_id),
        "decision": decision,
        "status": f"{was_status} -> {status}",
        "tier": f"{was_tier} -> {tier or was_tier}",
        "mapping_verdict": changed,
    }


def queue(conn, tier: str = "review", limit: int = 50) -> list[dict]:
    """Open gaps of a tier, highest priority first, with what a reviewer needs to decide."""
    rows = conn.execute(
        "SELECT g.id::text, g.type::text, g.residual_risk::text, g.priority_score,"
        " o.source_clause_ref, o.source_span->>'quote', c.source_span->>'quote', g.rationale,"
        " g.evidence FROM gap g JOIN obligation o ON o.id = g.obligation_id"
        " LEFT JOIN control c ON c.id = g.control_id"
        " WHERE g.status = 'open' AND g.tier = %s AND g.superseded_at IS NULL"
        " ORDER BY g.priority_score DESC, o.source_clause_ref LIMIT %s",
        (tier, limit),
    ).fetchall()
    keys = ("id", "type", "residual", "priority", "ref", "obligation", "policy", "why", "evidence")
    return [dict(zip(keys, r, strict=True)) for r in rows]
