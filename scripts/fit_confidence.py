"""Fit the confidence tables on the development bank, from stored outputs (no model call).

    uv run python scripts/fit_confidence.py

Writes eval/reports/confidence_table.json:
  reliability    per band of the judge's own confidence, how often its verdict was right
  combinations   per signal combination (regcomp.confidence), how the findings of that kind did
Ground truth, in this order:
  answer key     a gap that cites a planted passage is real; one that cites a decoy passage, or
                 sits on a real finding scored "no gap", is a false alarm; a gap at a planted
                 obligation citing other text is counted apart (right obligation, other passage)
  gold sheet     the 50 adjudicated pairs (eval/runs/e2e2/adjudication_sheet_gold.csv)
Everything else is "not adjudicated". Fitted on the development bank only and frozen before any
held-out run; the held-out banks are then reported against it, never used to change it.
"""

import argparse
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

from score_gold import _norm, labels

from regcomp.confidence import BANDS, BASES, band, basis, combination, record
from regcomp.db import connect
from regcomp.evaluation import match
from regcomp.policies import policy

GOLD = Path("eval/runs/e2e2")
HIGH_SHEET = Path("eval/runs/confidence")  # scripts/make_high_tier_sheet.py
TABLE = Path("eval/reports/confidence_table.json")
FIT_ON = "nainital"  # the development bank; the gold sheet was drawn from it
_SPAN = "({0}.source_span->>'char_start')::int, ({0}.source_span->>'char_end')::int"


def gold_rows() -> list[dict]:
    """[{span, action, ref, gap}] for the adjudicated sheet, or [] when it is not on this
    machine (the sheet is not in the repository)."""
    sheet, private = GOLD / "adjudication_sheet_gold.csv", GOLD / "adjudication_private.json"
    if not (sheet.exists() and private.exists()):
        return []
    gold = labels(sheet)
    rows = json.loads(private.read_text(encoding="utf-8"))["rows"]
    return [
        {
            "span": tuple(rows[n]["obligation_span"]),
            "action": _norm(rows[n]["obligation_action"]),
            "ref": rows[n]["obligation_ref"],
            "gap": g["gap"],
        }
        for n, g in gold.items()
        if not g["blank"]
    ]


def gold_index(obligations: list[dict], gold: list[dict]) -> dict[str, bool]:
    """{obligation id: adjudicated as a gap} for the gold rows found in the current data. Same
    matching as score_gold.py: exact span and action, else a unique span, else a unique
    (clause, action) when a citation has moved."""
    out = {}
    for g in gold:
        exact = [o for o in obligations if o["span"] == g["span"] and o["action"] == g["action"]]
        same_span = [o for o in obligations if o["span"] == g["span"]]
        moved = [o for o in obligations if o["action"] == g["action"] and o["ref"] == g["ref"]]
        hit = exact[:1] or (same_span if len(same_span) == 1 else moved if len(moved) == 1 else [])
        if hit:
            out[hit[0]["id"]] = g["gap"]
    return out


def content_key(g: dict, spans: dict) -> tuple:
    """A gap's identity by content, stable across database rebuilds."""
    start, end = spans.get(g["obligation"], (None, None))
    c_start, c_end = g["control_span"] or (None, None)
    return (g["ref"], start, end, c_start, c_end)


def sheet_labels() -> dict[tuple, bool]:
    """{content key: labelled as a gap} from the author's high-confidence sheet, if filled in."""
    sheet, private = HIGH_SHEET / "high_tier_sheet.csv", HIGH_SHEET / "high_tier_private.json"
    if not (sheet.exists() and private.exists()):
        return {}
    import csv

    rows = json.loads(private.read_text(encoding="utf-8"))["rows"]
    out = {}
    with sheet.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            # the outcome after the full-policy text check wins over the label from two texts
            after = (r.get("AFTER_full_policy_check") or "").strip().lower()
            label = after or next(v for k, v in r.items() if k.startswith("YOUR_label"))
            label = label.strip().lower()
            if label in ("gap", "no gap") and rows[r["#"]]["system_finding"]:
                out[tuple(rows[r["#"]]["key"])] = label == "gap"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=FIT_ON)
    ap.add_argument("--held-out", action="store_true")
    args = ap.parse_args()
    policy(args.policy, held_out=args.held_out)  # the guard on the held-out banks
    fitting = args.policy == FIT_ON
    key = [
        json.loads(x)
        for x in Path(f"eval/answer_key_{args.policy}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    with connect() as conn:
        mappings = [
            {
                "id": str(r[0]),
                "obligation": str(r[1]),
                "ref": r[2],
                "span": (r[3], r[4]),
                "action": _norm(r[5]),
                "verdict": r[6],
                "confidence": float(r[7]),
                "citation_ok": r[8] == "true",
                "control_span": (r[9], r[10]) if r[9] is not None else None,
                "gap_type": None,
            }
            for r in conn.execute(
                f"SELECT m.id, o.id, o.source_clause_ref, {_SPAN.format('o')}, o.action,"
                f" m.verdict::text, m.confidence, m.judges->0->>'citation_ok', {_SPAN.format('c')}"
                " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
                " LEFT JOIN control c ON c.id = m.control_id WHERE m.superseded_at IS NULL"
            ).fetchall()
        ]
        by_mapping = {m["id"]: m for m in mappings}
        gaps = [
            {
                "id": str(r[0]),
                "obligation": str(r[1]),
                "ref": r[2],
                "gap_type": r[3],
                "tier": r[4],
                "evidence": r[5],
                "has_test": r[6],
                "control_span": (r[7], r[8]) if r[7] is not None else None,
                "mapping": by_mapping.get(str(r[9])),
            }
            for r in conn.execute(
                "SELECT g.id, o.id, o.source_clause_ref, g.type::text, g.tier, g.evidence,"
                f" g.control_test_id IS NOT NULL, {_SPAN.format('c')}, g.mapping_id"
                " FROM gap g JOIN obligation o ON o.id = g.obligation_id"
                " LEFT JOIN mapping m ON m.id = g.mapping_id"
                " LEFT JOIN control c ON c.id = COALESCE(g.control_id, m.control_id)"
                " WHERE g.status = 'open' AND g.superseded_at IS NULL"
                " AND g.tier <> 'not_applicable'"
            ).fetchall()
        ]
    gold = gold_rows() if fitting else []
    gold_gap = gold_index(
        [
            {"id": m["obligation"], "span": m["span"], "action": m["action"], "ref": m["ref"]}
            for m in mappings
        ],
        gold,
    )

    # ---- truth for each gap
    truth: dict[str, str] = {}
    for row in key:
        if row["kind"] == "mutation":
            strict, near = match(row, gaps)
            truth.update({f["id"]: "real_planted" for f in strict})
            for f in near:
                truth.setdefault(f["id"], "other_passage")
        elif row["kind"] == "decoy":
            truth.update({f["id"]: "false_alarm" for f in match(row, gaps)[0]})
        elif row["kind"] == "real_finding" and row.get("scoring") == "no_gap":
            refs = set(row.get("target_obligation_refs", []))
            truth.update({g["id"]: "false_alarm" for g in gaps if g["ref"] in refs})
    # the evidence key: a planted operating failure is real, an evidence decoy is not
    evidence_key = Path(f"eval/answer_key_evidence_{args.policy}.jsonl")
    if evidence_key.exists():
        for line in evidence_key.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            refs = set(row["target_obligation_refs"])
            outcome = "real_planted" if row["kind"] == "evidence" else "false_alarm"
            truth.update(
                {
                    g["id"]: outcome
                    for g in gaps
                    if g["gap_type"] == "operating_failure" and g["ref"] in refs
                }
            )
    by_key = Counter(truth.values())
    for g in gaps:
        if g["id"] not in truth and g["obligation"] in gold_gap:
            truth[g["id"]] = "real" if gold_gap[g["obligation"]] else "false_alarm"

    spans = {m["obligation"]: m["span"] for m in mappings}
    settled = sorted(
        {content_key(g, spans) for g in gaps if g["id"] in truth and g["tier"] == "high"},
        key=str,
    )
    labelled = sheet_labels() if fitting else {}
    from_sheet = 0
    for g in gaps:
        key_ = content_key(g, spans)
        if g["id"] not in truth and key_ in labelled:
            truth[g["id"]] = "real" if labelled[key_] else "false_alarm"
            from_sheet += 1

    combos: dict[str, Counter] = defaultdict(Counter)
    tiers: dict[str, Counter] = defaultdict(Counter)
    for g in gaps:
        m = g["mapping"] or {}
        base = basis(m.get("verdict", "partial"), g["gap_type"], g["evidence"], g["has_test"])
        name = combination(base, m.get("citation_ok", False))
        combos[name]["findings"] += 1
        outcome = truth.get(g["id"], "not_adjudicated")
        combos[name][outcome] += 1
        combos[name]["real"] += outcome == "real_planted"  # planted gaps are real gaps
        tiers[name][g["tier"]] += 1

    # ---- reliability of the judge's own confidence
    judged: dict[str, tuple[bool, str]] = {}  # mapping id -> (a gap is the right answer, source)
    for row in key:
        if row["kind"] not in ("mutation", "decoy"):
            continue
        strict, near = match(row, mappings, gaps_only=False)
        if not near and not any(
            loc["char_end"] > loc["char_start"] for loc in row.get("locations", [])
        ):
            continue  # a deletion-only row names no passage: which obligation is meant is unclear
        for f in strict:
            judged[f["id"]] = (row["kind"] == "mutation", "key")
    for m in mappings:
        if m["id"] not in judged and m["obligation"] in gold_gap:
            judged[m["id"]] = (gold_gap[m["obligation"]], "gold")
    reliability = {name: Counter() for name, _, _ in BANDS}
    for mid, (is_gap, source) in judged.items():
        m = by_mapping[mid]
        right = (m["verdict"] != "covered") == is_gap
        cell = reliability[band(m["confidence"])]
        cell["judged"] += 1
        cell["right"] += right
        cell[f"{source}_judged"] += 1
        cell[f"{source}_right"] += right
        cell["said_gap" if m["verdict"] != "covered" else "said_covered"] += 1
    all_bands = Counter(band(m["confidence"]) for m in mappings)

    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    dev = {} if fitting else json.loads(TABLE.read_text(encoding="utf-8"))["combinations"]
    out = TABLE if fitting else Path(f"eval/reports/confidence_holdout_{args.policy}.json")
    table = {
        "fitted_on" if fitting else "checked_on": args.policy,
        "fitted_at" if fitting else "checked_at": time.strftime("%Y-%m-%d %H:%M"),
        "code_commit": head,
        "ground_truth": {
            "answer_key_rows": sum(r["kind"] in ("mutation", "decoy") for r in key),
            "gold_rows_labelled": len(gold),
            "gold_rows_found_in_current_data": len(gold_gap),
            "gaps_with_truth_from_key": dict(by_key),
            "gaps_with_truth_from_high_tier_sheet": from_sheet,
        },
        "settled": [list(k) for k in settled],
        "reliability": [
            {
                "judge_confidence": name,
                "verdicts_in_band": all_bands[name],
                **{
                    k: reliability[name][k]
                    for k in (
                        "judged",
                        "right",
                        "key_judged",
                        "key_right",
                        "gold_judged",
                        "gold_right",
                        "said_gap",
                        "said_covered",
                    )
                },
            }
            for name, _, _ in BANDS
        ],
        "combinations": {
            name: {
                "label": BASES[name.split("|")[0]],
                "citation": name.split("|")[1],
                "findings": c["findings"],
                "real": c["real"],
                "real_planted": c["real_planted"],
                "false_alarm": c["false_alarm"],
                "other_passage": c["other_passage"],
                "not_adjudicated": c["not_adjudicated"],
                "tiers": dict(tiers[name]),
                "record": record(c),
                **({} if fitting else {"development_record": dev.get(name, {}).get("record")}),
            }
            for name, c in sorted(combos.items(), key=lambda kv: -kv[1]["findings"])
        },
    }
    out.write_text(
        json.dumps(table, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"ground truth: {table['ground_truth']}")
    print(
        "\njudge confidence | verdicts | with truth | right | (key right/judged, gold right/judged)"
    )
    for r in table["reliability"]:
        print(
            f"- {r['judge_confidence']:<13} | {r['verdicts_in_band']:>3} | {r['judged']:>2} | "
            f"{r['right']:>2} | key {r['key_right']}/{r['key_judged']}, gold "
            f"{r['gold_right']}/{r['gold_judged']} | judge said gap {r['said_gap']}, covered "
            f"{r['said_covered']}"
        )
    print(
        "\nsignal combination | findings | real (planted) | false alarm | other passage | "
        "not adjudicated | tiers"
    )
    for name, c in table["combinations"].items():
        print(
            f"- {name:<32} | {c['findings']:>2} | {c['real']} ({c['real_planted']}) | "
            f"{c['false_alarm']} | "
            f"{c['other_passage']} | {c['not_adjudicated']} | {c['tiers']}"
        )
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
