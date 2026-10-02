"""Stage 4 (dev set): rank the open gaps with the fixed risk rubric (data/risk_rubric.yaml).

Run after run_map.py and run_tests.py. Sets inherent_risk, residual_risk and priority_score on
every gap in Postgres and prints the ranking; the judge's rationale is left as written.

    uv run python scripts/run_risk.py            # score and print the top 15
    uv run python scripts/run_risk.py --top 40
"""

import argparse
from collections import Counter

from regcomp.db import connect
from regcomp.ingest.rbi_html import parse_file
from regcomp.risk import assess

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    heading = {
        c.ref: " | ".join(h for h in (c.chapter, c.section) if h)
        for c in parse_file(REGULATION).clauses
    }
    with connect(autocommit=True) as conn:
        gaps = conn.execute(
            "SELECT g.id, g.type, o.source_clause_ref, o.action, o.source_span->>'quote'"
            " FROM gap g JOIN obligation o ON o.id = g.obligation_id WHERE g.status = 'open'"
        ).fetchall()
        ranked = []
        with conn.cursor() as cur:
            for gid, gap_type, ref, action, quote in gaps:
                risk = assess(f"{action}. {quote}", heading.get(ref, ""), gap_type)
                cur.execute(
                    "UPDATE gap SET inherent_risk = %s, residual_risk = %s, priority_score = %s"
                    " WHERE id = %s",
                    (risk.inherent, risk.residual, risk.priority, gid),
                )
                ranked.append((risk, ref, gap_type, action))
    ranked.sort(key=lambda r: -r[0].priority)
    order = ("critical", "high", "medium", "low")
    by_level = Counter(r[0].residual for r in ranked)
    print(f"gaps scored: {len(ranked)}")
    print("residual risk: " + ", ".join(f"{k} {by_level.get(k, 0)}" for k in order))
    print("\n| # | Priority | Residual | RBI ref | Gap type | Obligation | Why |")
    print("|---|---|---|---|---|---|---|")
    for n, (risk, ref, gap_type, action) in enumerate(ranked[: args.top], 1):
        print(
            f"| {n} | {risk.priority:.2f} | {risk.residual} | {ref} | {gap_type} "
            f"| {action[:70]} | {risk.reasons[0]} |"
        )


if __name__ == "__main__":
    main()
