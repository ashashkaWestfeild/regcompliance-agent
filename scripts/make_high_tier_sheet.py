"""Blind sheet for the high-confidence findings that nothing has adjudicated yet.

    uv run python scripts/make_high_tier_sheet.py

Writes to eval/runs/confidence/:
  high_tier_sheet.csv      the unadjudicated high-confidence findings mixed with half as many
                           pairs the system judged covered, shuffled, with no system label
  high_tier_private.json   which rows were findings, keyed by content (regulation reference and
                           character spans), so labels still apply after a database rebuild
Once labelled (gap / no gap), scripts/fit_confidence.py reads the sheet as a third source of
truth and the confidence records become real hit rates. Label before the evaluation freeze.
"""

import csv
import json
import random
from pathlib import Path

from regcomp.db import connect

SEED = 20261003
OUT = Path("eval/runs/confidence")
TABLE = Path("eval/reports/confidence_table.json")
_SPAN = "({0}.source_span->>'char_start')::int, ({0}.source_span->>'char_end')::int"


def main() -> None:
    with connect(autocommit=True) as conn:
        findings = conn.execute(
            f"SELECT o.source_clause_ref, {_SPAN.format('o')}, o.action, o.threshold->>'raw',"
            f" o.source_span->>'quote', c.source_span->>'quote', {_SPAN.format('c')},"
            " g.type::text FROM gap g JOIN obligation o ON o.id = g.obligation_id"
            " LEFT JOIN mapping m ON m.id = g.mapping_id"
            " LEFT JOIN control c ON c.id = COALESCE(g.control_id, m.control_id)"
            " WHERE g.status = 'open' AND g.superseded_at IS NULL AND g.tier = 'high'"
            " AND g.type <> 'operating_failure' ORDER BY 1, 2, 4"
        ).fetchall()
        covered = conn.execute(
            f"SELECT o.source_clause_ref, {_SPAN.format('o')}, o.action, o.threshold->>'raw',"
            f" o.source_span->>'quote', c.source_span->>'quote', {_SPAN.format('c')}, NULL"
            " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
            " JOIN control c ON c.id = m.control_id"
            " WHERE m.superseded_at IS NULL AND m.verdict = 'covered'"
            " AND NOT EXISTS (SELECT 1 FROM gap g WHERE g.obligation_id = o.id"
            " AND g.superseded_at IS NULL) ORDER BY 1, 2, 4"
        ).fetchall()
    # leave out what the answer key or the 50-pair sheet already settles (fit_confidence.py)
    settled = set()
    if TABLE.exists():
        settled = {tuple(k) for k in json.loads(TABLE.read_text("utf-8")).get("settled", [])}
    open_findings = [f for f in findings if (f[0], f[1], f[2], f[7], f[8]) not in settled]
    rng = random.Random(SEED)
    fillers = rng.sample(covered, min(len(covered), max(1, len(open_findings) // 2)))
    rows = [(f, True) for f in open_findings] + [(f, False) for f in fillers]
    rng.shuffle(rows)

    OUT.mkdir(parents=True, exist_ok=True)
    private = {"seed": SEED, "rows": {}}
    with (OUT / "high_tier_sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "#",
                "rbi_ref",
                "regulation_text",
                "obligation_being_checked (as extracted)",
                "policy_text (the passage the system compared it with)",
                "YOUR_label (gap / no gap)",
                "YOUR_notes",
            ]
        )
        for n, (f, is_finding) in enumerate(rows, 1):
            ref, o_start, o_end, action, threshold, quote, passage, c_start, c_end, _ = f
            duty = action + (f" ({threshold})" if threshold else "")
            w.writerow([n, ref, quote, duty, passage or "(no policy passage cited)", "", ""])
            private["rows"][str(n)] = {
                "system_finding": is_finding,
                "key": [ref, o_start, o_end, c_start, c_end],
            }
    (OUT / "high_tier_private.json").write_text(json.dumps(private, indent=1), encoding="utf-8")
    print(
        f"{OUT / 'high_tier_sheet.csv'}: {len(rows)} rows ({len(open_findings)} of "
        f"{len(findings)} high-confidence findings not yet adjudicated, {len(fillers)} covered "
        "pairs)"
    )


if __name__ == "__main__":
    main()
