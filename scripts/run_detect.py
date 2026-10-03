"""Stage 3c (D2 attempt): second pass over covered verdicts, after run_verify.py and before
run_risk.py. Does the passage the judge relied on carry the duty as RBI states it?

  - definition support: the judge's supporting passage defines a term instead of stating a duty
    -> missing_control, review queue
  - added modifier: the supporting policy sentence follows RBI's sentence but adds words in front
    of one of RBI's own words (src/regcomp/pipeline/detect.py) -> narrow_scope, review queue

Findings go to the review queue; nothing the judge or run_verify decided is changed. Safe to
re-run: it first removes its own earlier findings.

    uv run python scripts/run_detect.py
"""

from collections import Counter

from psycopg.types.json import Jsonb

from regcomp.db import connect
from regcomp.pipeline.detect import added_modifiers, definition_support

TAG = "run_detect"


def main() -> None:
    stats = Counter()
    with connect(autocommit=True) as conn:
        conn.execute("DELETE FROM gap WHERE evidence->>'added_by' = %s", (TAG,))
        rows = conn.execute(
            "SELECT o.id, o.source_version, o.effective_from, o.source_span->>'quote',"
            " m.id, c.id, c.source_span->>'quote'"
            " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
            " JOIN control c ON c.id = m.control_id"
            " WHERE m.verdict = 'covered' AND m.superseded_at IS NULL"
            " AND o.superseded_at IS NULL"
            " AND NOT EXISTS (SELECT 1 FROM gap g WHERE g.mapping_id = m.id"
            "                 AND g.superseded_at IS NULL AND g.type <> 'operating_failure')"
        ).fetchall()
        for oid, version, effective, obligation, mapping, control, passage in rows:
            stats["covered verdicts checked"] += 1
            found = None
            if definition_support(obligation, passage):
                found = (
                    "missing_control",
                    {"rule": "definition_support"},
                    "The policy passage the judge relied on defines the term; it does not state "
                    "the duty.",
                )
            else:
                mods = added_modifiers(obligation, passage)
                if mods:
                    added = "; ".join(f"'{m.added}' before '{m.before}'" for m in mods)
                    found = (
                        "narrow_scope",
                        {
                            "rule": "added_modifier",
                            "added": [m.added for m in mods],
                            "before": [m.before for m in mods],
                            "overlap": mods[0].overlap,
                            "sentence": mods[0].sentence,
                        },
                        f"Text comparison: the policy sentence follows RBI's wording but adds "
                        f"{added}, so the duty may cover less than RBI requires.",
                    )
            if not found:
                continue
            gap_type, evidence, rationale = found
            conn.execute(
                "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                " control_id, mapping_id, inherent_risk, residual_risk, priority_score,"
                " rationale, tier, evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    f"GAP:{oid}",
                    version,
                    effective,
                    gap_type,
                    oid,
                    control,
                    mapping,
                    "medium",
                    "medium",
                    0.5,
                    rationale,
                    "review",
                    Jsonb(evidence | {"added_by": TAG}),
                ),
            )
            stats[f"{evidence['rule']} -> review"] += 1
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
