"""Full-policy text check for held-out precision sheet rows labelled "gap" (no database needed).

    uv run python scripts/heldout_full_policy_check.py --policy centralbank --sheet <labelled csv>

A sheet row shows one policy passage. Before a "gap" label counts, the whole policy is searched
for text that covers the obligation elsewhere: the five closest sentences by wording and the
five closest by bge-m3 embedding, printed with the obligation for a person to read. Nothing is
decided here and nothing is written. The policy text is the planted copy the frozen run read.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.llm import embed
from regcomp.pipeline.verify import Comparer, _pairs, body
from regcomp.policies import policy

RUNS = Path("eval/runs/heldout_precision")


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--sheet", type=Path, required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pol = policy(args.policy, held_out=True)
    private = json.loads((RUNS / f"{args.policy}_private.json").read_text("utf-8"))["rows"]
    snap = json.loads((RUNS / f"{args.policy}_snapshot.json").read_text("utf-8"))
    by_key = {}
    for f in snap["population"] + snap["covered"]:
        cs = f["control_span"] or (-1, -1)
        by_key[(f["ref"], *f["obligation_span"], *cs)] = f
    with args.sheet.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    label = next(c for c in rows[0] if c.startswith("YOUR_label"))
    marked = [r for r in rows if r[label].strip().lower() == "gap"]

    text = parse_policy_items(json.loads(pol.items.read_text(encoding="utf-8"))).text
    comparer = Comparer(text)
    sentences = [(a, b) for a, b in comparer.windows if b - a < 900][: len(comparer.windows)]
    vectors = embed([" ".join(text[a:b].split()) for a, b in sentences])
    print(
        f"{args.policy}: {len(marked)} of {len(rows)} rows labelled gap; "
        f"{len(sentences)} policy windows"
    )
    for r in marked:
        p = private[r["#"]]
        f = by_key.get(tuple(p["key"]))
        kind = "system finding" if p["system_finding"] else "covered pair"
        print(f"\n== row {r['#']} | RBI {r['rbi_ref']} | {kind} | notes: {r.get('YOUR_notes', '')}")
        quote = f["quote"] if f else r["regulation_text"]
        print(f"   obligation: {' '.join(quote.split())}")
        print(f"   checked as: {r['obligation_being_checked (as extracted)']}")
        want = _pairs(body(quote))
        top = sorted(range(len(comparer.windows)), key=lambda i: -len(want & comparer.pairs[i]))[:5]
        print("   closest policy text by wording:")
        for i in top:
            a, b = comparer.windows[i]
            share = len(want & comparer.pairs[i]) / max(1, len(want))
            print(f"     [{share:.2f}] {' '.join(text[a:b].split())[:330]}")
        q = embed([" ".join(quote.split())])[0]
        best = sorted(range(len(sentences)), key=lambda i: -cosine(q, vectors[i]))[:5]
        print("   closest policy text by embedding:")
        for i in best:
            a, b = sentences[i]
            print(f"     [{cosine(q, vectors[i]):.2f}] {' '.join(text[a:b].split())[:330]}")


if __name__ == "__main__":
    main()
