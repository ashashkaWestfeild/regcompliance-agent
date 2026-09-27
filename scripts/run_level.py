"""Classify every extracted obligation of a run as policy / sop_system / not_applicable.

Reads eval/runs/<run>/obligations.json and writes eval/runs/<run>/levels.json, keyed by the
obligation's stable identity (source span + action), which run_map.py applies when loading.
Every call is cached, so re-runs are free.

    uv run python scripts/run_level.py --run e2e5
"""

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from regcomp.db import connect
from regcomp.pipeline.level import classify_unit


def level_key(o: dict) -> str:
    return f"{o['char_start']}:{o['char_end']}:{o['action']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = Path("eval/runs") / args.run
    items = json.loads((run / "obligations.json").read_text(encoding="utf-8"))["items"]
    by_unit = defaultdict(list)
    for o in items:
        by_unit[o["unit_ref"]].append({**o, "id": level_key(o)})
    levels, started = {}, time.time()
    with connect(autocommit=True) as conn:
        for i, obs in enumerate(by_unit.values(), 1):
            levels.update(classify_unit(obs, conn))
            if i % 20 == 0 or i == len(by_unit):
                print(
                    f"[{time.strftime('%H:%M:%S')}] classified {i}/{len(by_unit)} units", flush=True
                )
    (run / "levels.json").write_text(json.dumps(levels, indent=1, ensure_ascii=False), "utf-8")
    counts = Counter(v["level"] for v in levels.values())
    missing = sum(not v["classified"] for v in levels.values())
    print(
        f"levels: {dict(counts)}; unclassified (defaulted to policy) {missing}; "
        f"{time.time() - started:.0f}s"
    )


if __name__ == "__main__":
    main()
