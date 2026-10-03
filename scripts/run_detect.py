"""Stage 3c (D2 attempt): second pass over covered verdicts, after run_verify.py and before
run_risk.py. Does the passage the judge relied on carry the duty as RBI states it?

  - definition support (code): the judge's supporting passage defines a term instead of stating
    a duty -> missing_control
  - scope question (model, schema-generic, no examples): asked only when (a) the code rule
    proposes a modifier added in front of RBI's own words, (b) the supporting passage sits under
    a list lead-in, or (c) the best supporting sentence is below CLOSE overlap with RBI's wording
    (PROBLEMS_LOG P-056). The passage is shown with its lead-in. "narrower" becomes a
    narrow_scope finding only if the limiting words the model names occur in the policy text.
    A proposed modifier never becomes a finding on its own.

All findings go to the review queue; nothing the judge or run_verify decided is changed. Safe to
re-run: it first removes its own earlier findings. Model: scope_check (local qwen3:8b unless
REGCOMP_MODEL_SCOPE_CHECK says otherwise); answers are cached.

    uv run python scripts/run_detect.py [--stop-after-min 25]
"""

import argparse
import time
from collections import Counter

from psycopg.types.json import Jsonb

from regcomp.db import connect
from regcomp.llm import LLMError, complete_json, model_for
from regcomp.pipeline.detect import (
    SCOPE_SCHEMA,
    SCOPE_SYSTEM,
    Clause,
    added_modifiers,
    definition_support,
    lead_in,
    limiting_words_found,
    scope_prompt,
    support_overlap,
)
from regcomp.pipeline.verify import CLOSE

TAG = "run_detect"
BATCH = 5  # items per scope question


def add_gap(conn, row: dict, gap_type: str, evidence: dict, rationale: str) -> None:
    conn.execute(
        "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
        " control_id, mapping_id, inherent_risk, residual_risk, priority_score,"
        " rationale, tier, evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            f"GAP:{row['oid']}",
            row["version"],
            row["effective"],
            gap_type,
            row["oid"],
            row["control"],
            row["mapping"],
            "medium",
            "medium",
            0.5,
            rationale,
            "review",
            Jsonb(evidence | {"added_by": TAG}),
        ),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop-after-min", type=float, default=None)
    args = ap.parse_args()
    started = time.time()
    stats = Counter()
    with connect(autocommit=True) as conn:
        conn.execute("DELETE FROM gap WHERE evidence->>'added_by' = %s", (TAG,))
        text = conn.execute("SELECT text FROM document WHERE kind = 'policy'").fetchone()[0]
        clauses = [
            Clause(ref, s, e)
            for ref, s, e in conn.execute(
                "SELECT c.clause_ref, c.char_start, c.char_end FROM clause c"
                " JOIN document d ON d.id = c.document_id"
                " WHERE d.kind = 'policy' AND c.superseded_at IS NULL"
            ).fetchall()
        ]
        fields = ["oid", "version", "effective", "obligation", "mapping", "control", "passage",
                  "start", "end"]  # fmt: skip
        rows = [
            dict(zip(fields, r, strict=True))
            for r in conn.execute(
                "SELECT o.id, o.source_version, o.effective_from, o.source_span->>'quote',"
                " m.id, c.id, c.source_span->>'quote',"
                " (c.source_span->>'char_start')::int, (c.source_span->>'char_end')::int"
                " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
                " JOIN control c ON c.id = m.control_id"
                " WHERE m.verdict = 'covered' AND m.superseded_at IS NULL"
                " AND o.superseded_at IS NULL"
                " AND NOT EXISTS (SELECT 1 FROM gap g WHERE g.mapping_id = m.id"
                "                 AND g.superseded_at IS NULL AND g.type <> 'operating_failure')"
                " ORDER BY o.source_clause_ref, m.id"
            ).fetchall()
        ]
        asks = []
        for row in rows:
            stats["covered verdicts checked"] += 1
            if definition_support(row["obligation"], row["passage"]):
                add_gap(
                    conn,
                    row,
                    "missing_control",
                    {"rule": "definition_support"},
                    "The policy passage the judge relied on defines the term; it does not state "
                    "the duty.",
                )
                stats["definition support -> review"] += 1
                continue
            triggers = []
            mods = added_modifiers(row["obligation"], row["passage"])
            if mods:
                triggers.append("modifier")
            lead = lead_in(clauses, text, row["start"], row["end"]) if row["start"] else None
            if lead:
                triggers.append("lead_in")
            overlap = support_overlap(row["obligation"], row["passage"])
            if overlap < CLOSE:
                triggers.append("low_overlap")
            if not triggers:
                continue
            for t in triggers:
                stats[f"scope question trigger: {t}"] += 1
            asks.append(
                row
                | {
                    "id": str(len(asks) + 1),
                    "lead_in": lead,
                    "triggers": triggers,
                    "overlap": overlap,
                    "modifiers": [m.added for m in mods],
                }
            )
        print(
            f"scope questions to ask: {len(asks)} in batches of {BATCH} "
            f"(model {model_for('scope_check')})",
            flush=True,
        )
        for n in range(0, len(asks), BATCH):
            if args.stop_after_min and time.time() - started > args.stop_after_min * 60:
                print(f"stopped after {args.stop_after_min} min; re-run to resume from the cache")
                break
            batch = asks[n : n + BATCH]
            local = [it | {"id": str(k + 1)} for k, it in enumerate(batch)]
            try:
                answer = complete_json(
                    "scope_check", SCOPE_SYSTEM, scope_prompt(local), SCOPE_SCHEMA, conn=conn
                )
            except LLMError as e:
                stats["scope question failed (skipped)"] += len(batch)
                print(f"  batch {n // BATCH + 1}: model error, skipped: {e}", flush=True)
                continue
            by_id = {r.get("item"): r for r in answer.get("results", [])}
            for it in local:
                r = by_id.get(it["id"])
                if not r:
                    stats["scope question: no answer"] += 1
                    continue
                stats[f"scope answer: {r['scope']}"] += 1
                if r["scope"] != "narrower":
                    continue
                if not limiting_words_found(r, it):
                    stats["narrower, but limiting words not in the policy text (dropped)"] += 1
                    continue
                add_gap(
                    conn,
                    it,
                    "narrow_scope",
                    {
                        "rule": "scope_question",
                        "triggers": it["triggers"],
                        "limiting_words": r["limiting_words"],
                        "lead_in": it["lead_in"],
                        "overlap": it["overlap"],
                        "proposed_modifiers": it["modifiers"],
                    },
                    f"Scope check: the policy applies the duty only in part "
                    f"('{r['limiting_words']}'). {r['rationale']}",
                )
                stats["scope question -> narrow_scope, review"] += 1
            done = min(n + BATCH, len(asks))
            print(f"[{time.strftime('%H:%M:%S')}] scope checked {done}/{len(asks)}", flush=True)
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
