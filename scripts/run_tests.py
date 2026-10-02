"""Stage 3 (dev set): control testing - design tests for mapped controls, operating tests from
evidence. Deterministic; the LLM never sees evidence rows.

- Design test for every control that a mapping cites (owner / frequency / evidence named).
- Operating test for each evidence file in data/evidence/<policy>/manifest.yaml, linked to the
  control mapped to the file's obligation; ineffective -> operating_failure gap.
- No mapped control -> "cannot assess" (never guessed).

    uv run python scripts/run_tests.py --policy nainital
"""

import argparse
import hashlib
import uuid
from datetime import date
from pathlib import Path

import yaml

from regcomp.db import connect
from regcomp.evidence import (
    ckycr_late,
    design_test,
    operating_test,
    read_csv,
    rekyc_overdue,
)

RULES = {
    "rekyc_overdue": lambda m: rekyc_overdue(date.fromisoformat(str(m["as_of"]))),
    "ckycr_late": lambda m: ckycr_late(int(m["deadline_days"])),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="nainital")
    args = ap.parse_args()
    folder = Path(f"data/evidence/{args.policy}")
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text(encoding="utf-8"))

    with connect(autocommit=True) as conn:
        conn.execute("DELETE FROM gap WHERE type = 'operating_failure'")
        conn.execute("DELETE FROM control_test")
        conn.execute("DELETE FROM evidence")

        # Design tests: every control cited by a covered/partial mapping.
        cited = conn.execute(
            "SELECT DISTINCT c.id, c.owner, c.frequency, c.threshold, c.expected_evidence"
            " FROM mapping m JOIN control c ON c.id = m.control_id"
            # a policy passage has no extracted attributes to test
            " WHERE c.extraction->>'method' IS DISTINCT FROM 'passage'"
        ).fetchall()
        design = {"effective": 0, "ineffective": 0}
        for cid, owner, freq, threshold, evidence in cited:
            t = design_test(
                {"owner": owner, "frequency": freq, "threshold": threshold, "evidence": evidence}
            )
            design[t.result] += 1
            conn.execute(
                "INSERT INTO control_test (control_id, kind, result, rationale)"
                " VALUES (%s, 'design', %s, %s)",
                (cid, t.result, t.rationale),
            )
        print(
            f"design tests: effective {design['effective']}, ineffective "
            f"{design['ineffective']} (of {len(cited)} cited controls)"
        )

        # Operating tests from evidence.
        for m in manifest:
            path = folder / m["file"]
            rows = read_csv(path)
            mapping = conn.execute(
                "SELECT m.id, m.control_id, o.id FROM mapping m JOIN obligation o"
                " ON o.id = m.obligation_id WHERE o.source_clause_ref = %s"
                " AND m.control_id IS NOT NULL ORDER BY m.confidence DESC LIMIT 1",
                (m["obligation_ref"],),
            ).fetchone()
            if mapping is None:
                print(f"{m['file']}: cannot assess - no control mapped to {m['obligation_ref']}")
                continue
            mapping_id, control_id, obligation_id = mapping
            ev_id = uuid.uuid4()
            t = operating_test(
                rows, RULES[m["rule"]](m), tolerance=float(m["tolerance"]), rule=m["rule"]
            )
            period = sorted(
                v
                for r in rows
                for k, v in r.items()
                if k != "account_id" and len(v) == 10 and v[4] == "-"
            )
            conn.execute(
                "INSERT INTO evidence (id, control_id, source_path, period_start, period_end,"
                " population, sample_size, exceptions, sha256)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
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
            test_id = uuid.uuid4()
            conn.execute(
                "INSERT INTO control_test (id, control_id, mapping_id, kind, result,"
                " evidence_ids, exception_rate, tolerance, rationale)"
                " VALUES (%s,%s,%s,'operating',%s,%s,%s,%s,%s)",
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
            if t.result == "ineffective":
                conn.execute(
                    "INSERT INTO gap (key, source_version, effective_from, type, obligation_id,"
                    " control_id, mapping_id, control_test_id, inherent_risk, residual_risk,"
                    " priority_score, rationale) VALUES (%s,%s,%s,'operating_failure',%s,%s,%s,"
                    "%s,'high','high',0.9,%s)",
                    (
                        f"GAP:OPS:{m['file']}",
                        "evidence",
                        date.today(),
                        obligation_id,
                        control_id,
                        mapping_id,
                        test_id,
                        t.rationale,
                    ),
                )
            print(f"{m['file']} -> {m['obligation_ref']}: {t.result} ({t.rationale})")


if __name__ == "__main__":
    main()
