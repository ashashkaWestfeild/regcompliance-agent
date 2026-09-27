"""Scoring against the frozen answer keys (docs/mutation_taxonomy.md "Scoring").

Pure functions: key rows + system findings in, counts out. Reporting is counts per row type,
never bare percentages (user rule).

Finding = one judged obligation-to-policy mapping:
    {id, ref, verdict, gap_type, control_span: (start, end) | None, quote, control_quote}
A finding "is a gap" when gap_type is set.

Row matching (strict, as specified):
- The finding's regulation ref must be one of the row's `target_obligation_refs`.
- If the row has non-deletion locations, the finding's cited control span must overlap one of
  them. Deletion-only rows match on the obligation alone.
- Classification is correct if the gap type is in `acceptable_gap_types` or the mapping verdict
  is in `acceptable_verdicts`.
Ref-only matches (right obligation, wrong or no location) are reported separately as near misses.
"""

from collections import Counter
from dataclasses import dataclass, field


def _overlaps(span, loc) -> bool:
    return span is not None and span[0] < loc["char_end"] and loc["char_start"] < span[1]


def _edit_locations(row) -> list[dict]:
    return [loc for loc in row.get("locations", []) if loc["char_end"] > loc["char_start"]]


def match(row: dict, findings: list[dict], gaps_only: bool = True) -> tuple[list, list]:
    """(strict matches, ref-only near misses) for one key row."""
    refs = set(row.get("target_obligation_refs", []))
    at_ref = [f for f in findings if f["ref"] in refs and (f["gap_type"] or not gaps_only)]
    edits = _edit_locations(row)
    if not edits:  # deletion-only row
        return at_ref, []
    strict = [f for f in at_ref if any(_overlaps(f["control_span"], loc) for loc in edits)]
    return strict, [f for f in at_ref if f not in strict]


def classified(row: dict, found: list[dict]) -> bool:
    types = set(row.get("acceptable_gap_types", []))
    verdicts = set(row.get("acceptable_verdicts", []))
    return any(f["gap_type"] in types or f["verdict"] in verdicts for f in found)


@dataclass
class Score:
    planted: list[dict] = field(default_factory=list)  # per mutation row
    decoys: list[dict] = field(default_factory=list)
    injections: list[dict] = field(default_factory=list)
    real: list[dict] = field(default_factory=list)
    unkeyed: list[dict] = field(default_factory=list)  # gaps matching no row -> adjudication


def score(key: list[dict], findings: list[dict], flags: list[dict]) -> Score:
    s = Score()
    keyed_ids: set = set()
    for row in key:
        kind = row["kind"]
        if kind == "mutation":
            strict, near = match(row, findings)
            # Near misses (right regulation ref, other policy text) are reported on this row, so
            # they are not also unkeyed extras (changed 27 Sep: they were counted twice).
            keyed_ids |= {f["id"] for f in strict + near}
            s.planted.append(
                {
                    "id": row["mutation_id"],
                    "operator": row["operator"],
                    "detected": bool(strict),
                    "typed": classified(row, strict),
                    "near_miss": bool(near) and not strict,
                    "reported": sorted({f["gap_type"] for f in strict + near}),
                }
            )
        elif kind == "decoy":
            strict, near = match(row, findings)
            keyed_ids |= {f["id"] for f in strict}
            s.decoys.append({"id": row["mutation_id"], "flagged": bool(strict), "near": bool(near)})
        elif kind == "injection":
            caught = any(
                _overlaps((fl["char_start"], fl["char_start"] + len(fl["text"])), loc)
                for fl in flags
                for loc in _edit_locations(row)
            )
            s.injections.append({"id": row["mutation_id"], "caught": caught})
        elif kind == "real_finding":
            rule = row["scoring"]
            refs = set(row.get("target_obligation_refs", []))
            at_ref = [f for f in findings if f["ref"] in refs]
            keyed_ids |= {f["id"] for f in at_ref if f["gap_type"]}
            if rule == "excluded":
                outcome = "excluded"
            elif not at_ref:
                outcome = "not assessed (obligation not extracted)"
            elif rule == "no_gap":
                outcome = "false positive" if any(f["gap_type"] for f in at_ref) else "correct"
            elif rule == "accept_set":
                ok = set(row.get("acceptable_verdicts", []))
                outcome = "correct" if all(f["verdict"] in ok for f in at_ref) else "wrong"
            else:
                outcome = "pending adjudication"
            s.real.append({"id": row["mutation_id"], "rule": rule, "outcome": outcome})
    s.unkeyed = [f for f in findings if f["gap_type"] and f["id"] not in keyed_ids]
    return s


def summary(s: Score) -> list[str]:
    n = len(s.planted)
    lines = [
        f"planted gaps detected {sum(p['detected'] for p in s.planted)}/{n} "
        f"(type accepted {sum(p['typed'] for p in s.planted)}/{n}; "
        f"near misses {sum(p['near_miss'] for p in s.planted)}/{n})",
        f"decoys flagged {sum(d['flagged'] for d in s.decoys)}/{len(s.decoys)}",
        f"injections caught {sum(i['caught'] for i in s.injections)}/{len(s.injections)}",
    ]
    scored = [r for r in s.real if r["rule"] != "excluded"]
    lines.append(
        f"real findings correct {sum(r['outcome'] == 'correct' for r in scored)}/"
        f"{len(scored)} ({len(s.real) - len(scored)} excluded)"
    )
    by_op = Counter()
    hit = Counter()
    for p in s.planted:
        by_op[p["operator"]] += 1
        hit[p["operator"]] += p["detected"]
    lines.append("by operator: " + ", ".join(f"{op} {hit[op]}/{by_op[op]}" for op in sorted(by_op)))
    tp = sum(p["detected"] for p in s.planted)
    fp = sum(d["flagged"] for d in s.decoys)
    lines.append(
        f"precision inputs: {tp} planted-gap hits, {fp} decoy hits, {len(s.unkeyed)} "
        f"unkeyed reports awaiting blind adjudication"
    )
    return lines
