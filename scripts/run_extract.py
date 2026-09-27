"""Stage 1 of the crude end-to-end run: extract obligations (regulation) and controls (policy).

Dev set only (Nainital). Every model call is cached in Postgres, so re-running is cheap and
resumes where it stopped. Outputs go to eval/runs/<run>/ (git-ignored).

    uv run python scripts/run_extract.py --run e2e1
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
from regcomp.pipeline.units import units

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"
DEV_POLICY = "data/mutated/nainital.items.json"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    out = Path("eval/runs") / args.run
    out.mkdir(parents=True, exist_ok=True)

    reg = parse_file(REGULATION)
    pol = parse_policy_items(json.loads(Path(DEV_POLICY).read_text(encoding="utf-8")))
    with connect(autocommit=True) as conn:
        obligations = extract_obligations(units(reg), conn, progress("obligations"))
        (out / "obligations.json").write_text(
            json.dumps(asdict(obligations), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        controls = extract_controls(units(pol), conn, progress("controls"))
        (out / "controls.json").write_text(
            json.dumps(asdict(controls), ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(
        f"done: {len(obligations.items)} obligations ({len(obligations.rejected)} rejected, "
        f"{obligations.duplicates} duplicates collapsed), "
        f"{len(controls.items)} controls ({len(controls.rejected)} rejected), "
        f"flags {len(obligations.flags) + len(controls.flags)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
