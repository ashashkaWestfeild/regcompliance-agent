"""Change agent, last step: write the outcome of a change event to the versioned graph.

Old rows are never edited or deleted. The changed clauses, the obligations taken from them, and
those obligations' mappings and open gaps are closed in time (effective_to / superseded_at); the
new version's rows are added next to them and linked to the change event. The agent opens gaps;
it never marks one resolved and never accepts a risk: those are a reviewer's actions.

Everything happens in one transaction. A dry run (what-if) has no path to this step.
"""

import hashlib
from collections import Counter
from pathlib import Path

from psycopg.types.json import Jsonb

from regcomp.llm import model_for
from regcomp.risk import assess


def _document(conn, new_path: str, doc) -> tuple:
    """(id of the current regulation document, id of the new version's document row)."""
    old = conn.execute(
        "SELECT id, issuer, title FROM document WHERE kind = 'master_direction'"
        " ORDER BY issued_on DESC NULLS LAST LIMIT 1"
    ).fetchone()
    sha = hashlib.sha256(doc.text.encode()).hexdigest()
    row = conn.execute("SELECT id FROM document WHERE sha256 = %s", (sha,)).fetchone()
    if row:
        return old[0], row[0]
    synthetic = "synthetic" in Path(new_path).parts
    new = conn.execute(
        "INSERT INTO document (kind, issuer, title, version_label, sha256, text, supersedes,"
        " is_synthetic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (
            "draft" if synthetic else "amendment",
            old[1],
            old[2],
            Path(new_path).stem,
            sha,
            doc.text,
            old[0],
            synthetic,
        ),
    ).fetchone()[0]
    return old[0], new


def _clauses(conn, event, doc, new_doc, changes: list[dict], version: str, today) -> dict:
    """One clause_diff per change; the new clause row next to the superseded old one.
    Returns {changed clause ref: new clause id}."""
    by_ref = {c.ref: c for c in doc.clauses}
    new_clause = {}
    for c in changes:
        old_id = conn.execute(
            "SELECT id FROM clause WHERE key = %s AND superseded_at IS NULL", (f"REG:{c['ref']}",)
        ).fetchone()
        if old_id:  # first: only one current row per clause key may exist
            conn.execute(
                "UPDATE clause SET effective_to = %s, superseded_at = now() WHERE id = %s",
                (today, old_id[0]),
            )
        clause = by_ref.get(c["ref"]) if c["change_class"] != "repealed" else None
        if clause is not None:
            new_clause[c["ref"]] = conn.execute(
                "INSERT INTO clause (key, source_version, effective_from, document_id,"
                " clause_ref, parent_ref, heading, char_start, char_end, quote)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (
                    f"REG:{clause.ref}",
                    version,
                    today,
                    new_doc,
                    clause.ref,
                    clause.parent_ref,
                    clause.section,
                    clause.char_start,
                    clause.char_end,
                    clause.quote,
                ),
            ).fetchone()[0]
        conn.execute(
            "INSERT INTO clause_diff (change_event_id, old_clause_id, new_clause_id,"
            " change_class, summary) VALUES (%s,%s,%s,%s,%s)",
            (
                event,
                old_id and old_id[0],
                new_clause.get(c["ref"]),
                c["change_class"],
                f"[{c['effect']}] {c['summary']}",
            ),
        )
    return new_clause


def _supersede(conn, obligation_ids: list[str], today, out: Counter) -> None:
    for table, column in (
        ("gap", "obligation_id"),
        ("mapping", "obligation_id"),
        ("obligation", "id"),
    ):
        done = conn.execute(
            f"UPDATE {table} SET effective_to = %s, superseded_at = now()"
            f" WHERE {column} = ANY(%s::uuid[]) AND superseded_at IS NULL",
            (today, obligation_ids),
        )
        out[f"{table}s superseded"] += done.rowcount


def commit(conn, new_path: str, doc, state: dict, today, thread: str) -> dict:
    """state: the agent state after compare (changes, scope, new_obligations, results, delta)."""
    version = Path(new_path).stem
    changes, found = state["changes"], state["scope"]
    new_obs = {o["id"]: o for o in state.get("new_obligations", [])}
    results = {r["id"]: r for r in state.get("results", [])}
    by_ref = {c.ref: c for c in doc.clauses}
    out: Counter = Counter()
    with conn.transaction():
        old_doc, new_doc = _document(conn, new_path, doc)
        event = conn.execute(
            "INSERT INTO change_event (old_document_id, new_document_id, dry_run,"
            " affected_obligation_ids, affected_mapping_ids, projected_gap_delta, trace_id)"
            " VALUES (%s,%s,false,%s::uuid[],%s::uuid[],%s,%s) RETURNING id",
            (
                old_doc,
                new_doc,
                found["direct"] + found["by_definition"],
                found["mappings"],
                (state.get("delta") or {}).get("gap_delta"),
                thread,
            ),
        ).fetchone()[0]
        new_clause = _clauses(conn, event, doc, new_doc, changes, version, today)
        out["clause diffs"] = len(changes)
        if new_obs or any(c["effect"] == "repealed" for c in changes):
            _supersede(conn, found["direct"], today, out)

        for n, (oid, o) in enumerate(new_obs.items(), 1):
            holder = next(
                (ref for ref in new_clause if o["ref"] == ref or o["ref"].startswith(ref + "(")),
                None,
            )
            if holder is None:
                continue  # an obligation outside the changed clauses is not part of this event
            span = {
                "document_id": str(new_doc),
                "char_start": o["char_start"],
                "char_end": o["char_end"],
                "quote": o["quote"],
            }
            new_id = conn.execute(
                "INSERT INTO obligation (key, source_version, effective_from, clause_id,"
                " source_clause_ref, source_span, actor, modality, action, object, threshold,"
                " applicability, extraction) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " RETURNING id",
                (
                    f"OBL:{o['unit_ref']}#{version}-{n}",
                    version,
                    today,
                    new_clause[holder],
                    o["ref"],
                    Jsonb(span),
                    o["actor"],
                    o["modality"],
                    o["action"],
                    o["action"],
                    Jsonb({"raw": o["threshold"]}) if o.get("threshold") else None,
                    Jsonb({"raw": o.get("applies_to"), "level": o["level"]}),
                    Jsonb(
                        {
                            "model": model_for("extract_obligations"),
                            "passes": 1,
                            "pass_agreement": False,
                            "change_event": str(event),
                        }
                    ),
                ),
            ).fetchone()[0]
            out["obligations added"] += 1
            r = results.get(oid)
            if r is None or r["verdict"] is None:
                out["left for review (no verdict)"] += 1
                continue
            control = r.get("control_id") if r["verdict"] != "missing" else None
            mapping = conn.execute(
                "INSERT INTO mapping (key, source_version, effective_from, obligation_id,"
                " control_id, verdict, rationale, obligation_citations, control_citations,"
                " judges, confidence, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " RETURNING id",
                (
                    f"MAP:{new_id}",
                    version,
                    today,
                    new_id,
                    control,
                    r["verdict"] if control or r["verdict"] == "missing" else "missing",
                    r["rationale"],
                    Jsonb([{"quote": o["quote"]}]),
                    Jsonb([{"quote": r.get("control_quote")}] if control else []),
                    Jsonb(
                        [
                            {
                                "judge": "cheap",
                                "model": model_for("judge"),
                                "verdict": r["verdict"],
                                "issue": r.get("issue"),
                                "gap_type": r["gap_type"],
                                "confidence": r["confidence"],
                            }
                        ]
                    ),
                    max(0.0, min(1.0, float(r["confidence"]))),
                    "escalated" if r.get("review") else "auto",
                ),
            ).fetchone()[0]
            out["mappings added"] += 1
            if r["gap_type"]:
                clause = by_ref.get(o["ref"])
                heading = (
                    " | ".join(h for h in (clause.chapter, clause.section) if h) if clause else ""
                )
                risk = assess(f"{o['action']}. {o['quote']}", heading, r["gap_type"])
                conn.execute(
                    "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                    " control_id, mapping_id, inherent_risk, residual_risk, priority_score,"
                    " rationale, detected_by_change_event, tier)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        f"GAP:{new_id}",
                        version,
                        today,
                        r["gap_type"],
                        new_id,
                        control,
                        mapping,
                        risk.inherent,
                        risk.residual,
                        risk.priority,
                        r["rationale"],
                        event,
                        "review" if r.get("review") else "high",
                    ),
                )
                out["gaps opened"] += 1
    return {"change_event": str(event), **out}
