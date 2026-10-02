"""Tidy the stored remediation drafts without calling a model.

    uv run python scripts/clean_remediation.py            # report what would change
    uv run python scripts/clean_remediation.py --apply    # do it

- One remedy per regulation paragraph: when several drafts sit on gaps of the same paragraph,
  the best one is kept (regcomp.remediation.one_per_paragraph) and the others are removed. The
  app shows the kept remedy on every gap of that paragraph.
- Internal item tags ("the obligation in O2") are removed from the text.
No verdict, gap, tier or score is touched.
"""

import argparse
import sys

from regcomp.db import connect
from regcomp.remediation import one_per_paragraph, scrub


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with connect() as conn:
        rows = conn.execute(
            "SELECT r.id::text, o.source_clause_ref, g.priority_score, r.drafted_by_model,"
            " r.action, r.success_criterion FROM remediation r JOIN gap g ON g.id = r.gap_id"
            " JOIN obligation o ON o.id = g.obligation_id"
        ).fetchall()
        drafts = [
            dict(
                zip(
                    ("id", "ref", "priority", "drafted_by", "action", "success_criterion"),
                    r,
                    strict=True,
                )
            )
            for r in rows
        ]
        kept, dropped = one_per_paragraph(drafts)
        scrubbed = 0
        for d in kept:
            action, criterion = scrub(d["action"]), scrub(d["success_criterion"])
            if (action, criterion) != (d["action"], d["success_criterion"]):
                scrubbed += 1
                if args.apply:
                    conn.execute(
                        "UPDATE remediation SET action = %s, success_criterion = %s WHERE id = %s",
                        (action, criterion, d["id"]),
                    )
        for d in dropped:
            print(f"- duplicate on RBI {d['ref']} removed: {d['action'][:90]}...")
            if args.apply:
                conn.execute("DELETE FROM remediation WHERE id = %s", (d["id"],))
        if args.apply:
            conn.commit()
    passed = sum("verbatim obligation" not in d["drafted_by"] for d in kept)
    print(
        f"{len(drafts)} drafts -> {len(kept)} remedies, one per paragraph "
        f"({len(dropped)} duplicates, {scrubbed} with internal tags cleaned)"
    )
    print(f"fidelity check: {passed} of {len(kept)} kept remedies use the model's own wording")
    print("applied" if args.apply else "report only; pass --apply to change the database")


if __name__ == "__main__":
    main()
