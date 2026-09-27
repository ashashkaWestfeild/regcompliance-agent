"""Evaluation harness v1: score a pipeline run against the frozen answer key (counts only).

    uv run python scripts/score.py --run e2e1 --policy nainital

Writes to eval/runs/<run>/:
  report.md                  counts per row type + pipeline metrics, citing the key commit
  adjudication_sheet.csv     blind sheet for the user: a random sample of unkeyed gaps mixed
                             with an equal number of covered pairs, shuffled, no system verdicts
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
SAMPLE_GAPS = 25  # unkeyed gaps per adjudication sheet


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
        " m.judges, o.source_span->>'quote', c.source_span->>'quote', o.id, o.source_span,"
        " c.control_ref, o.action, o.threshold->>'raw'"
        " FROM mapping m JOIN obligation o ON o.id = m.obligation_id"
        " LEFT JOIN control c ON c.id = m.control_id"
        " LEFT JOIN gap g ON g.mapping_id = m.id"
    ).fetchall()
    findings = []
    for (
        mid,
        ref,
        verdict,
        gap_type,
        cspan,
        status,
        judges,
        oquote,
        cquote,
        oid,
        ospan,
        cref,
        action,
        threshold,
    ) in rows:
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
                "obligation_id": str(oid),
                "obligation_span": (ospan["char_start"], ospan["char_end"]),
                "control_ref": cref,
                "action": action,
                "threshold": threshold,
            }
        )
    policy_sha = conn.execute("SELECT sha256 FROM document WHERE kind = 'policy'").fetchone()[0]
    return findings, policy_sha


def closest_passage(conn, obligation_id: str) -> tuple[str, str]:
    """(control_ref, quote) of the policy control nearest to the obligation by embedding.
    Used where the judge cited no control, so a row never reveals a 'missing' verdict."""
    row = conn.execute(
        "SELECT c.control_ref, c.source_span->>'quote' FROM embedding eo"
        " JOIN embedding ec ON ec.owner_kind = 'control' AND ec.model = eo.model"
        " JOIN control c ON c.id = ec.owner_id"
        " WHERE eo.owner_kind = 'obligation' AND eo.owner_id = %s"
        " ORDER BY ec.vec <=> eo.vec LIMIT 1",
        (obligation_id,),
    ).fetchone()
    return row if row else ("", "")


def write_adjudication(conn, run: Path, run_name: str, findings, unkeyed):
    """Blind adjudication sheet: a seeded random sample of unkeyed gaps (a person can label ~50
    rows, not 350) + an equal number of pairs with no gap, shuffled. Blindness rules:
    - no verdict, gap type, confidence, rationale or status columns;
    - every row shows policy text: the judge's cited control, else the closest control by
      embedding, so "no policy text" can never mark a system-flagged row;
    - unflagged rows are mappings with no gap of any kind;
    - one row per distinct (regulation sentence, policy passage): several obligations extracted
      from one sentence and judged against the same passage would otherwise repeat a row
      (seen 27 Sep: one proviso appeared 5 times). A content pair that has any gap is never
      used as an unflagged row.
    The private file keeps stable identifiers (regulation and policy character spans + quotes),
    so the same 50 pairs can be re-judged by any later judge and scored against the labels."""

    def content(f):
        return (f["obligation_span"], f["control_span"] or (-1, -1))

    # Sort by content, not UUIDs, so a rebuilt database gives the same sample.
    gapped_content = {content(f) for f in findings if f["gap_type"]}
    flagged = sorted(unkeyed, key=lambda f: (content(f), f["action"] or ""))
    flagged = list({content(f): f for f in reversed(flagged)}.values())[::-1]
    clean = [f for f in findings if f["verdict"] == "covered" and content(f) not in gapped_content]
    clean = sorted(clean, key=lambda f: (content(f), f["action"] or ""))
    clean = list({content(f): f for f in reversed(clean)}.values())[::-1]
    rng = random.Random(SEED)
    sampled = rng.sample(flagged, min(len(flagged), SAMPLE_GAPS))
    fillers = rng.sample(clean, min(len(clean), len(sampled)))
    pairs = [(f, True) for f in sampled] + [(f, False) for f in fillers]
    rng.shuffle(pairs)

    private = {"run": run_name, "key_commit": key_commit(), "rows": {}}
    with (run / "adjudication_sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "#",
                "rbi_ref",
                "regulation_text",
                "obligation_being_checked (as extracted)",
                "policy_text (closest policy passage)",
                "YOUR_label (gap / no gap)",
                "YOUR_obligation_level (policy / sop_system / not_applicable)",
                "YOUR_notes",
            ]
        )
        for n, (f, is_gap) in enumerate(pairs, 1):
            if f["control_quote"]:
                cref, cquote, shown = f["control_ref"], f["control_quote"], "judge_cited"
            else:
                (cref, cquote), shown = closest_passage(conn, f["obligation_id"]), "nearest"
            duty = f["action"] + (f" ({f['threshold']})" if f["threshold"] else "")
            w.writerow([n, f["ref"], f["quote"], duty, cquote, "", "", ""])
            private["rows"][str(n)] = {
                "obligation_action": f["action"],
                "system_gap": is_gap,
                "system_verdict": f["verdict"],
                "system_gap_type": f["gap_type"],
                "mapping_id": f["id"],
                "obligation_ref": f["ref"],
                "obligation_span": f["obligation_span"],
                "obligation_quote": f["quote"],
                "policy_control_ref": cref,
                "policy_quote": cquote,
                "policy_text_source": shown,
            }
    (run / "adjudication_private.json").write_text(
        json.dumps(private, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return pairs, sampled


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
    ap.add_argument("--new-sheet", action="store_true", help="regenerate an existing sheet")
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

    print("\n".join(lines))
    sheet = run / "adjudication_sheet.csv"
    if sheet.exists() and not args.new_sheet:
        # A sheet may be in the user's hands (the gold set); never overwrite it silently.
        print(f"\nadjudication sheet kept: {sheet} exists (pass --new-sheet to regenerate)")
    else:
        with connect() as conn:
            pairs, sampled = write_adjudication(conn, run, args.run, findings, s.unkeyed)
        print(
            f"\nadjudication sheet: {len(pairs)} pairs ({len(sampled)} of {len(s.unkeyed)} "
            "unkeyed gaps, sampled, blind)"
        )
    digest = hashlib.sha256((run / "report.md").read_bytes()).hexdigest()[:12]
    print(f"report: {run / 'report.md'} ({digest})")


if __name__ == "__main__":
    main()
