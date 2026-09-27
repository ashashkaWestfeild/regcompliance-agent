"""Seeded random draw of mutation targets for a new policy (bias control).

Added 27 Sep 2026 for the third bank (Dhanlaxmi, held-out test2). Its answer key is authored
after the author has seen system behaviour on the dev set, so the author must not choose which
passages to mutate. This script decides, from a fixed seed:
  - which theme each operator slot gets (a seeded permutation of the taxonomy themes);
  - which policy passage each slot targets (a seeded choice among passages matching the theme);
  - which passages get the decoys and the injection.
The author then only writes the find/replace text for the drawn passages (still hand-written,
no LLM), and records any slot that is infeasible and moved to the next drawn candidate.

    uv run python scripts/draw_mutation_targets.py dhanlaxmi --seed 20260927
"""

import argparse
import json
import random
import re
from pathlib import Path

import yaml

from regcomp.ingest.pdf_docling import docling_items

THEMES = {  # generic patterns from docs/mutation_taxonomy.md (themes table)
    "periodic_rekyc": r"periodic(al)? updation|re-?kyc",
    "risk_categorization": r"risk categori[sz]ation",
    "beneficial_owner": r"beneficial owner",
    "ckycr_upload": r"\bCKYCR\b",
    "fiu_reporting": r"principal officer|FIU-IND",
    "ongoing_monitoring": r"on-?going (due diligence|monitoring)|intensified monitoring|money mule",
}
OPERATORS = [  # 7 gap slots: every operator once, plus a second weaken_threshold (as test set 1)
    "delete_control",
    "weaken_threshold",
    "narrow_scope",
    "contradict",
    "make_stale",
    "strip_design",
    "weaken_threshold",
]
NEEDS_NUMBER = {"weaken_threshold", "make_stale"}
DECOYS = ["rephrase", "reorder", "stricter_threshold"]
NUMBER = re.compile(
    r"\b(\d+|one|two|three|six|eight|ten|twelve)\b[^.]{0,20}"
    r"(day|month|year|per ?cent|%|lakh)",
    re.I,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("policy")
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    src = next(
        p
        for p in yaml.safe_load(Path("data/sources.yaml").read_text("utf-8"))["policies"]
        if p["id"] == args.policy
    )
    items = [
        (i, it["text"])
        for i, it in enumerate(docling_items(src["file"]))
        if it.get("label") in {"text", "list_item", "paragraph"} and len(it["text"]) >= 60
    ]
    rng = random.Random(args.seed)
    themes = list(THEMES)
    rng.shuffle(themes)
    used: set[int] = set()
    slots = []
    for n, op in enumerate(OPERATORS):
        drawn = themes[n % len(themes)]
        # If the drawn theme has no feasible passage for this operator (e.g. nothing numeric to
        # weaken), take the next theme in the seeded order: a fixed rule, not the author's pick.
        for step in range(len(themes)):
            theme = themes[(n + step) % len(themes)]
            pool = [
                (i, t)
                for i, t in items
                if i not in used
                and re.search(THEMES[theme], t, re.I)
                and (op not in NEEDS_NUMBER or NUMBER.search(t))
            ]
            if pool:
                break
        ranked = rng.sample(pool, len(pool))  # a full seeded order: fallbacks are pre-decided
        if ranked:
            used.add(ranked[0][0])
        slots.append(
            {
                "slot": n + 1,
                "operator": op,
                "theme": theme,
                "drawn_theme": drawn,
                "candidates_in_draw_order": [{"item": i, "text": t[:240]} for i, t in ranked[:5]],
            }
        )
    rest = [
        (i, t)
        for i, t in items
        if i not in used and any(re.search(p, t, re.I) for p in THEMES.values())
    ]
    decoys = [
        {
            "decoy": kind,
            "candidates_in_draw_order": [
                {"item": i, "text": t[:240]} for i, t in rng.sample(rest, min(5, len(rest)))
            ],
        }
        for kind in DECOYS
    ]
    injection_item = rng.choice(items)
    out = {
        "policy": args.policy,
        "policy_sha256": src["sha256"],
        "seed": args.seed,
        "theme_order": themes,
        "slots": slots,
        "decoys": decoys,
        "injection_after_item": {"item": injection_item[0], "text": injection_item[1][:240]},
        "rule": "use the first feasible candidate of each slot; log every skip and why",
    }
    path = Path(f"data/mutations/{args.policy}_draw.json")
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"draw written: {path} (seed {args.seed}); theme order {themes}")
    for s in slots:
        print(
            f"  slot {s['slot']}: {s['operator']:17} {s['theme']:20} "
            f"{len(s['candidates_in_draw_order'])} candidates"
        )


if __name__ == "__main__":
    main()
