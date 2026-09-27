"""Error analysis worksheet: why does the pipeline report gaps the answer key does not contain?

User rule (27 Sep): before any change, classify the cause of 30 unkeyed ("extra") gaps:
  (a) applicability  - obligation not expected at policy level (SOP / system / not applicable)
  (b) granularity    - the policy covers it at section level or by reference
  (c) retrieval      - correct policy text exists but was not in the judge's top-5
  (d) judge          - right candidates, wrong verdict
  plus (e) real gap (the extra is correct) and (f) extraction (the obligation itself is wrong).

The 30 are sampled (seeded) from extras NOT on the blind adjudication sheet, so the analyst's
reading never touches the user's gold-set pairs. For each extra the worksheet shows what the
judge saw (the same pgvector top-20 -> FlashRank top-5 as run_map) and the best lexical matches
from the whole policy, so retrieval misses are visible.

    uv run python scripts/error_analysis.py --run e2e2 --policy nainital
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from score import findings_from_db  # noqa: E402

from regcomp.db import connect  # noqa: E402
from regcomp.evaluation import score  # noqa: E402
from regcomp.pipeline.rerank import rerank  # noqa: E402

SEED = 20260928
N = 30
RETRIEVE_K, TOP_K = 20, 5
STOP = set(
    [
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "to",
        "in",
        "for",
        "on",
        "by",
        "with",
        "as",
        "is",
        "are",
        "be",
        "shall",
        "may",
        "must",
        "bank",
        "banks",
        "its",
        "their",
        "such",
        "any",
        "all",
        "this",
        "that",
        "which",
        "from",
        "at",
        "into",
        "under",
        "where",
        "who",
        "whom",
        "will",
        "should",
        "have",
        "has",
        "not",
        "other",
        "than",
        "also",
        "each",
        "these",
        "those",
        "there",
        "been",
        "being",
        "per",
    ]
)


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z\-]{2,}", text.lower()) if w not in STOP}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default="nainital")
    args = ap.parse_args()
    run = Path("eval/runs") / args.run
    key = [
        json.loads(x)
        for x in Path(f"eval/answer_key_{args.policy}.jsonl").read_text("utf-8").splitlines()
    ]
    on_sheet = {
        v["mapping_id"]
        for v in json.loads((run / "adjudication_private.json").read_text("utf-8"))["rows"].values()
    }

    with connect() as conn:
        findings, _ = findings_from_db(conn)
        extras = score(key, findings, []).unkeyed
        pool = {f["id"]: f for f in extras if f["id"] not in on_sheet}
        pool = sorted(pool.values(), key=lambda f: (f["obligation_span"], f["action"] or ""))
        sample = random.Random(SEED).sample(pool, min(N, len(pool)))
        sample.sort(key=lambda f: f["obligation_span"])

        controls = {
            str(cid): (ref, obj, quote)
            for cid, ref, obj, quote in conn.execute(
                "SELECT id, control_ref, objective, source_span->>'quote' FROM control"
            ).fetchall()
        }
        cwords = {cid: words(q) for cid, (_, _, q) in controls.items()}

        lines = [
            f"# Error analysis worksheet: run `{args.run}`, {len(sample)} of {len(pool)} "
            "unkeyed gaps not on the blind sheet (seed "
            f"{SEED})",
            "",
            "Causes: (a) applicability, (b) granularity/reference, (c) retrieval, (d) judge, "
            "(e) real gap, (f) extraction.",
            "",
        ]
        rows = []
        for n, f in enumerate(sample, 1):
            m = conn.execute(
                "SELECT m.judges->0, o.modality, o.threshold->>'raw' FROM mapping m"
                " JOIN obligation o ON o.id = m.obligation_id WHERE m.id = %s",
                (f["id"],),
            ).fetchone()
            judge, modality, threshold = m
            hits = conn.execute(
                "SELECT ec.owner_id FROM embedding eo JOIN embedding ec"
                " ON ec.owner_kind = 'control' AND ec.model = eo.model"
                " WHERE eo.owner_kind = 'obligation' AND eo.owner_id = %s"
                " ORDER BY ec.vec <=> eo.vec LIMIT %s",
                (f["obligation_id"], RETRIEVE_K),
            ).fetchall()
            cands = [
                (str(h[0]), f"{controls[str(h[0])][1]}. {controls[str(h[0])][2]}") for h in hits
            ]
            top5 = [cid for cid, _ in rerank(f"{f['action']}. {f['quote']}", cands, TOP_K)]
            ow = words(f"{f['action']} {f['quote']}")
            lexical = sorted(
                (cid for cid in controls if cid not in top5),
                key=lambda cid: -len(ow & cwords[cid]),
            )[:3]
            lines += [
                f"## {n}. RBI {f['ref']} ({modality}) -> reported `{f['gap_type']}`",
                f"- **Obligation:** {f['action']}"
                + (f" (threshold: {threshold})" if threshold else ""),
                f"- **Regulation text:** {f['quote']}",
                f"- **Judge:** {judge.get('verdict')} / {judge.get('issue')}; cited "
                f"{f['control_ref'] or '-'}; rationale: {judge.get('rationale')}",
                "- **Judge's top-5:**",
                *[f"  - [{controls[c][0]}] {controls[c][2][:300]}" for c in top5],
                "- **Best lexical matches outside the top-5:**",
                *[
                    f"  - [{controls[c][0]}] ({len(ow & cwords[c])} shared terms) "
                    f"{controls[c][2][:300]}"
                    for c in lexical
                ],
                "",
            ]
            rows.append({"n": n, "mapping_id": f["id"], "ref": f["ref"], "gap_type": f["gap_type"]})
    (run / "error_analysis_worksheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run / "error_analysis_sample.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"worksheet: {run / 'error_analysis_worksheet.md'} ({len(sample)} extras)")


if __name__ == "__main__":
    main()
