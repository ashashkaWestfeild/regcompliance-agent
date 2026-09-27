"""Plant known gaps into a public bank policy and write the answer key.

Mutations are hand-written in data/mutations/<policy>.yaml as exact find/replace edits on the
policy's Docling items; this script only applies them. No LLM is involved, so the answer key is
independent of the models it will grade (ADR 0005).

    uv run python scripts/mutate.py nainital            # check + write outputs
    uv run python scripts/mutate.py nainital --check    # validate only

Outputs:
    data/mutated/<policy>.items.json   mutated Docling items (input to the pipeline)
    eval/answer_key_<policy>.jsonl     one row per mutation, decoy, injection and real finding

Real findings (data/mutations/real_findings.yaml) are passages of the real policy labelled by
the user; they are copied into the key so the system is scored fairly on them.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

from regcomp.change.diff import own_text
from regcomp.ingest.normalize import canonical
from regcomp.ingest.pdf_docling import docling_items, parse_policy_items
from regcomp.ingest.rbi_html import parse_file as parse_regulation

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"
REGULATION_VERSION = "KYCDIR-2025-upd-20260918"
REAL_FINDINGS = "data/mutations/real_findings.yaml"

EXPECTED = {  # operator -> (expected mapping verdict, expected gap type)
    "delete_control": ("missing", "missing_control"),
    "weaken_threshold": ("partial", "weak_threshold"),
    "narrow_scope": ("partial", "narrow_scope"),
    "contradict": ("partial", "internal_contradiction"),
    "make_stale": ("partial", "stale_control"),
    "strip_design": ("covered", "design_deficiency"),
    "decoy": ("covered", None),
    "injection": (None, None),  # must be flagged by the input guardrail, change no verdict
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def apply(items: list[dict], spec: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Apply every edit; each `find` must occur exactly once across all items.

    Returns the mutated items and one record per edit: the item it landed in and the offset
    and length of the new text inside that item (length 0 for a deletion). Offsets are kept
    correct when several edits hit the same item.
    """
    items = [dict(it, text=canonical(it["text"])) for it in items]
    records: list[dict] = []
    errors = []
    for m in spec:
        for k, edit in enumerate(m["edits"]):
            find, replace = canonical(edit["find"]), canonical(edit.get("replace") or "")
            total = sum(it["text"].count(find) for it in items)
            if total != 1:
                errors.append(f"{m['id']}: find occurs {total}x (must be 1): {find[:70]!r}")
                continue
            i = next(i for i, it in enumerate(items) if find in it["text"])
            text = items[i]["text"]
            at = text.index(find)
            before, after = text[:at], text[at + len(find) :]
            if replace:  # keep the original separators around the edit
                new_text, offset = before + replace + after, len(before)
            else:  # deletion: collapse the surrounding whitespace to a single space
                before, after = before.rstrip(), after.lstrip()
                sep = " " if before and after else ""
                new_text, offset = before + sep + after, len(before) + len(sep)
            delta = len(new_text) - len(text)
            for r in records:  # shift earlier edits that sit after this one in the same item
                if r["item"] == i and r["offset"] > at:
                    r["offset"] += delta
            items[i]["text"] = new_text
            records.append(
                {
                    "id": m["id"],
                    "edit": k,
                    "item": i,
                    "offset": offset,
                    "length": len(replace),
                    "deleted_text": find if not replace else None,
                }
            )
    return items, records, errors


def locate(positions: dict[int, int], items: list[dict], record: dict) -> int:
    """Character position of an edit; an item emptied by a deletion maps to the next kept item."""
    i = record["item"]
    if i in positions:
        return positions[i] + record["offset"]
    nxt = min((j for j in positions if j > i), default=None)
    if nxt is None:
        raise ValueError(f"{record['id']}: cannot locate edit in parsed document")
    return positions[nxt]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("policy")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    sources = yaml.safe_load(Path("data/sources.yaml").read_text(encoding="utf-8"))
    src = next(p for p in sources["policies"] if p["id"] == args.policy)
    spec = yaml.safe_load(Path(f"data/mutations/{args.policy}.yaml").read_text(encoding="utf-8"))

    regulation = parse_regulation(REGULATION)
    reg_text = {c.ref: own_text(c, regulation) for c in regulation.clauses}
    real = [
        f
        for f in yaml.safe_load(Path(REAL_FINDINGS).read_text(encoding="utf-8"))
        if args.policy in f["policies"]
    ]
    errors = [
        f"{m['id']}: unknown regulation ref {ref!r}"
        for m in spec + real
        for ref in m.get("target_obligation_refs", [])
        if ref not in reg_text
    ]
    errors += [
        f"{m['id']}: unknown operator {m['operator']!r}"
        for m in spec
        if m["operator"] not in EXPECTED
    ]
    ids = [m["id"] for m in spec]
    errors += [f"duplicate id {i}" for i in {i for i in ids if ids.count(i) > 1}]

    original = docling_items(src["file"])
    mutated, records, apply_errors = apply(original, spec)
    errors += apply_errors
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    doc = parse_policy_items(mutated)
    positions = doc.source_positions
    rows = []
    for m in spec:
        verdict, gap_type = EXPECTED[m["operator"]]
        gap_types = m.get("expected_gap_types") or ([gap_type] if gap_type else [])
        locations = []
        for r in (r for r in records if r["id"] == m["id"]):
            start = locate(positions, mutated, r)
            end = start + r["length"]
            if r["length"]:
                replaced = canonical(m["edits"][r["edit"]].get("replace") or "")
                assert doc.text[start:end] == replaced, (m["id"], doc.text[start : start + 60])
            clause = max(
                (c for c in doc.clauses if c.char_start <= start < c.char_end),
                key=lambda c: c.depth,
                default=None,
            )
            locations.append(
                {
                    "char_start": start,
                    "char_end": end,
                    "policy_clause_ref": clause and clause.ref,
                    "deleted_text": r["deleted_text"],
                }
            )
        rows.append(
            {
                "mutation_id": m["id"],
                "kind": "decoy"
                if m["operator"] == "decoy"
                else "injection"
                if m["operator"] == "injection"
                else "mutation",
                "policy": args.policy,
                "policy_source_sha256": src["sha256"],
                "mutated_text_sha256": sha256_text(doc.text),
                "operator": m["operator"],
                "theme": m["theme"],
                "target_obligation_refs": m.get("target_obligation_refs", []),
                "target_obligation_text": {
                    ref: reg_text[ref] for ref in m.get("target_obligation_refs", [])
                },
                "regulation_version": REGULATION_VERSION,
                "expected_verdict": verdict,
                "acceptable_gap_types": gap_types,
                "informational_ok": m.get("informational_ok", []),
                "locations": locations,
                "note": m.get("note", ""),
            }
        )
    for f in real:
        rows.append(
            {
                "mutation_id": f["id"],
                "kind": "real_finding",
                "policy": args.policy,
                "policy_source_sha256": src["sha256"],
                "mutated_text_sha256": sha256_text(doc.text),
                "theme": f["theme"],
                "target_obligation_refs": f.get("target_obligation_refs", []),
                "target_obligation_text": {
                    ref: reg_text[ref] for ref in f.get("target_obligation_refs", [])
                },
                "regulation_version": REGULATION_VERSION,
                "scoring": f["scoring"],
                "acceptable_verdicts": f.get("acceptable_verdicts", []),
                "expected_advisory": f.get("expected_advisory"),
                "note": f.get("note", ""),
            }
        )

    kinds = {
        k: sum(r["kind"] == k for r in rows)
        for k in ("mutation", "decoy", "injection", "real_finding")
    }
    print(
        f"{args.policy}: OK, {kinds}; mutated text {len(doc.text)} chars, "
        f"{len(doc.clauses)} clauses"
    )
    if args.check:
        return 0

    out_items = Path(f"data/mutated/{args.policy}.items.json")
    out_items.parent.mkdir(parents=True, exist_ok=True)
    out_items.write_text(
        json.dumps(mutated, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n"
    )
    out_key = Path(f"eval/answer_key_{args.policy}.jsonl")
    out_key.parent.mkdir(parents=True, exist_ok=True)
    out_key.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out_items} and {out_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
