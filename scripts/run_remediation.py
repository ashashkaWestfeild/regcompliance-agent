"""Stage 5 (dev set): remediation drafts for the top-ranked open gaps.

Run after run_risk.py. For the N gaps with the highest priority score it drafts an action, a
suggested policy wording and a success criterion (one model call each; owner, due date and the
fidelity check are rules, see src/regcomp/remediation.py), stores them in `remediation` and
prints them. Drafts are proposals for a reviewer; nothing is closed or accepted here.

    uv run python scripts/run_remediation.py --top 10
"""

import argparse
import time
from datetime import date

from regcomp.db import connect
from regcomp.remediation import draft


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    today = date.today()
    with connect(autocommit=True) as conn:
        gaps = conn.execute(
            "SELECT g.id, g.type, g.residual_risk, g.priority_score, g.rationale,"
            " o.source_clause_ref, o.source_span->>'quote', c.source_span->>'quote'"
            " FROM gap g JOIN obligation o ON o.id = g.obligation_id"
            " LEFT JOIN control c ON c.id = g.control_id"
            # drafts go to the high-confidence tier; a review-queue item is confirmed first
            " WHERE g.status = 'open' AND g.tier = 'high' AND g.superseded_at IS NULL"
            " ORDER BY g.priority_score DESC, o.source_clause_ref"
            " LIMIT %s",
            (args.top,),
        ).fetchall()
        conn.execute("DELETE FROM remediation")
        fell_back = 0
        for n, (gid, gap_type, residual, score, reason, ref, quote, passage) in enumerate(gaps, 1):
            r = draft(
                {
                    "type": gap_type,
                    "residual": residual,
                    "obligation": quote,
                    "policy_passage": passage,
                    "reason": reason,
                },
                today,
                conn,
            )
            conn.execute(
                "INSERT INTO remediation (gap_id, action, owner_line, owner_role, due_date,"
                " success_criterion, drafted_by_model) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    gid,
                    r["action"],
                    r["owner_line"],
                    r["owner_role"],
                    r["due_date"],
                    r["success_criterion"],
                    r["drafted_by"],
                ),
            )
            fell_back += bool(r["checks"])
            print(
                f"[{time.strftime('%H:%M:%S')}] drafted {n}/{len(gaps)}\n"
                f"  RBI {ref} | {gap_type} | residual {residual} ({score:.2f}) | "
                f"{r['owner_line']} {r['owner_role']} | due {r['due_date']}\n"
                f"  action: {r['action']}\n  closes when: {r['success_criterion']}\n"
                f"  drafted by: {r['drafted_by']}"
                + (f"\n  fidelity check: {'; '.join(r['checks'])}" if r["checks"] else ""),
                flush=True,
            )
    print(f"remediation drafts: {len(gaps)}; replaced by the verbatim obligation: {fell_back}")


if __name__ == "__main__":
    main()
