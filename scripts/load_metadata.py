"""Load source metadata for citations: document fields from data/sources.yaml, and RBI's
clause-level amendment markers from the parser. No model is involved and no verdict changes.

    uv run python scripts/load_metadata.py --policy nainital

Run after run_map.py (which creates the document and clause rows). Repeatable.
"""

import argparse

from psycopg.types.json import Jsonb

from regcomp.db import connect
from regcomp.ingest.rbi_html import parse_file
from regcomp.policies import policy
from regcomp.sources import marker_date, policy_meta, regulation_meta

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="nainital")
    ap.add_argument("--held-out", action="store_true")
    args = ap.parse_args()
    policy(args.policy, held_out=args.held_out)  # the guard on the held-out banks
    with connect() as conn:
        reg_id, version = conn.execute(
            "SELECT id, version_label FROM document WHERE kind = 'master_direction'"
        ).fetchone()
        reg = regulation_meta(version)
        conn.execute(
            "UPDATE document SET source_title = %s, reference_no = %s, issued_on = %s,"
            " effective_from = %s, amended_by = %s, url = %s WHERE id = %s",
            (
                reg["source_title"],
                reg["reference_no"],
                reg["issued_on"],
                reg["version_date"],
                reg["amended_by"],
                reg["url"],
                reg_id,
            ),
        )
        pol = policy_meta(args.policy)
        conn.execute(
            "UPDATE document SET source_title = %s, stated_date = %s, stated_date_kind = %s,"
            " url = %s WHERE kind = 'policy'",
            (pol["source_title"], pol["stated_date"], pol["stated_date_kind"], pol["url"]),
        )
        marked = [c for c in parse_file(REGULATION).clauses if c.amended_by]
        conn.execute("UPDATE clause SET amended_by = '[]' WHERE document_id = %s", (reg_id,))
        stored = 0
        for c in marked:
            stored += conn.execute(
                "UPDATE clause SET amended_by = %s WHERE document_id = %s AND clause_ref = %s"
                " AND superseded_at IS NULL",
                (Jsonb(c.amended_by), reg_id, c.ref),
            ).rowcount
        conn.commit()
    print(
        f"regulation: {reg['reference_no']}; issued {reg['issued_on']}; version date "
        f"{reg['version_date']}"
    )
    print(f"policy: {pol['source_title']}; {pol['stated_date_kind']}: {pol['stated_date']}")
    print(f"amendment markers stored on {stored} of {len(marked)} marked clauses:")
    for c in marked:
        print(f"- {c.ref}: effective {marker_date(c.amended_by[0])}")


if __name__ == "__main__":
    main()
