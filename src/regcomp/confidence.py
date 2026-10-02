"""Confidence note for a finding: which checks support it, and how such findings did on dev.

The judge's own 0-1 "confidence" is not shown. Measured on the development bank (2 Oct 2026) it
does not track correctness: most verdicts sit at 0.95 or 1.0 whether right or wrong, and "missing"
verdicts get low values because the prompt never says what the number is confidence in. A note is
built instead from signals that code can verify, and each combination carries its measured record
on the development bank, as counts (scripts/fit_confidence.py writes the table; it is fitted on
the development bank only and frozen before any held-out run).
"""

DIFFERENCE = {"number_differs", "optional", "adds_words"}
MIN_FOR_PERCENT = 30  # below this, counts only

BASES = {
    "evidence_test": "An evidence test failed (computed in code from the log)",
    "judge_and_text": "The judge and the text comparison agree",
    "text_only": "The text comparison found a difference the judge had passed",
    "number_not_weaker": "The number differs, but it is stricter or its direction is unclear",
    "judge_only": "The judge alone: no near-identical policy sentence to compare with",
    "judge_contradicted": (
        "The judge flagged it, but the policy states the text almost word for word"
    ),
    "procedure_level": "A judge gap on an obligation normally met by a procedure or system",
    "technical_requirement": "A judge gap on a technical system requirement",
}
BANDS = (
    ("1.00", 1.0, 1.01),
    ("0.95 to 0.99", 0.95, 1.0),
    ("0.80 to 0.94", 0.8, 0.95),
    ("below 0.80", -1.0, 0.8),
)


def basis(verdict: str, gap_type: str, evidence: dict | None, has_test: bool = False) -> str:
    """Which checks a finding rests on, from stored fields only."""
    ev = evidence or {}
    if has_test or gap_type == "operating_failure":
        return "evidence_test"
    if ev.get("check") == "level":
        return "procedure_level"
    if ev.get("check") == "technical":
        return "technical_requirement"
    kind = ev.get("kind")
    if kind in DIFFERENCE:
        if ev.get("check") == "number" and ev.get("direction") != "weaker":
            return "number_not_weaker"
        return "judge_and_text" if verdict != "covered" else "text_only"
    if kind == "same":
        return "judge_contradicted"
    return "judge_only"


def combination(base: str, citation_ok: bool) -> str:
    return f"{base}|{'cited' if citation_ok else 'uncited'}"


def band(confidence: float) -> str:
    return next(name for name, low, high in BANDS if low <= confidence < high)


def record(counts: dict | None) -> str:
    """The development-bank record of a signal combination, in words, as counts. Gaps we planted
    are real by construction, so they are named apart from independently adjudicated ones."""
    if not counts or not counts.get("findings"):
        return "No finding of this kind on the development bank."
    real, false = counts.get("real", 0), counts.get("false_alarm", 0)
    planted, other = counts.get("real_planted", 0), counts.get("other_passage", 0)
    judged = real + false
    rest = counts["findings"] - judged - other
    if judged:
        text = (
            f"Development bank: {real} of {judged} adjudicated finding(s) of this kind were "
            "real gaps"
        )
        if planted:
            text += f" ({planted} of them gaps we planted)"
    else:
        text = f"Development bank: {counts['findings']} finding(s) of this kind, none adjudicated"
    if other:
        text += f"; {other} at a planted obligation but citing other text"
    if judged and rest:
        text += f"; {rest} more not adjudicated"
    if judged >= MIN_FOR_PERCENT:
        return text + f" ({round(100 * real / judged)}%)."
    return text + ("." if not judged else ". Too few cases for a percentage.")


def note(verdict, gap_type, evidence, has_test, citation_ok, table: dict) -> dict:
    """The confidence note for one finding: its signals and the record of that combination."""
    base = basis(verdict, gap_type, evidence, has_test)
    key = combination(base, bool(citation_ok))
    return {
        "basis": base,
        "signals": [
            BASES[base],
            "Policy citation verified against the source"
            if citation_ok
            else "Policy citation not verified",
        ],
        "record": record(table.get("combinations", {}).get(key)),
    }
