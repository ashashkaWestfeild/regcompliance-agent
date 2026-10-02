"""Change agent part 2: the tools that redo only what a change touches.

    re_extract   obligations of the changed clauses in the new version (same extractor, citation
                 gate and level classifier as ingestion)
    re_map       retrieve policy candidates for those obligations and judge them (same judge and
                 gap rules as ingestion); a unit the judge cannot answer is reported as
                 "cannot assess" and goes to review instead of ending the run
    current      what the graph holds today for the obligations in scope
    compare      old against new: gaps that would open, gaps that would close

Nothing here writes to the compliance graph. With dry_run the agent stops after compare, which
is the what-if mode; writing the result is change/commit.py.
"""

import re
from collections import defaultdict

from regcomp.llm import LLMError, embed
from regcomp.pipeline.extract import extract_obligations
from regcomp.pipeline.judge import judge_unit
from regcomp.pipeline.level import classify_unit
from regcomp.pipeline.units import units

TOP_K = 5  # candidates the judge sees
RETRIEVE_K = 20


def _norm(text: str) -> str:
    return " ".join(re.findall(r"\w+", (text or "").lower()))


def changed_units(doc, refs: list[str]) -> list:
    """The extraction units of `doc` that contain a changed clause."""
    spans = [(c.char_start, c.char_end) for c in doc.clauses if c.ref in refs]
    return [
        u
        for u in units(doc)
        if any(u.start < end and start < u.start + len(u.text) for start, end in spans)
    ]


def re_extract(doc, refs: list[str], conn) -> list[dict]:
    """Obligations stated inside the changed clauses of the new version, with their level."""
    spans = [(c.char_start, c.char_end) for c in doc.clauses if c.ref in refs]
    found = extract_obligations(changed_units(doc, refs), conn).items
    inside = [o for o in found if any(s <= o["char_start"] < e for s, e in spans)]
    by_unit = defaultdict(list)
    for n, o in enumerate(inside):
        o["id"] = f"new-{n + 1}"
        o["ref"] = max(
            (c for c in doc.clauses if c.char_start <= o["char_start"] < c.char_end),
            key=lambda c: c.depth,
        ).ref
        by_unit[o["unit_ref"]].append(o)
    for obs in by_unit.values():
        levels = classify_unit(obs, conn)
        for o in obs:
            o["level"] = levels[o["id"]]["level"]
    return inside


def _same_text(a: tuple[int, int], b: tuple[int, int]) -> bool:
    inside = min(a[1], b[1]) - max(a[0], b[0])
    return inside >= 0.5 * min(a[1] - a[0], b[1] - b[0])


def candidates_for(conn, obligation: dict) -> list[dict]:
    """Top policy candidates for one obligation: embedding order from pgvector, repeats of the
    same policy text dropped (the retrieval the dev baseline uses)."""
    text = f"{obligation['action']}. {obligation.get('threshold') or ''} {obligation['quote']}"
    vec = "[" + ",".join(f"{x:.6f}" for x in embed([text])[0]) + "]"
    rows = conn.execute(
        "SELECT c.id::text, c.control_ref, c.source_span->>'quote',"
        " (c.source_span->>'char_start')::int, (c.source_span->>'char_end')::int"
        " FROM embedding e JOIN control c ON c.id = e.owner_id"
        " WHERE e.owner_kind = 'control' ORDER BY e.vec <=> %s::vector LIMIT %s",
        (vec, RETRIEVE_K),
    ).fetchall()
    kept: list[dict] = []
    for cid, ref, quote, start, end in rows:
        if not any(_same_text((start, end), k["span"]) for k in kept):
            kept.append({"id": cid, "ref": ref, "quote": quote, "span": (start, end)})
    return kept[:TOP_K]


def re_map(obligations: list[dict], conn) -> list[dict]:
    """Judge the obligations against freshly retrieved candidates, unit by unit."""
    by_unit = defaultdict(list)
    for o in obligations:
        by_unit[o["unit_ref"]].append(o)
    out = []
    for obs in by_unit.values():
        hits = {o["id"]: candidates_for(conn, o) for o in obs}
        cand = {c["id"]: c for o in obs for c in hits[o["id"]]}
        local = {cid: f"C{n}" for n, cid in enumerate(cand, 1)}
        payload = [
            {
                "id": f"O{n}",
                "modality": o["modality"],
                "quote": o["quote"],
                "threshold": o.get("threshold"),
                "applies_to": o.get("applies_to"),
                "candidates": [local[c["id"]] for c in hits[o["id"]]],
            }
            for n, o in enumerate(obs, 1)
        ]
        reason = "cannot assess: no judge answer"
        try:
            judged = judge_unit(payload, {local[cid]: c for cid, c in cand.items()}, conn)
        except LLMError as e:
            judged = []
            reason = f"cannot assess: {e}"
        by_label = {r["obligation"]: r for r in judged}
        back = {v: k for k, v in local.items()}
        for n, o in enumerate(obs, 1):
            r = by_label.get(f"O{n}")
            base = {k: o[k] for k in ("id", "ref", "action", "quote", "modality", "level")}
            if r is None:  # the judge failed or skipped it: a person decides, never a guess
                out.append(
                    base
                    | {
                        "verdict": None,
                        "gap_type": None,
                        "review": True,
                        "rationale": reason,
                    }
                )
                continue
            control = cand.get(back.get(r["control"])) if r["control"] else None
            out.append(
                base
                | {
                    "verdict": r["verdict"],
                    "issue": r["issue"],
                    # as in ingestion: a gap is raised only on a policy-level obligation
                    "gap_type": r["gap_type"] if o["level"] == "policy" else None,
                    "control_id": control and control["id"],
                    "control_ref": control and control["ref"],
                    "control_quote": control and control["quote"],
                    "rationale": r["rationale"],
                    "confidence": r["confidence"],
                    "review": not r["citation_ok"] or r["confidence"] < 0.7,
                }
            )
    return out


def current(conn, obligation_ids: list[str]) -> list[dict]:
    """Today's verdict and open gap for the obligations in scope."""
    if not obligation_ids:
        return []
    rows = conn.execute(
        "SELECT o.id::text, o.source_clause_ref, o.action, m.verdict::text, g.type::text"
        " FROM obligation o LEFT JOIN mapping m ON m.obligation_id = o.id"
        " AND m.superseded_at IS NULL"
        " LEFT JOIN gap g ON g.obligation_id = o.id AND g.status = 'open'"
        " AND g.superseded_at IS NULL WHERE o.id = ANY(%s::uuid[])",
        (obligation_ids,),
    ).fetchall()
    return [
        {"id": i, "ref": ref, "action": action, "verdict": verdict, "gap_type": gap}
        for i, ref, action, verdict, gap in rows
    ]


def compare(old: list[dict], new: list[dict]) -> dict:
    """What re-analysis changes. Old and new obligations are paired by clause and action; an
    old one with no partner is retired (its text is gone), a new one with no partner is new."""
    old_by = {(o["ref"], _norm(o["action"])): o for o in old}
    opened, closed, changed, same, review = [], [], [], 0, []
    seen = set()
    for n in new:
        key = (n["ref"], _norm(n["action"]))
        was = old_by.get(key)
        seen.add(key)
        label = {"ref": n["ref"], "action": n["action"]}
        if n.get("review"):
            review.append(label | {"why": n["rationale"]})
        before, after = was and was["gap_type"], n["gap_type"]
        if after and not before:
            opened.append(label | {"gap_type": after, "why": n["rationale"], "new": was is None})
        elif before and not after and n["verdict"] == "covered":
            closed.append(label | {"gap_type": before})
        elif before and not after:
            # no longer raised, but not judged covered either (e.g. now classed procedure-level):
            # a person looks at it; the agent does not count it as closed
            review.append(label | {"why": f"gap {before} no longer raised: {n['rationale']}"})
        elif before != after:
            changed.append(label | {"from": before, "to": after})
        else:
            same += 1
    retired = [o for key, o in old_by.items() if key not in seen]
    closed += [
        {"ref": o["ref"], "action": o["action"], "gap_type": o["gap_type"], "retired": True}
        for o in retired
        if o["gap_type"]
    ]
    return {
        "opened": opened,
        "closed": closed,
        "changed_type": changed,
        "unchanged": same,
        "retired_obligations": len(retired),
        "new_obligations": sum(1 for n in new if (n["ref"], _norm(n["action"])) not in old_by),
        "needs_review": review,
        "gap_delta": len(opened) - len(closed),
    }
