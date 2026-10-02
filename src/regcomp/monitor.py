"""Ongoing monitoring by evidence: a new batch of operating evidence arrives for a control.

The second trigger of the system (the first is a new version of the regulation, handled by the
change agent). It needs no model and no agentic planning: the batch is tested by a fixed rule,
compared with the control's previous operating test, and the graph is updated.

    effective   -> ineffective : an operating_failure gap is opened
    ineffective -> ineffective : the open gap stays, with the new figures
    ineffective -> effective   : the gap is NOT closed; it is moved to the review queue as
                                 "recovered, awaiting reviewer closure" (only a reviewer closes)
    effective   -> effective   : nothing to do
    no mapped control          : cannot assess (never guessed)

The model never sees evidence rows; only counts are stored.
"""

import hashlib
import uuid
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from regcomp.evidence import ckycr_late, operating_test, read_csv, rekyc_overdue

RULES = {
    "rekyc_overdue": lambda m: rekyc_overdue(date.fromisoformat(str(m["as_of"]))),
    "ckycr_late": lambda m: ckycr_late(int(m["deadline_days"])),
}


def transition(before: str | None, now: str) -> str:
    """What a new operating result means given the previous one."""
    if now == "cannot_assess":
        return "cannot_assess"
    if now == "ineffective":
        return "still_failing" if before == "ineffective" else "newly_failing"
    return "recovered" if before == "ineffective" else "healthy"


def assess_batch(conn, entry: dict, path: Path, today: date | None = None) -> dict:
    """Test one evidence file (`entry`: file, obligation_ref, rule, tolerance and the rule's
    parameters, as in data/evidence/<policy>/manifest.yaml) and record the outcome."""
    today = today or date.today()
    rows = read_csv(path)
    mapping = conn.execute(
        "SELECT m.id, m.control_id, o.id FROM mapping m JOIN obligation o"
        " ON o.id = m.obligation_id WHERE o.source_clause_ref = %s AND m.control_id IS NOT NULL"
        " AND m.superseded_at IS NULL ORDER BY m.confidence DESC LIMIT 1",
        (entry["obligation_ref"],),
    ).fetchone()
    if mapping is None:
        return {
            "file": path.name,
            "obligation_ref": entry["obligation_ref"],
            "result": "cannot_assess",
            "change": "cannot_assess",
            "rationale": f"no control mapped to {entry['obligation_ref']}",
        }
    mapping_id, control_id, obligation_id = mapping
    previous = conn.execute(
        "SELECT result::text FROM control_test WHERE control_id = %s AND kind = 'operating'"
        " ORDER BY tested_at DESC LIMIT 1",
        (control_id,),
    ).fetchone()
    t = operating_test(
        rows, RULES[entry["rule"]](entry), tolerance=float(entry["tolerance"]), rule=entry["rule"]
    )
    change = transition(previous and previous[0], t.result)
    period = sorted(
        v for r in rows for k, v in r.items() if k != "account_id" and len(v) == 10 and v[4] == "-"
    )
    ev_id, test_id = uuid.uuid4(), uuid.uuid4()
    gap_key = f"GAP:OPS:{entry['obligation_ref']}"
    with conn.transaction():
        conn.execute(
            "INSERT INTO evidence (id, control_id, source_path, period_start, period_end,"
            " population, sample_size, exceptions, sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ev_id,
                control_id,
                path.as_posix(),
                period[0],
                period[-1],
                t.population,
                t.population,
                t.exceptions,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ),
        )
        conn.execute(
            "INSERT INTO control_test (id, control_id, mapping_id, kind, result, evidence_ids,"
            " exception_rate, tolerance, rationale) VALUES (%s,%s,%s,'operating',%s,%s,%s,%s,%s)",
            (
                test_id,
                control_id,
                mapping_id,
                t.result,
                [ev_id],
                t.exception_rate,
                t.tolerance,
                t.rationale,
            ),
        )
        open_gap = conn.execute(
            "SELECT id FROM gap WHERE key = %s AND superseded_at IS NULL AND status = 'open'",
            (gap_key,),
        ).fetchone()
        evidence = {"check": "operating", "change": change, "file": path.name}
        if t.result == "ineffective" and open_gap is None:
            conn.execute(
                "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                " control_id, mapping_id, control_test_id, inherent_risk, residual_risk,"
                " priority_score, rationale, tier, evidence)"
                " VALUES (%s,'evidence',%s,'operating_failure',%s,%s,%s,%s,'high','high',0.9,"
                "%s,'high',%s)",
                (
                    gap_key,
                    today,
                    obligation_id,
                    control_id,
                    mapping_id,
                    test_id,
                    t.rationale,
                    Jsonb(evidence),
                ),
            )
        elif t.result == "ineffective":
            conn.execute(
                "UPDATE gap SET control_test_id = %s, rationale = %s, tier = 'high',"
                " evidence = %s WHERE id = %s",
                (test_id, t.rationale, Jsonb(evidence), open_gap[0]),
            )
        elif open_gap is not None:  # recovered: a reviewer closes it, the system does not
            conn.execute(
                "UPDATE gap SET control_test_id = %s, tier = 'review', evidence = %s,"
                " rationale = %s WHERE id = %s",
                (
                    test_id,
                    Jsonb(evidence),
                    f"Latest evidence is within tolerance ({t.rationale}). Awaiting reviewer"
                    " closure.",
                    open_gap[0],
                ),
            )
    return {
        "file": path.name,
        "obligation_ref": entry["obligation_ref"],
        "result": t.result,
        "change": change,
        "rationale": t.rationale,
    }
