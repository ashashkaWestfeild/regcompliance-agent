"""Stage 3 (dev set): control testing - design tests for mapped controls, operating tests from
evidence. Deterministic; the LLM never sees evidence rows.

- Design test for every control that a mapping cites (owner / frequency / evidence named).
- Operating test for each evidence file in data/evidence/<policy>/manifest.yaml, linked to the
  control mapped to the file's obligation; ineffective -> operating_failure gap.
- No mapped control -> "cannot assess" (never guessed).

    uv run python scripts/run_tests.py --policy nainital
"""

import argparse
from pathlib import Path

import yaml

from regcomp.db import connect
from regcomp.evidence import design_test
from regcomp.monitor import assess_batch


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

        # Operating tests from evidence (same code path as a later batch: regcomp/monitor.py).
        for m in manifest:
            out = assess_batch(conn, m, folder / m["file"])
            if out["result"] == "cannot_assess":
                print(f"{m['file']}: cannot assess - {out['rationale']}")
            else:
                print(f"{m['file']} -> {m['obligation_ref']}: {out['result']} ({out['rationale']})")


if __name__ == "__main__":
    main()
