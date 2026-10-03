"""Leak check for the D2 detector (PROBLEMS_LOG P-055): no South Indian Bank text in the detector,
its tests or its prompts.

    uv run python scripts/d2_leak_check.py > eval/reports/d2_leak_check.txt

For every edit of the third bank's key (data/mutations/southindianbank.yaml) it takes the find
and replace strings and the whole edited sentence, before and after, and searches the files below
for (a) each string and (b) any run of 8 consecutive words from the edited sentences. Matching
ignores case, punctuation and spacing. Every match is reported with its file, line and the edit
it comes from; the exit code is 1 if anything matches.
"""

import json
import re
import sys
from pathlib import Path

import yaml

from regcomp.ingest.pdf_docling import parse_policy_items

SEARCHED = [
    "src/regcomp/pipeline/detect.py",
    "tests/test_detect.py",
    "src/regcomp/prompts",  # any prompt files, if the detector adds one
    "scripts/run_detect.py",
]
RUN = 8  # consecutive words


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def sentence_around(text: str, needle: str) -> str:
    """The sentence of `text` that contains `needle` (whitespace-normalised)."""
    flat = " ".join(text.split())
    at = flat.find(" ".join(needle.split()))
    if at < 0:
        return ""
    start = max(flat.rfind(". ", 0, at), flat.rfind("; ", 0, at)) + 1
    ends = [e for e in (flat.find(". ", at), flat.find("; ", at)) if e >= 0]
    return flat[start : (min(ends) + 1 if ends else len(flat))].strip()


def files() -> list[Path]:
    out = []
    for name in SEARCHED:
        p = Path(name)
        if p.is_dir():
            out += sorted(q for q in p.rglob("*") if q.is_file())
        elif p.exists():
            out.append(p)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    spec = yaml.safe_load(Path("data/mutations/southindianbank.yaml").read_text("utf-8"))
    mutated = parse_policy_items(
        json.loads(Path("data/mutated/southindianbank.items.json").read_text("utf-8"))
    ).text
    targets = []  # (edit id, kind, text)
    for m in spec:
        for e in m.get("edits", []):
            for kind in ("find", "replace"):
                if e.get(kind):
                    targets.append((m["id"], kind, e[kind]))
            if e.get("replace"):
                targets.append((m["id"], "edited sentence", sentence_around(mutated, e["replace"])))
            targets.append((m["id"], "original sentence", e["find"]))
    searched = files()
    print(f"searched {len(searched)} files: " + ", ".join(str(p) for p in searched))
    print(f"{len(targets)} strings from {len(spec)} key rows; runs of {RUN} words")
    hits = 0
    for path in searched:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        line_words = [words(line) for line in lines]
        flat = [(n, w) for n, ws in enumerate(line_words, 1) for w in ws]
        seq = [w for _, w in flat]
        joined = " ".join(seq)
        for mid, kind, text in targets:
            tw = words(text)
            if not tw:
                continue
            if " ".join(tw) in joined:
                hits += 1
                print(f"MATCH {path}: whole {kind} of {mid}: {text[:120]}")
                continue
            for i in range(len(tw) - RUN + 1):
                run = " ".join(tw[i : i + RUN])
                at = joined.find(run)
                if at >= 0:
                    line = flat[len(joined[:at].split())][0]
                    hits += 1
                    print(f"MATCH {path}:{line}: {RUN}-word run of {mid} ({kind}): '{run}'")
                    break
    print(f"result: {hits} match(es)")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
