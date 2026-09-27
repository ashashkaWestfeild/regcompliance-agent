"""Build the user's blind labelling sheet from the current dev run in Postgres.

Samples obligations (fixed seed) that the frozen answer key does NOT target, shows each with its
top-5 retrieved policy passages and NO system verdict. The user fills: verdict (covered /
partial / missing), best candidate (1-5, or 'other' + a policy section), notes.

    uv run python scripts/make_label_sheet.py --n 30 --out eval/labels/label_sheet_dev.csv
"""

import argparse
import csv
import json
import random
from pathlib import Path

from regcomp.db import connect

DEV_KEY = "eval/answer_key_nainital.jsonl"
SEED = 20260927


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", default="eval/labels/label_sheet_dev.csv")
    args = ap.parse_args()

    key = [json.loads(x) for x in Path(DEV_KEY).read_text(encoding="utf-8").splitlines()]
    excluded = {ref for row in key for ref in row.get("target_obligation_refs", [])}

    with connect() as conn:
        obligations = conn.execute(
            "SELECT id, source_clause_ref, source_span->>'quote' FROM obligation"
            " WHERE modality IN ('must', 'must_not') ORDER BY key"
        ).fetchall()
        pool = [o for o in obligations if o[1] not in excluded]
        sample = random.Random(SEED).sample(pool, min(args.n, len(pool)))
        rows = []
        for n, (oid, ref, quote) in enumerate(sample, 1):
            cands = conn.execute(
                "SELECT c.control_ref, c.source_span->>'quote' FROM embedding e"
                " JOIN control c ON c.id = e.owner_id WHERE e.owner_kind = 'control'"
                " ORDER BY e.vec <=> (SELECT vec FROM embedding WHERE owner_kind = 'obligation'"
                " AND owner_id = %s) LIMIT 5",
                (oid,),
            ).fetchall()
            row = {"#": n, "rbi_ref": ref, "obligation": quote}
            for i in range(5):
                ref_i, text_i = cands[i] if i < len(cands) else ("", "")
                row[f"cand{i + 1}_policy_ref"] = ref_i
                row[f"cand{i + 1}_text"] = text_i
            row.update(
                {
                    "YOUR_verdict (covered/partial/missing)": "",
                    "YOUR_best_candidate (1-5 or other)": "",
                    "YOUR_other_policy_ref": "",
                    "YOUR_notes": "",
                }
            )
            rows.append(row)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # BOM: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out} (excluded {len(excluded)} key-targeted refs)")


if __name__ == "__main__":
    main()
