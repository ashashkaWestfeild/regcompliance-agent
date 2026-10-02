"""Applicability stage: decide, for every obligation, whether it applies to this bank.

    uv run python scripts/run_applicability.py --policy nainital           # decide, store, report
    uv run python scripts/run_applicability.py --policy nainital --apply   # and act on "no"

Runs after the level stage (and after run_verify when --apply is used). Decisions are stored
with their reason, who decided (rule or model), and the profile attribute relied on. Without
--apply nothing else changes (shadow mode). With --apply a gap on an obligation that does not
apply leaves both tiers (tier not_applicable) and stays visible with its reason; "conditional"
is a note on the finding and moves nothing. The stage is repeatable: it first restores what an
earlier run changed.
"""

import argparse
import hashlib
import sys
import time
from collections import Counter, defaultdict

from psycopg.types.json import Jsonb

from regcomp.applicability import (
    PROFILES,
    classify_conditions,
    condition_of,
    decide,
    load_profile,
    load_vocab,
)
from regcomp.db import connect
from regcomp.policies import policy

FIELDS = ("answer", "reason", "decided_by", "attribute", "value", "basis", "matched_in")


def undo(conn) -> None:
    conn.execute(
        "UPDATE gap SET tier = evidence->'applicability'->>'tier_before',"
        " evidence = nullif(evidence - 'applicability', '{}'::jsonb)"
        " WHERE evidence ? 'applicability'"
    )


def store(conn, profile_id: str, sha: str, decisions: dict[str, dict]) -> int:
    current = {
        str(r[0]): (r[1], *r[2:])
        for r in conn.execute(
            "SELECT obligation_id, profile_sha256, " + ", ".join(FIELDS) + " FROM"
            " applicability_decision WHERE profile = %s AND superseded_at IS NULL",
            (profile_id,),
        ).fetchall()
    }
    written = 0
    for oid, d in decisions.items():
        row = (sha, *[d[f] for f in FIELDS])
        if current.get(oid) == row:
            continue
        conn.execute(
            "UPDATE applicability_decision SET superseded_at = now()"
            " WHERE obligation_id = %s AND profile = %s AND superseded_at IS NULL",
            (oid, profile_id),
        )
        conn.execute(
            "INSERT INTO applicability_decision (obligation_id, profile, profile_sha256, "
            + ", ".join(FIELDS)
            + ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (oid, profile_id, *row),
        )
        written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="nainital")
    ap.add_argument("--profile", help="profile id, to override the one in sources.yaml")
    ap.add_argument("--held-out", action="store_true")
    ap.add_argument("--apply", action="store_true", help="take 'no' obligations out of the tiers")
    ap.add_argument(
        "--model",
        action="store_true",
        help="ask a model whether an unmatched condition is a bank attribute (off by default)",
    )
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pol = policy(args.policy, held_out=args.held_out)  # the guard on the held-out banks
    profile_id = args.profile or pol.profile
    profile, vocab = load_profile(profile_id), load_vocab()
    sha = hashlib.sha256((PROFILES / f"{profile_id}.yaml").read_bytes()).hexdigest()

    with connect(autocommit=True) as conn:
        undo(conn)
        rows = conn.execute(
            "SELECT id::text, source_clause_ref, applicability->>'raw', source_span->>'quote'"
            " FROM obligation WHERE superseded_at IS NULL"
        ).fetchall()
        obligations = {r[0]: {"ref": r[1], "applies_to": r[2], "quote": r[3]} for r in rows}
        first = {oid: decide(o, profile, vocab) for oid, o in obligations.items()}
        open_conditions = [
            condition_of(obligations[oid])
            for oid, d in first.items()
            if condition_of(obligations[oid]) and not d["matched_in"]
        ]
        kinds = {}
        if open_conditions and args.model:
            started = time.time()
            kinds = classify_conditions(
                open_conditions,
                conn,
                progress=lambda done, total: print(
                    f"[{time.strftime('%H:%M:%S')}] conditions classified {done}/{total}",
                    flush=True,
                ),
            )
            print(f"model pass: {len(kinds)} conditions in {time.time() - started:.0f}s")
        decisions = {oid: decide(o, profile, vocab, kinds) for oid, o in obligations.items()}
        with conn.transaction():
            written = store(conn, profile_id, sha, decisions)

        gaps = conn.execute(
            "SELECT g.id::text, g.obligation_id::text, g.tier, g.type::text FROM gap g"
            " WHERE g.status = 'open' AND g.superseded_at IS NULL"
        ).fetchall()
        moved = 0
        if args.apply:
            with conn.transaction():
                for gid, oid, tier, _ in gaps:
                    d = decisions.get(oid)
                    if d and d["answer"] == "no":
                        note = {**{f: d[f] for f in FIELDS}, "tier_before": tier}
                        conn.execute(
                            "UPDATE gap SET tier = 'not_applicable', evidence ="
                            " coalesce(evidence, '{}'::jsonb) || %s WHERE id = %s",
                            (Jsonb({"applicability": note}), gid),
                        )
                        moved += 1

    n = len(decisions)
    by = Counter((d["answer"], d["decided_by"]) for d in decisions.values())
    print(f"\napplicability of {n} obligations to {profile['bank']} (profile {profile_id}):")
    for answer in ("yes", "no", "conditional"):
        rule, model = by[(answer, "rule")], by[(answer, "model")]
        print(f"- {answer}: {rule + model} (by rule {rule}, by model {model})")
    unmatched = len(open_conditions)
    print(
        f"- conditions that name no bank attribute from the vocabulary: {unmatched} obligations, "
        f"{len({c.lower() for c in open_conditions})} distinct"
    )
    print(f"- decisions written or changed: {written}")

    for answer in ("no", "conditional"):
        groups = defaultdict(list)
        for oid, d in decisions.items():
            if d["answer"] == answer:
                groups[(d["decided_by"], d["attribute"], d["value"])].append(
                    obligations[oid]["ref"]
                )
        if groups:
            print(f"\n{answer}, by what decided it:")
        for (who, attribute, value), refs in sorted(groups.items(), key=lambda g: -len(g[1])):
            name = f"{attribute}: {value}" if value else f"{attribute}"
            listed = ", ".join(sorted(set(refs))[:8])
            print(f"- {len(refs)} | {who} | {name} | RBI {listed}")

    on = Counter((decisions[oid]["answer"], tier) for _, oid, tier, _ in gaps if oid in decisions)
    print("\nopen gaps on these obligations (answer, tier before this stage): count")
    for (answer, tier), count in sorted(on.items()):
        print(f"- {answer}, {tier}: {count}")
    mode = f"applied: {moved} gap(s) moved to not_applicable" if args.apply else "shadow mode"
    print(f"\n{mode}; 'conditional' is a note and moves nothing")


if __name__ == "__main__":
    main()
