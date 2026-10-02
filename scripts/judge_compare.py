"""Judge comparison on a subset of dev units: the local judge against a hosted open-weights model.

Same obligations, same candidates, same prompt; only the model differs. The subset holds every
unit with an answer-key obligation, every unit with a gap in the loaded run, and a seeded sample
of units the local judge found fully covered (to see whether the other model invents gaps).
Dev set only; the texts are public (RBI Directions, the dev bank's published policy).

    uv run python scripts/judge_compare.py --model groq:openai/gpt-oss-120b --stop-after-min 24

Run it again to resume: every answer is cached. Needs the dev run loaded (run_map.py) and, for a
hosted model, its key in .env.
"""

import argparse
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

from regcomp.db import connect
from regcomp.llm import LLMError
from regcomp.pipeline.judge import judge_unit

TOP_K, RETRIEVE_K, SEED = 5, 20, 20261002
KEY = "eval/answer_key_nainital.jsonl"


def _same_text(a, b) -> bool:
    inside = min(a[1], b[1]) - max(a[0], b[0])
    return inside >= 0.5 * min(a[1] - a[0], b[1] - b[0])


def load_units(conn) -> dict[str, list[dict]]:
    rows = conn.execute(
        "SELECT o.id::text, o.key, o.source_clause_ref, o.modality::text, o.action,"
        " o.source_span->>'quote', o.threshold->>'raw', o.applicability->>'raw',"
        " o.applicability->>'level', m.verdict::text, m.judges->0->>'gap_type', g.tier"
        " FROM obligation o JOIN mapping m ON m.obligation_id = o.id"
        " LEFT JOIN gap g ON g.mapping_id = m.id AND g.type <> 'operating_failure'"
        " WHERE o.superseded_at IS NULL"
    ).fetchall()
    units = defaultdict(list)
    for r in rows:
        unit, _, n = r[1].removeprefix("OBL:").rpartition("#")
        units[unit].append(
            dict(
                zip(
                    ("id", "key", "ref", "modality", "action", "quote", "threshold", "applies_to",
                     "level", "local_verdict", "local_gap", "tier"),
                    r,
                    strict=True,
                ),
                n=int(n),
            )
        )  # fmt: skip
    return {u: sorted(obs, key=lambda o: o["n"]) for u, obs in units.items()}


def candidates(conn, obligation_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT c.id::text, c.source_span->>'quote', (c.source_span->>'char_start')::int,"
        " (c.source_span->>'char_end')::int FROM embedding e JOIN control c ON c.id = e.owner_id"
        " WHERE e.owner_kind = 'control' ORDER BY e.vec <=>"
        " (SELECT vec FROM embedding WHERE owner_id = %s::uuid AND owner_kind = 'obligation')"
        " LIMIT %s",
        (obligation_id, RETRIEVE_K),
    ).fetchall()
    kept: list[dict] = []
    for cid, quote, start, end in rows:
        if not any(_same_text((start, end), k["span"]) for k in kept):
            kept.append({"id": cid, "quote": quote, "span": (start, end)})
    return kept[:TOP_K]


def judge(conn, obs: list[dict], model: str | None) -> dict[str, dict]:
    """{obligation id: judged result} for one unit, with `model` (None = the local default)."""
    hits = {o["id"]: candidates(conn, o["id"]) for o in obs}
    cand = {c["id"]: c for o in obs for c in hits[o["id"]]}
    local = {cid: f"C{n}" for n, cid in enumerate(cand, 1)}
    payload = [
        {
            "id": f"O{n}",
            "modality": o["modality"],
            "quote": o["quote"],
            "threshold": o["threshold"],
            "applies_to": o["applies_to"],
            "candidates": [local[c["id"]] for c in hits[o["id"]]],
        }
        for n, o in enumerate(obs, 1)
    ]
    if model:
        os.environ["REGCOMP_MODEL_JUDGE"] = model
    else:
        os.environ.pop("REGCOMP_MODEL_JUDGE", None)
    judged = judge_unit(payload, {local[cid]: c for cid, c in cand.items()}, conn)
    back = {v: k for k, v in local.items()}
    out = {}
    for r in judged:
        o = obs[int(r["obligation"][1:]) - 1]
        r["span"] = cand[back[r["control"]]]["span"] if r.get("control") in back else None
        out[o["id"]] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="e.g. groq:openai/gpt-oss-120b")
    ap.add_argument("--covered-units", type=int, default=10)
    ap.add_argument("--stop-after-min", type=float, default=24)
    ap.add_argument("--out", type=Path, default=Path("eval/reports/judge_compare.json"))
    args = ap.parse_args()
    key = [json.loads(line) for line in Path(KEY).read_text(encoding="utf-8").splitlines()]
    keyed = {
        ref: row["mutation_id"]
        for row in key
        if row["kind"] in ("mutation", "decoy")
        for ref in row["target_obligation_refs"]
    }
    t0 = time.time()
    with connect(autocommit=True) as conn:
        units = load_units(conn)
        with_key = [u for u, obs in units.items() if any(o["ref"] in keyed for o in obs)]
        with_gap = [
            u for u, obs in units.items() if u not in with_key and any(o["local_gap"] for o in obs)
        ]
        clean = sorted(u for u in units if u not in with_key and u not in with_gap)
        sample = random.Random(SEED).sample(clean, min(args.covered_units, len(clean)))
        chosen = with_key + with_gap + sample
        print(
            f"units: {len(with_key)} with key rows, {len(with_gap)} with a local gap, "
            f"{len(sample)} sampled as fully covered = {len(chosen)} of {len(units)}",
            flush=True,
        )
        rows, failed = [], []
        for i, unit in enumerate(chosen, 1):
            if time.time() - t0 > args.stop_after_min * 60:
                print(f"time is up at {i - 1}/{len(chosen)} units; run again to resume", flush=True)
                return 3
            obs = units[unit]
            try:
                hosted = judge(conn, obs, args.model)
            except LLMError as e:
                failed.append(unit)
                print(f"[{time.strftime('%H:%M:%S')}] unit {unit} failed: {e}", flush=True)
                continue
            for o in obs:
                h = hosted.get(o["id"])
                rows.append(
                    {
                        "unit": unit,
                        "group": "key"
                        if unit in with_key
                        else "gap"
                        if unit in with_gap
                        else "covered",
                        "ref": o["ref"],
                        "key_row": keyed.get(o["ref"]),
                        "action": o["action"],
                        "level": o["level"],
                        "local_verdict": o["local_verdict"],
                        "local_gap": o["local_gap"],
                        "tier": o["tier"],
                        "hosted_verdict": h and h["verdict"],
                        "hosted_issue": h and h["issue"],
                        "hosted_gap": h and h["gap_type"],
                        "hosted_span": h and h["span"],
                        "hosted_rationale": h and h["rationale"],
                    }
                )
            if i % 5 == 0 or i == len(chosen):
                print(
                    f"[{time.strftime('%H:%M:%S')}] hosted judged {i}/{len(chosen)} units",
                    flush=True,
                )

    args.out.write_text(
        json.dumps({"model": args.model, "failed_units": failed, "rows": rows}, indent=1,
                   ensure_ascii=False),
        encoding="utf-8",
    )  # fmt: skip
    both = [r for r in rows if r["hosted_verdict"]]
    table = Counter((bool(r["local_gap"]), bool(r["hosted_gap"])) for r in both)
    print(f"\nobligations judged by both: {len(both)} (hosted failed on {len(failed)} units)")
    print(f"  gap for both {table[(True, True)]}; local only {table[(True, False)]}; "
          f"hosted only {table[(False, True)]}; neither {table[(False, False)]}")  # fmt: skip
    by_row = defaultdict(lambda: [False, False])
    for r in both:
        if r["key_row"]:
            by_row[r["key_row"]][0] |= bool(r["local_gap"])
            by_row[r["key_row"]][1] |= bool(r["hosted_gap"])
    print("  key rows with a gap raised at the obligation (local judge / hosted judge):")
    for row_id, (a, b) in sorted(by_row.items()):
        print(f"    {row_id}: {'yes' if a else 'no'} / {'yes' if b else 'no'}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
