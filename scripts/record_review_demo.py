"""Record two reviewer decisions on the d2 copy of the database and export the trail for the app.

    uv run python scripts/record_review_demo.py      # DATABASE_URL must be the d2 copy

The hosted demo never saves a decision without the reviewer code, so no decision has been recorded
on the live database. This demonstration, made by Claude on the author's instruction, records one
confirmation and one dismissal on the d2 copy with regcomp.review.decide (the same code the app
uses) and exports what changed: the gap's status and tier, the mapping verdict, and the
review_override row a dismissal writes. Output: eval/reports/review_trail_d2.json.
"""

import json
import subprocess
from pathlib import Path

from regcomp.db import connect, database_role, database_url
from regcomp.review import decide

OUT = Path("eval/reports/review_trail_d2.json")
REVIEWER = "Claude (demonstration on the d2 copy, on the author's instruction)"
DECISIONS = [
    (
        "4b3f3036-ff85-4a1d-8cb0-8ba052f3c0ce",
        "confirm",
        "Planted gap N05 of the development key: the policy limits intensified monitoring to "
        "high-risk accounts identified at account opening; RBI 41(2) covers all of them.",
    ),
    (
        "dec948d8-b7fc-4d49-a2f0-c0e8a4fb8914",
        "dismiss",
        "RBI paragraph 2 states when the Directions come into force; it places no duty on the bank "
        "to publish an effective date. A false alarm.",
    ),
]


def snapshot(conn, gap_id: str) -> dict:
    row = conn.execute(
        "SELECT o.source_clause_ref, o.action, g.type::text, g.status::text, g.tier,"
        " m.verdict::text, m.status::text FROM gap g JOIN obligation o ON o.id = g.obligation_id"
        " LEFT JOIN mapping m ON m.id = g.mapping_id WHERE g.id = %s",
        (gap_id,),
    ).fetchone()
    keys = ["ref", "obligation", "gap_type", "status", "tier", "mapping_verdict", "mapping_status"]
    return dict(zip(keys, row, strict=True))


def main() -> None:
    if database_role(database_url()) != "d2":
        raise SystemExit("run this against the d2 copy only (REGCOMP_D2_HOST)")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    trail = []
    with connect(autocommit=True) as conn:
        for gap_id, decision, reason in DECISIONS:
            before = snapshot(conn, gap_id)
            result = decide(conn, gap_id, decision, REVIEWER, reason)
            after = snapshot(conn, gap_id)
            trail.append({"gap": gap_id, "decision": decision, "reviewer": REVIEWER,
                          "reason": reason, "before": before, "after": after,
                          "result": result})  # fmt: skip
        overrides = [
            dict(
                zip(
                    ["ref", "old_verdict", "new_verdict", "reason", "reviewer", "created_at"],
                    r,
                    strict=True,
                )
            )  # fmt: skip
            for r in conn.execute(
                "SELECT o.source_clause_ref, r.old_verdict::text, r.new_verdict::text, r.reason,"
                " r.reviewer, r.created_at::text FROM review_override r"
                " JOIN mapping m ON m.id = r.mapping_id JOIN obligation o ON o.id = m.obligation_id"
            ).fetchall()
        ]
    out = {
        "what": "Two reviewer decisions recorded on the d2 copy of the database (not the live "
        "demo database) with the app's own decision code. Development data.",
        "code_commit": commit,
        "decisions": trail,
        "review_override": overrides,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")  # fmt: skip
    for t in trail:
        print(f"{t['decision']}: RBI {t['before']['ref']} {t['result']['status']}, tier "
              f"{t['result']['tier']}, mapping {t['result']['mapping_verdict']}")  # fmt: skip
    print(f"{OUT}: {len(trail)} decisions, {len(overrides)} review_override row(s)")


if __name__ == "__main__":
    main()
