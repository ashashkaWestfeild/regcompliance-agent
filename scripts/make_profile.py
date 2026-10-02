"""Build a bank's profile from its own published policy (no model, no judgement).

    uv run python scripts/make_profile.py --policy nainital
    uv run python scripts/make_profile.py --policy centralbank --held-out

Reads the policy as published (not the planted-gap copy) and lists every value of
data/applicability_vocab.yaml that the policy mentions, with the clause and the words around the
first mention as evidence. `not_offered` starts empty: only a person adds a stated absence, with
its source. A profile is committed before the bank is run and is not edited after its results
are seen.
"""

import argparse
import hashlib
from pathlib import Path

import yaml

from regcomp.applicability import PROFILES, build_profile, load_vocab
from regcomp.ingest.pdf_docling import docling_items, parse_policy_items
from regcomp.policies import SOURCES, policy

HEADER = """\
# Bank profile, built by scripts/make_profile.py from the bank's published policy
# ({file}, sha256 {sha}).
# has: a value is listed because the policy itself deals with it; `where` is the clause and
#   `evidence` the words around the first mention. Mention in the policy is the basis: the
#   profile says what the policy covers, not what the bank sells.
# not_offered: stated absences, added by a person with a source (basis). Empty unless stated.
#   Each entry: {{attribute, value, basis, note}}. basis "assumption" never excludes anything.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--held-out", action="store_true")
    args = ap.parse_args()
    policy(args.policy, held_out=args.held_out)  # the guard on the held-out banks
    sources = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["policies"]
    src = next(p for p in sources if p["id"] == args.policy)
    doc = parse_policy_items(docling_items(src["file"]))

    def ref_at(pos: int) -> str:
        inside = [c for c in doc.clauses if c.char_start <= pos < c.char_end]
        return min(inside, key=lambda c: c.char_end - c.char_start).ref if inside else "preamble"

    profile = build_profile(src["bank"], src["bank_type"], doc.text, ref_at, load_vocab())
    out = PROFILES / f"{args.policy}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(Path(src["file"]).read_bytes()).hexdigest()
    body = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True, width=110)
    out.write_text(
        HEADER.format(file=src["file"], sha=sha[:12]) + body, encoding="utf-8", newline="\n"
    )
    counts = ", ".join(f"{a} {len(v)}" for a, v in profile["has"].items())
    print(f"{out}: {counts}; not_offered 0")


if __name__ == "__main__":
    main()
