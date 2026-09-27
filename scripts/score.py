"""Evaluation harness v1: score a pipeline run against the frozen answer key (counts only).

    uv run python scripts/score.py --run e2e1 --policy nainital

Writes to eval/runs/<run>/:
  report.md                  counts per row type + pipeline metrics, citing the key commit
  adjudication_sheet.csv     blind sheet for the user: unkeyed gaps mixed with an equal number
                             of covered pairs, shuffled, no system verdicts
  adjudication_private.json  which sheet rows were system gaps (do not open before labelling)
"""

import argparse
import csv
import hashlib
import json
import random
import subprocess
from pathlib import Path

from regcomp.db import connect
from regcomp.evaluation import score, summary

SEED = 20260927


def _detected(p: dict) -> str:
    return "yes" if p["detected"] else "near miss" if p["near_miss"] else "no"


def key_commit() -> str:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%h %cI", "--", "eval/answer_key_nainital.jsonl"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip() or "unknown"


def findings_from_db(conn) -> tuple[list[dict], str]:
    rows = conn.execute(
        "SELECT m.id, o.source_clause_ref, m.verdict, g.type, c.source_span, m.status,"
        " m.judges, o.source_span->>'quote', c.source_span->>'quote'"
        " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
        " LEFT JOIN control c ON c.id = m.control_id"
        " LEFT JOIN gap g ON g.mapping_id = m.id"
    ).fetchall()
    findings = []
    for mid, ref, verdict, gap_type, cspan, status, judges, oquote, cquote in rows:
        span = (cspan["char_start"], cspan["char_end"]) if cspan else None
        judge = judges[0] if judges else {}
        findings.append(
            {
                "id": str(mid),
                "ref": ref,
                "verdict": verdict,
                "gap_type": gap_type,
                "control_span": span,
                "status": status,
                "citation_ok": judge.get("citation_ok"),
                "confidence": judge.get("confidence"),
                "quote": oquote,
                "control_quote": cquote,
            }
        )
    policy_sha = conn.execute("SELECT sha256 FROM document WHERE kind = 'policy'").fetchone()[0]
    return findings, policy_sha


def cost(conn) -> list[str]:
    rows = conn.execute(
        "SELECT stage, count(*), sum(latency_ms), sum(eval_tokens) FROM llm_cache"
        " GROUP BY stage ORDER BY stage"
    ).fetchall()
    return [
        f"{stage}: {n} calls, {int(ms or 0) / 60000:.1f} model-min, {int(tok or 0)} output tokens"
        for stage, n, ms, tok in rows
    ]


def score_evidence(policy: str) -> list[str]:
    """Evidence key: planted operating failures must yield an operating_failure gap on the
    target obligation; evidence decoys must not."""
    path = Path(f"eval/answer_key_evidence_{policy}.jsonl")
    if not path.exists():
        return ["- no evidence key"]
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    with connect() as conn:
        tested = conn.execute(
            "SELECT DISTINCT o.source_clause_ref, t.result FROM control_test t"
            " JOIN mapping m ON m.id = t.mapping_id JOIN obligation o ON o.id = m.obligation_id"
            " WHERE t.kind = 'operating'"
        ).fetchall()
        failing = {
            r[0]
            for r in conn.execute(
                "SELECT o.source_clause_ref FROM gap g JOIN obligation o ON o.id = g.obligation_id"
                " WHERE g.type = 'operating_failure'"
            ).fetchall()
        }
    results = {ref: result for ref, result in tested}
    out = []
    for r in rows:
        refs = r["target_obligation_refs"]
        got = next((results[x] for x in refs if x in results), "not tested")
        has_gap = any(x in failing for x in refs)
        want_gap = r["kind"] == "evidence"
        ok = (got == r["expected_operating_result"]) and (has_gap == want_gap)
        out.append(
            f"- {r['mutation_id']} ({r['kind']}, {', '.join(refs)}): operating test "
            f"{got}, operating_failure gap {'yes' if has_gap else 'no'} -> "
            f"{'correct' if ok else 'WRONG'}"
        )
    correct = sum(line.endswith("correct") for line in out)
    return [f"- evidence rows correct {correct}/{len(out)}", *out]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default="nainital")
    args = ap.parse_args()
    run = Path("eval/runs") / args.run
    key = [
        json.loads(x)
        for x in Path(f"eval/answer_key_{args.policy}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    ext_o = json.loads((run / "obligations.json").read_text(encoding="utf-8"))
    ext_c = json.loads((run / "controls.json").read_text(encoding="utf-8"))

    with connect() as conn:
        findings, policy_sha = findings_from_db(conn)
        stage_cost = cost(conn)
    expected_sha = key[0]["mutated_text_sha256"]
    if policy_sha != expected_sha:
        raise SystemExit(
            f"policy text in DB ({policy_sha[:12]}) is not the keyed document "
            f"({expected_sha[:12]}); refusing to score"
        )

    s = score(key, findings, ext_c["flags"] + ext_o["flags"])
    evidence_lines = score_evidence(args.policy)
    gaps = [f for f in findings if f["gap_type"]]
    split = key[0].get("split", "?")
    lines = [
        f"# Evaluation report: run `{args.run}`, policy `{args.policy}` ({split} set)",
        "",
        f"Answer key: `eval/answer_key_{args.policy}.jsonl` at commit {key_commit()}; "
        f"policy text sha256 verified ({expected_sha[:12]}...).",
        "",
        "## Against the answer key (counts)",
        *[f"- {line}" for line in summary(s)],
        "",
        "| Row | Operator | Detected | Type accepted | Reported types |",
        "|---|---|---|---|---|",
        *[
            f"| {p['id']} | {p['operator']} | {_detected(p)} "
            f"| {'yes' if p['typed'] else 'no'} | {', '.join(p['reported']) or '-'} |"
            for p in s.planted
        ],
        "",
        *[
            f"- Decoy {d['id']}: {'FLAGGED (false positive)' if d['flagged'] else 'not flagged'}"
            for d in s.decoys
        ],
        *[f"- Injection {i['id']}: {'caught' if i['caught'] else 'MISSED'}" for i in s.injections],
        *[f"- Real finding {r['id']} ({r['rule']}): {r['outcome']}" for r in s.real],
        "",
        "## Evidence key (operating tests)",
        *evidence_lines,
        "",
        "## Pipeline metrics (counts)",
        f"- obligations extracted {len(ext_o['items'])}, rejected by citation gate "
        f"{len(ext_o['rejected'])}",
        f"- controls extracted {len(ext_c['items'])}, rejected by citation gate "
        f"{len(ext_c['rejected'])}",
        f"- mappings {len(findings)}: covered {sum(f['verdict'] == 'covered' for f in findings)}, "
        f"partial {sum(f['verdict'] == 'partial' for f in findings)}, missing "
        f"{sum(f['verdict'] == 'missing' for f in findings)}",
        f"- judge control citations verified {sum(bool(f['citation_ok']) for f in findings)}"
        f"/{len(findings)}; auto-accepted {sum(f['status'] == 'auto' for f in findings)}, "
        f"escalated {sum(f['status'] == 'escalated' for f in findings)}",
        f"- gaps reported {len(gaps)}; unkeyed (to blind adjudication) {len(s.unkeyed)}",
        "- model time by stage (cache totals): " + "; ".join(stage_cost),
        "",
        "Not yet measured: extraction precision/recall vs the user's labels, calibration, "
        "applicability.",
    ]
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Blind adjudication sheet: unkeyed gaps + an equal number of covered pairs, shuffled.
    rng = random.Random(SEED)
    covered = [f for f in findings if f["verdict"] == "covered"]
    fillers = rng.sample(covered, min(len(covered), len(s.unkeyed)))
    pairs = [(f, True) for f in s.unkeyed] + [(f, False) for f in fillers]
    rng.shuffle(pairs)
    with (run / "adjudication_sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "#",
                "rbi_ref",
                "obligation",
                "policy_text (best match found)",
                "YOUR_label (gap / no gap)",
                "YOUR_notes",
            ]
        )
        for n, (f, _) in enumerate(pairs, 1):
            w.writerow(
                [n, f["ref"], f["quote"], f["control_quote"] or "(no policy text found)", "", ""]
            )
    (run / "adjudication_private.json").write_text(
        json.dumps(
            {
                str(n): {"mapping_id": f["id"], "system_gap": is_gap}
                for n, (f, is_gap) in enumerate(pairs, 1)
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("\n".join(lines))
    print(f"\nadjudication sheet: {len(pairs)} pairs ({len(s.unkeyed)} unkeyed gaps, blind)")
    digest = hashlib.sha256((run / "report.md").read_bytes()).hexdigest()[:12]
    print(f"report: {run / 'report.md'} ({digest})")


if __name__ == "__main__":
    main()
