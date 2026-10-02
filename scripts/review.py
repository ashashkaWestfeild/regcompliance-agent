"""Reviewer's command line: list a tier of open gaps, or record a decision on one.

    uv run python scripts/review.py                      # the review queue
    uv run python scripts/review.py --tier high
    uv run python scripts/review.py --gap <id> --decision dismiss --reviewer "A. Reviewer" \\
        --reason "the policy states this in clause 12"

Decisions: confirm (real gap), dismiss (false alarm; the verdict is corrected to covered),
resolve (fixed), accept (risk accepted). The UI's review page uses the same functions.
"""

import argparse

from regcomp.db import connect
from regcomp.review import DECISIONS, decide, queue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="review", choices=["review", "high"])
    ap.add_argument("--gap")
    ap.add_argument("--decision", choices=list(DECISIONS))
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--reason", default="")
    args = ap.parse_args()
    with connect(autocommit=True) as conn:
        if args.gap:
            if not args.decision:
                ap.error("--decision is required with --gap")
            out = decide(conn, args.gap, args.decision, args.reviewer, args.reason)
            print(", ".join(f"{k}: {v}" for k, v in out.items() if v))
            return
        rows = queue(conn, args.tier)
        print(f"{len(rows)} open gaps in the {args.tier} tier")
        for g in rows:
            why = (g["evidence"] or {}).get("detail") or g["why"]
            print(
                f"\n{g['id']}  RBI {g['ref']} | {g['type']} | {g['residual']} "
                f"({g['priority']:.2f})\n  RBI: {(g['obligation'] or '')[:200]}\n"
                f"  policy: {(g['policy'] or '-')[:200]}\n  why: {why[:200]}"
            )


if __name__ == "__main__":
    main()
