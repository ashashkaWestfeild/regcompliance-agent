"""Redundant-coverage check for planted gaps (answer-key integrity).

A deleted, narrowed or weakened control is only a real gap if no *other* passage in the altered
policy still satisfies the obligation. For every such mutation this lists:
  - lexical hits: passages matching the obligation's key wording (from the spec's `check`), and
  - semantic neighbours: the policy clauses most similar to the RBI clause (bge-m3 via Ollama),
excluding the mutated locations themselves. A human reviews the output; nothing is auto-decided.

    uv run python scripts/coverage_check.py nainital
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

from regcomp.change.diff import own_text
from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.ingest.rbi_html import parse_file as parse_regulation

REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"
CHECK_OPERATORS = {
    "delete_control",
    "narrow_scope",
    "weaken_threshold",
    "make_stale",
    "weaken_modality",
}
OLLAMA = "http://localhost:11434/api/embed"
TOP_K = 6


def embed(texts: list[str]) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 64):
        body = json.dumps({"model": "bge-m3", "input": texts[i : i + 64]}).encode()
        req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
        out += json.load(urllib.request.urlopen(req, timeout=600))["embeddings"]
    return out


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb)


def main(policy: str) -> None:
    spec = yaml.safe_load(Path(f"data/mutations/{policy}.yaml").read_text(encoding="utf-8"))
    items = json.loads(Path(f"data/mutated/{policy}.items.json").read_text(encoding="utf-8"))
    key_lines = Path(f"eval/answer_key_{policy}.jsonl").read_text(encoding="utf-8").splitlines()
    key = {r["mutation_id"]: r for r in map(json.loads, key_lines)}
    doc = parse_policy_items(items)
    reg = parse_regulation(REGULATION)
    reg_own = {c.ref: own_text(c, reg) for c in reg.clauses}

    leaves = [c for c in doc.clauses if not any(k.parent_ref == c.ref for k in doc.clauses)]
    leaf_text = [own_text(c, doc)[:2000] for c in leaves]
    leaf_vec = embed(leaf_text)

    for m in spec:
        if m["operator"] not in CHECK_OPERATORS:
            continue
        mutated_refs = {loc["policy_clause_ref"] for loc in key[m["id"]]["locations"]}
        print(f"\n=== {m['id']} {m['operator']} -> RBI {m['target_obligation_refs']}")
        for pattern in m.get("check", []):
            for hit in re.finditer(pattern, doc.text, re.IGNORECASE):
                ref = max(
                    (c for c in doc.clauses if c.char_start <= hit.start() < c.char_end),
                    key=lambda c: c.depth,
                    default=None,
                )
                where = ref.ref if ref else "?"
                mark = "  (mutated location)" if where in mutated_refs else ""
                snippet = doc.text[max(0, hit.start() - 90) : hit.end() + 90].replace("\n", " ")
                print(f"  lexical [{where}]{mark}: ...{snippet}...")
        target = " ".join(reg_own[r] for r in m["target_obligation_refs"])
        tvec = embed([target])[0]
        scored = sorted(
            ((cosine(tvec, v), c, t) for v, c, t in zip(leaf_vec, leaves, leaf_text, strict=True)),
            key=lambda x: -x[0],
        )
        shown = 0
        for score, c, t in scored:
            if c.ref in mutated_refs:
                continue
            print(f"  semantic {score:.3f} [{c.ref}]: {t[:220]}")
            shown += 1
            if shown == TOP_K:
                break


if __name__ == "__main__":
    main(sys.argv[1])
