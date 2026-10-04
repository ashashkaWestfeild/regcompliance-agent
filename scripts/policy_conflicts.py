"""Block C1 (development analysis): conflicting numbers or periods inside one policy.

    uv run python scripts/policy_conflicts.py      # reads obligations from DATABASE_URL (read-only)

Runs regcomp.conflicts over the development policies only (Nainital keys 1 and 2, and Central
Bank and Dhanlaxmi, development banks since the frozen v1 runs), never the third bank. Scores the
planted contradictions of their answer keys by position, and lists every other conflict for a
person to read. Development data: the rules were written while looking at these same keys, so no
number here is a held-out result. Nothing is written to a database, and the app does not use it.
Output: eval/reports/policy_conflicts_dev.md and .json.
"""

import json
from pathlib import Path

from regcomp.conflicts import conflicts, rbi_sentences, sentences
from regcomp.db import connect
from regcomp.ingest.pdf_docling import parse_policy_items

POLICIES = ["nainital", "nainital2", "centralbank", "dhanlaxmi"]
OUT = Path("eval/reports/policy_conflicts_dev")
NUMERIC = {"N06", "C06", "L04"}  # planted contradictions that state a different number or period


def key_rows(policy: str) -> list[dict]:
    path = Path(f"eval/answer_key_{policy}.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [r for r in rows if r.get("operator") == "contradict"]


def days(v: float) -> str:
    for unit, n in (("years", 365), ("months", 30), ("weeks", 7)):
        if v >= n and v % n == 0:
            return f"{v / n:g} {unit}"
    return f"{v:g} days"


def main() -> None:
    with connect() as conn:
        obligations = conn.execute(
            "SELECT source_clause_ref, source_span->>'quote' FROM obligation"
            " WHERE superseded_at IS NULL ORDER BY source_clause_ref"
        ).fetchall()
    report = {"what": "Conflicting numbers or periods inside one policy. Development data.",
              "policies": {}}  # fmt: skip
    for policy in POLICIES:
        items = json.loads(Path(f"data/mutated/{policy}.items.json").read_text(encoding="utf-8"))
        text = parse_policy_items(items).text
        spans = sentences(text)
        found, seen = [], set()
        for ref, quote in obligations:
            for rbi in rbi_sentences(quote or ""):
                for c in conflicts(rbi, text, spans):
                    sig = (c["dimension"], c["grade"], tuple(sorted(
                        (s, e) for v in c["values"].values() for s, e, _ in v)))  # fmt: skip
                    if sig in seen:
                        continue
                    seen.add(sig)
                    found.append({"ref": ref, "rbi_sentence": rbi, **c})
        planted = []
        for k in key_rows(policy):
            locs = [(loc["char_start"], loc["char_end"]) for loc in k["locations"]]
            hit = [
                f for f in found
                if f["ref"] in k["target_obligation_refs"]
                and any(s < b and e > a for v in f["values"].values() for s, e, _ in v
                        for a, b in locs)
            ]  # fmt: skip
            planted.append({"id": k["mutation_id"], "numeric": k["mutation_id"] in NUMERIC,
                            "target": k["target_obligation_refs"], "found": bool(hit)})  # fmt: skip
        on_key = {
            id(f) for f in found for k in key_rows(policy)
            for loc in k["locations"]
            for v in f["values"].values() for s, e, _ in v
            if s < loc["char_end"] and e > loc["char_start"]
        }  # fmt: skip
        report["policies"][policy] = {
            "planted": planted,
            "flags": [
                {"ref": f["ref"], "dimension": f["dimension"], "grade": f["grade"],
                 "entity": f["entity"],
                 "rbi_values": f["rbi"], "on_planted_passage": id(f) in on_key,
                 "rbi_sentence": f["rbi_sentence"],
                 "passages": {str(v): [{"start": s, "end": e, "quantity": q,
                                        "text": text[s:e].strip()} for s, e, q in ps]
                              for v, ps in f["values"].items()}}
                for f in found
            ],
        }  # fmt: skip
    OUT.with_suffix(".json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    OUT.with_suffix(".md").write_text(markdown(report), encoding="utf-8", newline="\n")
    for policy, r in report["policies"].items():
        hits = ", ".join(f"{p['id']} {'found' if p['found'] else 'missed'}" for p in r["planted"])
        print(f"{policy}: {len(r['flags'])} conflicts flagged; planted: {hits}")


def markdown(report: dict) -> str:
    lines = [
        "# Conflicting numbers or periods inside one policy (block C1)",
        "",
        "**Development data.** Measured on the development keys only (Nainital keys 1 and 2,",
        "Central Bank and Dhanlaxmi); the rules were written while looking at these keys, so",
        "nothing here is a held-out result. Feature 14 (contradiction detection) stays not",
        "claimed: this covers conflicts inside one policy; conflicts between regulations are on",
        "the roadmap.",
        "Code only (`src/regcomp/conflicts.py`), no model; not in the app or the gap table.",
        "Generated by `scripts/policy_conflicts.py`.",
        "",
        "| Policy | Conflicts flagged | On a planted passage | Planted contradictions |",
        "|---|---|---|---|",
    ]
    for policy, r in report["policies"].items():
        planted = "; ".join(
            f"{p['id']} ({', '.join(p['target'])}): "
            + ("found" if p["found"] else "missed")
            + ("" if p["numeric"] else ", wording only, out of scope")
            for p in r["planted"]
        )
        on = sum(f["on_planted_passage"] for f in r["flags"])
        lines.append(f"| {policy} | {len(r['flags'])} | {on} | {planted} |")
    lines += [
        "",
        "## How it was built (read before using the numbers)",
        "",
        "- First run: 2 of 3 numeric planted contradictions found (N06, L04), 7 conflicts flagged,",
        "  4 of them false: beneficial-owner thresholds that differ by customer type on purpose",
        "  (company, partnership, association) and re-KYC periods that differ by risk grade",
        "  (the grade stood before the number). C06 was missed because 'updation of KYC' and",
        "  'KYC updation' counted as different word pairs.",
        "- Three fixes, made after seeing those results on these same keys: group by the",
        "  customer type the sentence names; take the risk grade from earlier in the same",
        "  sentence when none follows the number; compare word pairs in either order.",
        "- Second run: the table above. The figures are therefore a best case on development",
        "  data, not an estimate for an unseen policy.",
        "",
        "## Not covered",
        "",
        "- Conflicts in wording without a number (planted S04: one passage exempts low-risk",
        "  customers from ongoing due diligence, another requires it for all).",
        "- Numbers stated as amounts of money, and periods written in ways the patterns do not",
        "  read; list items whose lead-in is more than one sentence away.",
        "- Conflicts between regulations (feature 13/14 territory): on the roadmap.",
        "",
        "## Every conflict flagged",
        "",
    ]
    for policy, r in report["policies"].items():
        lines += [f"### {policy}", ""]
        if not r["flags"]:
            lines += ["None.", ""]
        for f in r["flags"]:
            unit = days if f["dimension"] == "days" else (lambda v: f"{v:g}%")
            grade = f" ({f['grade']} risk)" if f["grade"] else ""
            grade += f" ({f['entity']})" if f["entity"] else ""
            rbi = ", ".join(unit(v) for v in f["rbi_values"]) or "not stated for this grade"
            tag = " **[planted]**" if f["on_planted_passage"] else ""
            lines.append(f"- RBI {f['ref']}{grade}: RBI says {rbi}{tag}")
            for ps in f["passages"].values():
                for p in ps:
                    lines.append(f'  - {p["quantity"]} at {p["start"]}: "{p["text"][:220]}"')
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
