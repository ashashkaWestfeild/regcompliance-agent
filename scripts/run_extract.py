"""Stage 1 of the crude end-to-end run: extract obligations (regulation) and controls (policy).

Every model call is cached in Postgres, so re-running is cheap and resumes where it stopped.
Outputs go to eval/runs/<run>/ (git-ignored).

    uv run python scripts/run_extract.py --run e2e1
    uv run python scripts/run_extract.py --run e2e1 --guard-only   # only redo the code-level scan

The bank's document is also scanned in code for text that tries to instruct an automated reader
(regcomp.pipeline.guard); those flags join the ones the extraction model raised.
"""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from regcomp.db import connect
from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.ingest.rbi_html import parse_file
from regcomp.pipeline.extract import extract_controls, extract_obligations
from regcomp.pipeline.guard import scan
from regcomp.pipeline.units import units
from regcomp.policies import policy

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"


def progress(label: str):
    started = time.time()

    def report(done: int, total: int, ref: str) -> None:
        rate = (time.time() - started) / done
        eta = rate * (total - done) / 60
        print(
            f"[{time.strftime('%H:%M:%S')}] {label} {done}/{total} ({ref}) "
            f"{rate:.1f}s/unit, eta {eta:.0f} min",
            flush=True,
        )

    return report


def with_scan(flags: list[dict], text: str) -> tuple[list[dict], int]:
    """The model's flags plus the code-level scan's, without repeating a sentence the model
    already flagged. Returns (all flags, number added by the scan)."""
    model = [f for f in flags if f.get("by") != "rule"]
    spans = [(f["char_start"], f["char_start"] + len(f["text"])) for f in model]
    added = [
        f
        for f in scan(text)
        if not any(a < f["char_start"] + len(f["text"]) and f["char_start"] < b for a, b in spans)
    ]
    return model + added, len(added)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default="nainital")
    ap.add_argument("--held-out", action="store_true", help="confirm a held-out (test) policy")
    ap.add_argument("--guard-only", action="store_true", help="redo the code-level scan only")
    args = ap.parse_args()
    bank = policy(args.policy, args.held_out)
    out = Path("eval/runs") / args.run
    out.mkdir(parents=True, exist_ok=True)

    pol = parse_policy_items(json.loads(bank.items.read_text(encoding="utf-8")))
    if args.guard_only:
        controls = json.loads((out / "controls.json").read_text(encoding="utf-8"))
        controls["flags"], added = with_scan(controls["flags"], pol.text)
        (out / "controls.json").write_text(
            json.dumps(controls, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"code-level scan: {added} sentence(s) flagged; flags now {len(controls['flags'])}")
        return 0

    reg = parse_file(REGULATION)
    with connect(autocommit=True) as conn:
        obligations = extract_obligations(units(reg), conn, progress("obligations"))
        (out / "obligations.json").write_text(
            json.dumps(asdict(obligations), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        controls = extract_controls(units(pol), conn, progress("controls"))
        controls.flags, added = with_scan(controls.flags, pol.text)
        (out / "controls.json").write_text(
            json.dumps(asdict(controls), ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(
        f"done: {len(obligations.items)} obligations ({len(obligations.rejected)} rejected, "
        f"{obligations.duplicates} duplicates collapsed), "
        f"{len(controls.items)} controls ({len(controls.rejected)} rejected), "
        f"flags {len(obligations.flags) + len(controls.flags)} "
        f"({added} from the code-level scan)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
