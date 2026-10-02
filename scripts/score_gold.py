"""Score judge candidates on the fixed 50-pair gold set (counts only).

  uv run python scripts/score_gold.py --labels eval/runs/e2e2/adjudication_sheet.csv e2e2 e2e5 e2e7

The sheet was drawn from run e2e2 (25 pairs the system flagged, 25 it did not) and labelled blind.
Each later run is scored on the same 50 obligations: its judge verdict for that obligation, and
whether a gap was raised (verdict not covered, and the obligation classified policy-level when the
run has levels.json).

Obligation ids are random per run, so a run's judgments.json is joined back to obligations.json by
replaying the judge loop's order (unit by unit); a unit whose labels do not line up is reported as
unresolved rather than guessed.
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

RUNS = Path("eval/runs")
SHEET_RUN = "e2e2"


def _norm(text: str) -> str:
    return " ".join(re.findall(r"\w+", (text or "").lower()))


def labels(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    cols = list(rows[0])
    label = next(c for c in cols if c.startswith("YOUR_label"))
    level = next(c for c in cols if c.startswith("YOUR_obligation_level"))
    return {
        r["#"]: {
            "gap": r[label].strip().lower() == "gap",
            "level": r[level].strip().lower(),
            "notes": r["YOUR_notes"],
            "blank": not r[label].strip(),
        }
        for r in rows
    }


def judged(run: str) -> tuple[dict[tuple, dict], list[str]]:
    """{(char_start, char_end, normalised action): judgment + level} for one run, and the units
    that could not be joined."""
    d = RUNS / run
    obligations = json.loads((d / "obligations.json").read_text(encoding="utf-8"))["items"]
    stream = list(json.loads((d / "judgments.json").read_text(encoding="utf-8")).values())
    levels = (
        json.loads((d / "levels.json").read_text(encoding="utf-8"))
        if (d / "levels.json").exists()
        else {}
    )
    units = defaultdict(list)
    for o in obligations:
        units[o["unit_ref"]].append(o)
    out, unresolved, at = {}, [], 0
    for ref, obs in units.items():
        want = {f"O{n}" for n in range(1, len(obs) + 1)}
        seen = {}
        while at + len(seen) < len(stream):
            tag = stream[at + len(seen)]["obligation"]
            if tag not in want or tag in seen:
                break
            seen[tag] = stream[at + len(seen)]
        if set(seen) != want:
            unresolved.append(ref)  # a skipped unit or a partial answer: consume nothing
            continue
        at += len(seen)
        for n, o in enumerate(obs, 1):
            lv = levels.get(f"{o['char_start']}:{o['char_end']}:{o['action']}", {})
            out[(o["char_start"], o["char_end"], _norm(o["action"]))] = dict(
                seen[f"O{n}"], level=lv.get("level"), has_levels=bool(levels)
            )
    if at != len(stream):
        unresolved.append(f"({len(stream) - at} judgments left over)")
    return out, unresolved


def find(index: dict[tuple, dict], row: dict) -> dict | None:
    start, end = row["obligation_span"]
    hit = index.get((start, end, _norm(row["obligation_action"])))
    if hit:
        return hit
    same_span = [v for (s, e, _), v in index.items() if (s, e) == (start, end)]
    return same_span[0] if len(same_span) == 1 else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("runs", nargs="+")
    args = ap.parse_args()

    gold = labels(args.labels)
    private = json.loads((RUNS / SHEET_RUN / "adjudication_private.json").read_text("utf-8"))[
        "rows"
    ]
    blank = sum(g["blank"] for g in gold.values())
    n_gap = sum(g["gap"] for g in gold.values())
    print(f"labels: {args.labels} ({len(gold) - blank}/{len(gold)} filled)")
    print(f"labelled gap {n_gap}, no gap {len(gold) - blank - n_gap}")
    print("level labels:", dict(Counter(g["level"] for g in gold.values())))
    print()
    print(
        "| run | matched | verdict not covered: label gap / flagged "
        "| gaps raised: label gap / raised | labelled gaps raised "
        "| labelled gaps judged covered | unresolved units |"
    )
    print("|---|---|---|---|---|---|---|")
    detail = {}
    for run in args.runs:
        if run == SHEET_RUN:  # the sheet's own run: its verdicts were recorded with the sample
            unresolved = []
            rows = {
                n: {"verdict": private[n]["system_verdict"], "level": None, "has_levels": False}
                for n in gold
            }
        else:
            index, unresolved = judged(run)
            rows = {n: find(index, private[n]) for n in gold}
        hit = {n: r for n, r in rows.items() if r}
        flagged = {n for n, r in hit.items() if r["verdict"] != "covered"}
        raised = {n for n in flagged if not hit[n]["has_levels"] or hit[n]["level"] == "policy"}
        is_gap = {n for n in hit if gold[n]["gap"]}
        print(
            f"| {run} | {len(hit)}/{len(gold)} | {len(flagged & is_gap)}/{len(flagged)} "
            f"| {len(raised & is_gap)}/{len(raised)} | {len(raised & is_gap)}/{len(is_gap)} "
            f"| {len(is_gap - flagged)}/{len(is_gap)} | {len(unresolved)} |"
        )
        detail[run] = (hit, flagged, raised)

    for run in args.runs:
        hit, flagged, raised = detail[run]
        if not any(r["has_levels"] for r in hit.values()):
            continue
        pairs = Counter((gold[n]["level"], r["level"]) for n, r in hit.items())
        agree = sum(c for (a, b), c in pairs.items() if a == b)
        print(f"\nlevel classifier in {run}: agrees with the label on {agree}/{len(hit)}")
        for (a, b), c in sorted(pairs.items()):
            if a != b:
                rows = [n for n, r in hit.items() if (gold[n]["level"], r["level"]) == (a, b)]
                print(f"  label {a} -> system {b}: {c} (rows {', '.join(rows)})")
        lost = [n for n in flagged - raised if gold[n]["gap"]]
        print(f"  labelled gaps dropped by the level filter: {len(lost)} (rows {', '.join(lost)})")

    print("\nper row (label | " + " | ".join(args.runs) + "):")
    for n in gold:
        cells = []
        for run in args.runs:
            hit, flagged, raised = detail[run]
            r = hit.get(n)
            cells.append(
                "-"
                if r is None
                else r["verdict"] + ("" if n in raised or n not in flagged else "*")
            )
        print(
            f"  {n:>2} {private[n]['obligation_ref']:<12} "
            f"{'gap' if gold[n]['gap'] else 'no gap':<6} | " + " | ".join(cells)
        )
    print("  (* = judged not covered, but no gap raised because the level is not policy)")


if __name__ == "__main__":
    main()
