"""Export one committed change event as a read-only version history for the app.

    uv run python scripts/export_version_history.py      # DATABASE_URL must be the d2 copy

The hosted demo only ever runs the change agent as a dry run. To show that the graph "evolves over
time", the commit step was run once on the d2 copy of the database (scripts/run_change.py without
--dry-run) and this script exports what it wrote: the change event, the changed clause before and
after, each closed row beside the row that replaced it (obligations, mappings, gaps), and the gap
delta. Read-only; the output is eval/reports/version_history_d2.json, stamped with the code commit.
"""

import json
import subprocess
from pathlib import Path

from regcomp.db import connect, database_role, database_url

OUT = Path("eval/reports/version_history_d2.json")


def rows(conn, sql: str, params=()) -> list[dict]:
    cur = conn.execute(sql, params)
    names = [d.name for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def main() -> None:
    if database_role(database_url()) != "d2":
        raise SystemExit("run this against the d2 copy only (REGCOMP_D2_HOST)")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    with connect() as conn:
        conn.execute("SET default_transaction_read_only = on")
        event = rows(
            conn,
            "SELECT e.id::text, e.received_at::text, e.dry_run, e.projected_gap_delta,"
            " o.version_label AS old_version, n.version_label AS new_version,"
            " n.title AS new_title FROM change_event e"
            " LEFT JOIN document o ON o.id = e.old_document_id"
            " JOIN document n ON n.id = e.new_document_id"
            " WHERE NOT e.dry_run ORDER BY e.received_at DESC LIMIT 1",
        )[0]
        diffs = rows(
            conn,
            "SELECT d.change_class::text, d.summary, oc.clause_ref, oc.quote AS before,"
            " nc.quote AS after FROM clause_diff d"
            " LEFT JOIN clause oc ON oc.id = d.old_clause_id"
            " LEFT JOIN clause nc ON nc.id = d.new_clause_id WHERE d.change_event_id = %s",
            (event["id"],),
        )
        when = "(SELECT received_at FROM change_event WHERE id = %s)"
        closed_obl = rows(
            conn,
            "SELECT source_clause_ref AS ref, action, modality::text, source_version,"
            " effective_from::text, effective_to::text, superseded_at::text FROM obligation"
            f" WHERE superseded_at IS NOT NULL AND superseded_at >= {when} ORDER BY action",
            (event["id"],),
        )
        new_obl = rows(
            conn,
            "SELECT source_clause_ref AS ref, action, modality::text, source_version,"
            " effective_from::text, recorded_at::text FROM obligation"
            f" WHERE superseded_at IS NULL AND recorded_at >= {when} ORDER BY action",
            (event["id"],),
        )
        closed_map = rows(
            conn,
            "SELECT o.source_clause_ref AS ref, m.verdict::text, m.source_version,"
            " m.superseded_at::text FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
            f" WHERE m.superseded_at IS NOT NULL AND m.superseded_at >= {when}",
            (event["id"],),
        )
        new_map = rows(
            conn,
            "SELECT o.source_clause_ref AS ref, m.verdict::text, m.source_version,"
            " m.recorded_at::text FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
            f" WHERE m.superseded_at IS NULL AND m.recorded_at >= {when}",
            (event["id"],),
        )
        closed_gap = rows(
            conn,
            "SELECT o.source_clause_ref AS ref, g.type::text, g.tier, g.status::text,"
            " g.superseded_at::text FROM gap g JOIN obligation o ON o.id = g.obligation_id"
            f" WHERE g.superseded_at IS NOT NULL AND g.superseded_at >= {when}",
            (event["id"],),
        )
        new_gap = rows(
            conn,
            "SELECT o.source_clause_ref AS ref, g.type::text, g.tier, g.status::text,"
            " g.rationale FROM gap g JOIN obligation o ON o.id = g.obligation_id"
            " WHERE g.detected_by_change_event = %s",
            (event["id"],),
        )
    out = {
        "what": "Recorded run of the change agent's commit step on the d2 copy of the database "
        "(not the live demo database), synthetic draft circular, local qwen3:8b from the "
        "model-call cache. Development data.",
        "code_commit": commit,
        "event": event,
        "clause_diff": diffs,
        "obligations": {"closed": closed_obl, "added": new_obl},
        "mappings": {"closed": closed_map, "added": new_map},
        "gaps": {"closed": closed_gap, "opened": new_gap},
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"{OUT}: event {event['id'][:8]}, {len(diffs)} clause change(s); obligations closed "
        f"{len(closed_obl)} / added {len(new_obl)}; mappings closed {len(closed_map)} / added "
        f"{len(new_map)}; gaps closed {len(closed_gap)} / opened {len(new_gap)}"
    )


if __name__ == "__main__":
    main()
