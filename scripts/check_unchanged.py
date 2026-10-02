"""Result lock: prove that a change left every verdict, gap type, tier and score line as it was.

    uv run python scripts/check_unchanged.py --lock     # write eval/reports/lock_<policy>.json
    uv run python scripts/check_unchanged.py            # compare with it; exit 1 on a difference

Display and metadata changes must pass the comparison. A change that is meant to move results
(a new pipeline stage) reports the differences printed here and then takes a new lock.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

from score import _detected, findings_from_db, score_evidence

from regcomp.db import connect
from regcomp.evaluation import score, summary
from regcomp.lock import differences, digest

_SPAN = (
    "coalesce(({0}.source_span->>'char_start')::int, -1), "
    "coalesce(({0}.source_span->>'char_end')::int, -1)"
)


def snapshot(policy: str, run: str) -> dict:
    key = [
        json.loads(x)
        for x in Path(f"eval/answer_key_{policy}.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    flags = []
    for name in ("controls.json", "obligations.json"):
        flags += json.loads((Path("eval/runs") / run / name).read_text(encoding="utf-8"))["flags"]
    with connect() as conn:
        findings, policy_sha = findings_from_db(conn)
        obligations = conn.execute(
            f"SELECT o.source_clause_ref, {_SPAN.format('o')},"
            " coalesce(o.applicability->>'level', 'policy') FROM obligation o"
            " WHERE o.superseded_at IS NULL"
        ).fetchall()
        mappings = conn.execute(
            f"SELECT o.source_clause_ref, {_SPAN.format('o')}, m.verdict::text,"
            f" {_SPAN.format('c')}, m.status::text FROM mapping m"
            " JOIN obligation o ON o.id = m.obligation_id"
            " LEFT JOIN control c ON c.id = m.control_id WHERE m.superseded_at IS NULL"
        ).fetchall()
        gaps = conn.execute(
            f"SELECT o.source_clause_ref, {_SPAN.format('o')}, g.type::text, g.tier,"
            f" g.status::text, {_SPAN.format('c')} FROM gap g"
            " JOIN obligation o ON o.id = g.obligation_id"
            " LEFT JOIN control c ON c.id = g.control_id WHERE g.superseded_at IS NULL"
        ).fetchall()
    s = score(key, findings, flags)
    snap = {
        "policy": policy,
        "run": run,
        "policy_sha256": policy_sha,
        "summary": summary(s),
        "planted": [
            [p["id"], _detected(p), p["tier"] or "-", bool(p["typed"]), sorted(p["reported"])]
            for p in s.planted
        ],
        "decoys": [[d["id"], bool(d["flagged"]), d["tier"] or "-"] for d in s.decoys],
        "injections": [[i["id"], bool(i["caught"])] for i in s.injections],
        "real": [[r["id"], r["rule"], r["outcome"]] for r in s.real],
        "evidence": score_evidence(policy),
        "obligations": sorted(list(r) for r in obligations),
        "mappings": sorted(list(r) for r in mappings),
        "gaps": sorted(list(r) for r in gaps),
    }
    snap["sha256"] = digest(snap)
    return snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="nainital")
    ap.add_argument("--run", default="e2e11", help="run whose extraction flags are scored")
    ap.add_argument("--lock", action="store_true", help="write the snapshot instead of comparing")
    args = ap.parse_args()
    path = Path(f"eval/reports/lock_{args.policy}.json")
    now = snapshot(args.policy, args.run)
    counts = (
        f"{len(now['obligations'])} obligations, {len(now['mappings'])} mappings, "
        f"{len(now['gaps'])} gaps"
    )
    if args.lock:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
        now = {"locked_at": time.strftime("%Y-%m-%d %H:%M"), "code_commit": head, **now}
        path.write_text(
            json.dumps(now, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"locked: {path} ({counts}; {now['sha256'][:12]})")
        return
    if not path.exists():
        raise SystemExit(f"no lock at {path}; take one with --lock")
    old = json.loads(path.read_text(encoding="utf-8"))
    diff = differences(old, now)
    if diff:
        print(f"CHANGED against the lock of {old['locked_at']} ({old['sha256'][:12]}):")
        print("\n".join(diff))
        raise SystemExit(1)
    print(f"unchanged against the lock of {old['locked_at']}: {counts}; {now['sha256'][:12]}")


if __name__ == "__main__":
    main()
