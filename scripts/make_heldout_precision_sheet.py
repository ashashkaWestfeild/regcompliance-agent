"""Blind sheet for the precision of the high-confidence tier on one held-out bank.

    uv run python scripts/make_heldout_precision_sheet.py --policy centralbank \
        --runs ../regcompliance-freeze/eval/runs

Run while that bank's frozen run is loaded in the database (reconstructed from the model-call
cache with the code of tag eval-freeze-2026-10-03). The script first checks that the findings
in the database score exactly as the frozen scorecard says; if not, it stops. Sampling follows
eval/heldout_precision_sample.json, committed before any sampling.

Writes to eval/runs/heldout_precision/:
  <policy>_sheet.csv      the rows to label: regulation text, obligation, policy text; blind
  <policy>_private.json   which rows are findings, with type and tier (do not open before
                          labelling)
  <policy>_snapshot.json  the whole population and every covered pair, for the later check
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

from score import closest_passage, findings_from_db

from regcomp.db import connect
from regcomp.evaluation import score, summary
from regcomp.policies import policy

PLAN = Path("eval/heldout_precision_sample.json")
OUT = Path("eval/runs/heldout_precision")


def content(f: dict) -> tuple:
    return (f["ref"], *f["obligation_span"], *(f["control_span"] or (-1, -1)))


def distinct(rows: list[dict]) -> list[dict]:
    """One row per (obligation sentence, policy passage), sorted by content."""
    seen, out = set(), []
    for f in sorted(rows, key=lambda f: (content(f), f["action"] or "")):
        if content(f) not in seen:
            seen.add(content(f))
            out.append(f)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--runs", type=Path, required=True, help="folder holding the frozen runs")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    pol = policy(args.policy, held_out=True)
    run = args.runs / f"ho_{args.policy}"
    key = [json.loads(x) for x in pol.key.read_text(encoding="utf-8").splitlines()]
    frozen = json.loads(Path(f"eval/reports/scorecard_{args.policy}.json").read_text("utf-8"))

    flags = []
    for name in ("controls.json", "obligations.json"):
        flags += json.loads((run / name).read_text(encoding="utf-8"))["flags"]
    with connect() as conn:
        findings, policy_sha = findings_from_db(conn)
        if policy_sha != key[0]["mutated_text_sha256"]:
            raise SystemExit(f"the database holds another policy, not {args.policy}")
        s = score(key, findings, flags)
        if summary(s) != frozen["summary"]:
            raise SystemExit("reconstructed findings do not score as the frozen scorecard; stop")
        population = distinct([f for f in s.unkeyed if f["tier"] == "high"])
        gapped = {f["obligation_id"] for f in findings if f["gap_type"]}
        covered = distinct(
            [
                f
                for f in findings
                if f["verdict"] == "covered"
                and f["obligation_id"] not in gapped
                and f["control_quote"]
            ]
        )
        for f in population:
            if not f["control_quote"]:
                f["control_ref"], f["control_quote"] = closest_passage(conn, f["obligation_id"])
                f["shown"] = "closest passage by embedding"

    rng = random.Random(plan["seed"])
    n = min(plan["per_bank"], len(population))
    picked = rng.sample(population, n)
    fillers = rng.sample(covered, min(n, len(covered)))
    rows = [(f, True) for f in picked] + [(f, False) for f in fillers]
    rng.shuffle(rows)

    OUT.mkdir(parents=True, exist_ok=True)
    private = {"policy": args.policy, "seed": plan["seed"], "rows": {}}
    with (OUT / f"{args.policy}_sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "#",
                "bank",
                "rbi_ref",
                "regulation_text",
                "obligation_being_checked (as extracted)",
                "policy_text (the passage the system compared it with)",
                "YOUR_label (gap / no gap)",
                "YOUR_notes",
            ]
        )
        for i, (f, is_finding) in enumerate(rows, 1):
            duty = (f["action"] or "") + (f" ({f['threshold']})" if f["threshold"] else "")
            w.writerow([i, pol.bank, f["ref"], f["quote"], duty, f["control_quote"] or "", "", ""])
            private["rows"][str(i)] = {
                "system_finding": is_finding,
                "gap_type": f["gap_type"],
                "tier": f["tier"] if is_finding else None,
                "key": list(content(f)),
                "obligation_id": f["obligation_id"],
                "policy_text_shown": f.get("shown", "the passage the system compared"),
            }
    (OUT / f"{args.policy}_private.json").write_text(
        json.dumps(private, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    keep = ("ref", "obligation_span", "control_span", "quote", "control_quote", "action",
            "gap_type", "tier", "obligation_id")  # fmt: skip
    (OUT / f"{args.policy}_snapshot.json").write_text(
        json.dumps(
            {
                "population": [{k: f.get(k) for k in keep} for f in population],
                "covered": [{k: f.get(k) for k in keep} for f in covered],
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    raw = sum(f["tier"] == "high" for f in s.unkeyed)
    print(
        f"{args.policy}: scorecard reproduced; high-confidence unkeyed findings {raw} "
        f"({len(population)} distinct sentence-passage pairs); sampled {n}; covered pairs "
        f"available {len(covered)}, sampled {len(fillers)}; sheet: "
        f"{OUT / (args.policy + '_sheet.csv')}"
    )


if __name__ == "__main__":
    main()
