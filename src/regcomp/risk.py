"""Risk ranking of gaps by a fixed rubric (data/risk_rubric.yaml). No model is involved.

A gap's risk comes from two things a reviewer can check by hand:
- the subject of the obligation (inherent risk), matched from its text and its heading;
- the kind of gap (how much of the obligation is left open).
Every score carries the reasons that produced it, so the ranking can be explained row by row.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

RUBRIC = Path("data/risk_rubric.yaml")
LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class Risk:
    inherent: str
    residual: str
    priority: float  # 0..1, highest first
    reasons: list[str]


@lru_cache(maxsize=2)
def rubric(path: str = str(RUBRIC)) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for theme in data["themes"]:
        theme["regex"] = re.compile(theme["pattern"], re.IGNORECASE)
    return data


def assess(obligation_text: str, heading: str, gap_type: str, path: str = str(RUBRIC)) -> Risk:
    r = rubric(path)
    theme = next(
        (
            t
            for where in (obligation_text or "", heading or "")  # the text first, then its heading
            for t in r["themes"]
            if t["regex"].search(where)
        ),
        None,
    )
    inherent = theme["level"] if theme else r["default"]
    factor = r["gap_factors"].get(gap_type, r["gap_factors"]["unspecified"])
    product = LEVELS[inherent] * factor
    residual = next(level for level, bound in r["residual_bounds"].items() if product >= bound)
    return Risk(
        inherent,
        residual,
        round(product / 4, 3),
        [
            f"subject: {theme['name'] if theme else 'no theme matched'} -> inherent {inherent}",
            f"gap type {gap_type}: {factor:.0%} of the obligation left open -> residual {residual}",
        ],
    )
