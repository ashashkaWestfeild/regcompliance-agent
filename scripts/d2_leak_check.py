"""Leak check for the D2 detector (PROBLEMS_LOG P-055, P-056): no South Indian Bank text outside
the test set itself.

    uv run python scripts/d2_leak_check.py > eval/reports/d2_leak_check.txt

Searched: every file changed since eval-freeze-2026-10-03 (git diff --name-only against the tag,
plus uncommitted and untracked files), text files only. For every edit of the third bank's key
it takes the find and replace strings and the whole edited sentence, before and after, and
looks for (a) each string and (b) any run of 8 consecutive words from them; matching ignores
case, punctuation and spacing. Matches in the test material itself (the key, the mutated policy,
the draw, the parsed policy) are counted as expected. Every other match is reported with where
else its words occur (RBI's Directions or a development bank's policy); a match with no other
source is a leak and sets exit code 1.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.ingest.rbi_html import parse_file as parse_regulation

TAG = "eval-freeze-2026-10-03"
REGULATION = "data/raw/rbi/kycdir_v3_20260918.html"
DEVELOPMENT = ["nainital", "nainital2", "centralbank", "dhanlaxmi"]
SIB_SHA = "df1d336b56a4b4b9ef87f0e7d039be80181a18860103cc821091fb92aef7219e"
# The held-out test material: South Indian Bank text is expected here and nowhere else.
TEST_SET = re.compile(rf"southindianbank|{SIB_SHA}")
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
    """Text files changed since the tag, committed or not, plus untracked files."""
    names = set()
    for cmd in (
        ["git", "diff", "--name-only", TAG],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        names |= set(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.split())
    out = []
    for name in sorted(names):
        p = Path(name)
        if not p.is_file():
            continue
        try:
            p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary (the policy PDF)
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
    # Text a match may legitimately come from: RBI's Directions and the development banks.
    sources = {"RBI Directions": parse_regulation(REGULATION).text}
    for bank in DEVELOPMENT:
        sources[f"{bank} policy"] = parse_policy_items(
            json.loads(Path(f"data/mutated/{bank}.items.json").read_text("utf-8"))
        ).text
    source_words = {name: " ".join(words(text)) for name, text in sources.items()}

    def origin(run: str) -> str:
        found = [name for name, flat in source_words.items() if run in flat]
        return "also in " + ", ".join(found) if found else "NO OTHER SOURCE: a leak"

    hits, expected, leaks = 0, 0, 0
    for path in searched:
        in_test_set = bool(TEST_SET.search(str(path).replace("\\", "/")))
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
                if in_test_set:
                    expected += 1
                    continue
                hits += 1
                why = origin(" ".join(tw))
                leaks += why.startswith("NO OTHER")
                print(f"MATCH {path}: whole {kind} of {mid}: {text[:100]} [{why}]")
                continue
            for i in range(len(tw) - RUN + 1):
                run = " ".join(tw[i : i + RUN])
                at = joined.find(run)
                if at >= 0:
                    if in_test_set:
                        expected += 1
                        break
                    line = flat[len(joined[:at].split())][0]
                    hits += 1
                    why = origin(run)
                    leaks += why.startswith("NO OTHER")
                    print(f"MATCH {path}:{line}: {RUN}-word run of {mid} ({kind}): '{run}' [{why}]")
                    break
    print(f"expected matches inside the test material: {expected}")
    print(f"matches outside the test material: {hits}; with no other source (leaks): {leaks}")
    sys.exit(1 if leaks else 0)


if __name__ == "__main__":
    main()
