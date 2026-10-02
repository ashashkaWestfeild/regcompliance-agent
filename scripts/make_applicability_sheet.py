"""Blind label sheet for the applicability step: is a limiting condition a bank attribute?

    uv run python scripts/make_applicability_sheet.py

Writes to eval/runs/applicability/:
  condition_sheet.csv      50 distinct conditions (seeded sample): 40 that the vocabulary did not
                           match and 10 that it did, shuffled, with no system label
  condition_private.json   what the rule, the local model and the hosted model said for each row
                           (do not open before labelling)
A labelled sheet gives the step its own accuracy number: the rule alone, and each model.
"""

import csv
import json
import os
import random
from pathlib import Path

from regcomp.applicability import classify_conditions, condition_of, hits, load_vocab
from regcomp.db import connect

SEED = 20261002
UNMATCHED, MATCHED = 40, 10
HOSTED = "groq:openai/gpt-oss-120b"
OUT = Path("eval/runs/applicability")


def main() -> None:
    vocab = load_vocab()
    with connect(autocommit=True) as conn:
        rows = conn.execute(
            "SELECT source_clause_ref, applicability->>'raw', source_span->>'quote'"
            " FROM obligation WHERE superseded_at IS NULL ORDER BY source_clause_ref, 2"
        ).fetchall()
        by_condition = {}
        for ref, raw, quote in rows:
            condition = condition_of({"applies_to": raw})
            if condition:
                by_condition.setdefault(condition.lower(), (ref, condition, quote))
        matched = sorted(c for c in by_condition if hits(c, vocab))
        unmatched = sorted(c for c in by_condition if not hits(c, vocab))
        rng = random.Random(SEED)
        sample = rng.sample(unmatched, min(UNMATCHED, len(unmatched)))
        sample += rng.sample(matched, min(MATCHED, len(matched)))
        rng.shuffle(sample)
        local = classify_conditions(sample, conn)  # cached where the stage has run with --model
        os.environ["REGCOMP_MODEL_CLASSIFY_CONDITION"] = HOSTED
        try:
            hosted = classify_conditions(sample, conn)
        except Exception as e:  # the hosted model is optional; the sheet does not depend on it
            print(f"hosted model not available ({type(e).__name__}); its column is left empty")
            hosted = {}

    OUT.mkdir(parents=True, exist_ok=True)
    private = {"seed": SEED, "rows": {}}
    with (OUT / "condition_sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "#",
                "rbi_ref",
                "regulation_text",
                "limiting_condition (as extracted)",
                "YOUR_label (bank attribute / circumstance)",
                "YOUR_attribute (if a bank attribute: which product, channel, customer type...)",
                "YOUR_notes",
            ]
        )
        for n, c in enumerate(sample, 1):
            ref, condition, quote = by_condition[c]
            w.writerow([n, ref, quote, condition, "", "", ""])
            found = hits(c, vocab)
            private["rows"][str(n)] = {
                "condition": condition,
                "rule": "bank attribute" if found else "circumstance",
                "rule_values": [t.value for t in found],
                "local_model": (local.get(c) or {}).get("kind"),
                "hosted_model": (hosted.get(c) or {}).get("kind"),
            }
    (OUT / "condition_private.json").write_text(
        json.dumps(private, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"{OUT / 'condition_sheet.csv'}: {len(sample)} conditions "
        f"({len(unmatched)} unmatched and {len(matched)} matched distinct conditions in all)"
    )


if __name__ == "__main__":
    main()
