"""Ongoing monitoring: test a new batch of operating evidence and update the gaps.

The batch is described like an entry of data/evidence/<policy>/manifest.yaml. Without --file the
synthetic demo batch is generated first (seeded; identifiers only): the October CKYCR upload log,
in which uploads are back within the 10-day deadline after the September log failed.

    uv run python scripts/run_evidence.py                       # demo batch (CKYCR, recovered)
    uv run python scripts/run_evidence.py --late-rate 0.15      # demo batch that still fails
    uv run python scripts/run_evidence.py --file my_log.csv --obligation-ref "65(2)" \\
        --rule ckycr_late --deadline-days 10
"""

import argparse
from datetime import date
from pathlib import Path

from regcomp.db import connect
from regcomp.evidence import generate_ckycr, write_csv
from regcomp.monitor import assess_batch

DEMO = Path("data/evidence/nainital/batches/ckycr_upload_log_2026-10.csv")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path)
    ap.add_argument("--obligation-ref", default="65(2)")
    ap.add_argument("--rule", default="ckycr_late", choices=["ckycr_late", "rekyc_overdue"])
    ap.add_argument("--deadline-days", type=int, default=10)
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--tolerance", type=float, default=0.05)
    ap.add_argument("--late-rate", type=float, default=0.02, help="demo batch only")
    args = ap.parse_args()
    path = args.file
    if path is None:
        path = DEMO
        write_csv(generate_ckycr(600, args.late_rate, seed=303, start=date(2026, 10, 1)), path)
        print(f"synthetic batch written: {path} ({args.late_rate:.0%} late by construction)")
    entry = {
        "file": path.name,
        "obligation_ref": args.obligation_ref,
        "rule": args.rule,
        "deadline_days": args.deadline_days,
        "as_of": args.as_of,
        "tolerance": args.tolerance,
    }
    with connect(autocommit=True) as conn:
        out = assess_batch(conn, entry, path)
    meaning = {
        "newly_failing": "an operating_failure gap was opened",
        "still_failing": "the open gap stays, with the new figures",
        "recovered": "the gap moved to the review queue; a reviewer closes it",
        "healthy": "nothing to do",
        "cannot_assess": "no control is mapped to that obligation",
    }[out["change"]]
    print(f"{out['file']} -> RBI {out['obligation_ref']}: {out['result']} ({out['rationale']})")
    print(f"change: {out['change']}: {meaning}")


if __name__ == "__main__":
    main()
