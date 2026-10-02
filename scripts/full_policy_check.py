"""Full-policy text check for sheet rows the author labelled "gap".

    uv run python scripts/full_policy_check.py --sheet <labelled csv>

A row on the sheet shows one policy passage. Before a "gap" label is counted as a real gap, the
whole policy is searched for text that covers the obligation somewhere else: the five policy
sentences closest in wording and the five closest passages by embedding are printed with the
obligation, to be read by a person. Nothing is decided here and nothing is written.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from regcomp.db import connect
from regcomp.pipeline.verify import Comparer, _pairs, body

PRIVATE = Path("eval/runs/confidence/high_tier_private.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=Path, default=Path("eval/runs/confidence/high_tier_sheet.csv"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    private = json.loads(PRIVATE.read_text(encoding="utf-8"))["rows"]
    with args.sheet.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    label = next(c for c in rows[0] if c.startswith("YOUR_label"))
    marked = [r for r in rows if r[label].strip().lower() == "gap"]
    print(f"{len(marked)} of {len(rows)} rows are labelled gap")
    with connect(autocommit=True) as conn:
        policy = conn.execute("SELECT text FROM document WHERE kind = 'policy'").fetchone()[0]
        comparer = Comparer(policy)
        for r in marked:
            ref, start, end, *_ = private[r["#"]]["key"]
            finding = "system finding" if private[r["#"]]["system_finding"] else "covered pair"
            found = conn.execute(
                "SELECT id, source_span->>'quote', action FROM obligation"
                " WHERE source_clause_ref = %s AND (source_span->>'char_start')::int = %s"
                " AND (source_span->>'char_end')::int = %s AND superseded_at IS NULL LIMIT 1",
                (ref, start, end),
            ).fetchone()
            if not found:
                print(f"\n== row {r['#']} RBI {ref}: obligation not found in the current data")
                continue
            oid, quote, action = found
            print(f"\n== row {r['#']} | RBI {ref} | {finding} | notes: {r.get('YOUR_notes', '')}")
            print(f"   obligation: {quote}")
            print(f"   checked as: {action}")
            want = _pairs(body(quote))
            scored = sorted(
                range(len(comparer.windows)),
                key=lambda i: -len(want & comparer.pairs[i]),
            )[:5]
            print("   closest policy sentences by wording:")
            for i in scored:
                a, b = comparer.windows[i]
                share = len(want & comparer.pairs[i]) / max(1, len(want))
                print(f"     [{share:.2f}] {' '.join(policy[a:b].split())[:330]}")
            print("   closest policy passages by embedding:")
            for cref, text in conn.execute(
                "SELECT c.control_ref, c.source_span->>'quote' FROM embedding eo"
                " JOIN embedding ec ON ec.owner_kind = 'control' AND ec.model = eo.model"
                " JOIN control c ON c.id = ec.owner_id"
                " WHERE eo.owner_kind = 'obligation' AND eo.owner_id = %s"
                " ORDER BY ec.vec <=> eo.vec LIMIT 5",
                (oid,),
            ).fetchall():
                print(f"     [{cref}] {' '.join((text or '').split())[:330]}")


if __name__ == "__main__":
    main()
