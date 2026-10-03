"""Error analysis for the D2 attempt: trace each held-out miss through the frozen v1 run.

    uv run python scripts/d2_trace_misses.py --runs ../regcompliance-freeze/eval/runs

Read-only. Uses the frozen run files of eval-freeze-2026-10-03 (obligations, extracted controls,
gaps), the answer keys, the mutated policies and the model-call cache (judge prompts and answers,
read from DATABASE_URL; nothing is written). For each missed planted gap it prints, stage by
stage: (1) extraction of the RBI obligation, (2) whether the mutated location lies in an
extracted control, (3) the candidates the judge saw, from the cached prompt, (4) the judge's
answer for that obligation, and (5) the gaps the run raised at that obligation.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from regcomp.db import connect
from regcomp.ingest.pdf_docling import parse_policy_items

MISSES = {
    "centralbank": ["C04", "C05", "C06", "C07"],
    "dhanlaxmi": ["L01", "L02", "L03", "L04"],
}
RUN = {"centralbank": "ho_centralbank", "dhanlaxmi": "ho_dhanlaxmi"}


def norm(s: str) -> str:
    return " ".join(s.split())


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", norm(s).lower()))


def parse_prompt(request: dict) -> tuple[dict, dict]:
    """Obligations and candidates, by their prompt-local ids, from a cached judge prompt."""
    user = next(m["content"] for m in request["messages"] if m["role"] == "user")
    return dict(re.findall(r"\[(O\d+)\] (.*)", user)), dict(re.findall(r"\[(C\d+)\] (.*)", user))


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def related(o: dict, refs: list[str], want: set[str]) -> bool:
    """An extracted obligation filed under the target paragraph (or its parent) whose wording
    shares at least half of the target obligation's words."""
    cr = o["clause_ref"]
    if not any(r == cr or r.startswith(cr + "(") or cr.startswith(r + "(") for r in refs):
        return False
    have = words(o["quote"])
    return len(want & have) >= 0.5 * min(len(want), len(have) or 1)


def trace(bank: str, mid: str, k: dict, run: Path, cache: list) -> None:
    text = parse_policy_items(
        json.loads(Path(f"data/mutated/{bank}.items.json").read_text("utf-8"))
    ).text
    flat = norm(text)
    obligations = json.loads((run / "obligations.json").read_text("utf-8"))["items"]
    controls = json.loads((run / "controls.json").read_text("utf-8"))["items"]
    with (run / "gaps.csv").open(encoding="utf-8") as fh:
        gaps = list(csv.DictReader(fh))
    refs = k["target_obligation_refs"]
    print(f"\n{'=' * 100}\n{bank} {mid} {k['operator']} -> RBI {refs}\n  note: {k['note']}")
    near_texts = []
    for loc in k["locations"]:
        span = (loc["char_start"], loc["char_end"])
        near_texts.append(norm(text[max(0, span[0] - 300) : span[1] + 300]))
        print(
            f"  location {loc['policy_clause_ref']} {span}: "
            f"...{norm(text[max(0, span[0] - 120) : span[1] + 120])[:360]}..."
        )
        if loc.get("deleted_text"):
            print(f"  deleted: {norm(loc['deleted_text'])[:300]}")
        hit = [
            c
            for c in controls
            if overlaps((c["char_start"], c["char_end"]), span)
            or (span[0] == span[1] and c["char_start"] <= span[0] <= c["char_end"])
        ]
        print(f"  [stage 2] extracted controls at the location: {len(hit)}")
        for c in hit[:2]:
            print(f"     - {c['clause_ref']}: {norm(c['quote'])[:200]}")
    want = words(" ".join(k.get("target_obligation_text", {}).values()))
    mine = [(i, o) for i, o in enumerate(obligations) if related(o, refs, want)]
    print(f"  [stage 1] obligations extracted for {refs}: {len(mine)}")
    for i, o in mine:
        head = norm(o["quote"])[:70]
        print(f"\n  O{i + 1} [{o['clause_ref']}] ({o['modality']}) {norm(o['quote'])[:240]}")
        prompts = []
        for req, resp in cache:
            obs, cands = parse_prompt(req)
            if not any(head in norm(t) for t in obs.values()):
                continue
            if not cands or not all(norm(c)[:60] in flat for c in list(cands.values())[:3]):
                continue
            prompts.append((obs, cands, resp))
        print(f"   [stage 3] cached judge prompts on {bank}: {len(prompts)}")
        if not prompts:
            continue
        obs, cands, resp = prompts[-1]
        for cid, ctext in cands.items():
            mark = (
                "  <== at/near the mutated location"
                if any(norm(ctext)[:50] in near for near in near_texts)
                else ""
            )
            print(f"     {cid} {norm(ctext)[:200]}{mark}")
        local = next(lid for lid, t in obs.items() if head in norm(t))
        answer = json.loads(resp) if isinstance(resp, str) else resp
        res = next((r for r in answer.get("results", []) if r.get("obligation") == local), None)
        if res:
            print(
                f"   [stage 4] judge ({local}): {res['verdict']} / issue {res['issue']} / best "
                f"{res['control']} / conf {res['confidence']}: {res['rationale']}"
            )
    at_ref = [g for g in gaps if g["regulation_ref"] in refs]
    print(f"\n  [stage 5] gaps raised at {refs} in the frozen run: {len(at_ref)}")
    for g in at_ref:
        print(f"     {g['verdict']} / {g['gap_type']}: {g['rationale'][:200]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    with connect(autocommit=True) as conn:
        cache = [
            (json.loads(req) if isinstance(req, str) else req, resp)
            for req, resp in conn.execute(
                "SELECT request, response FROM llm_cache WHERE stage = 'judge'"
                " AND model = 'qwen3:8b'"
            ).fetchall()
        ]
    for bank, rows in MISSES.items():
        with Path(f"eval/answer_key_{bank}.jsonl").open(encoding="utf-8") as fh:
            key = {r["mutation_id"]: r for r in map(json.loads, fh)}
        for mid in rows:
            trace(bank, mid, key[mid], args.runs / RUN[bank], cache)


if __name__ == "__main__":
    main()
