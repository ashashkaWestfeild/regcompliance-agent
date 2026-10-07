"""Wording of a few app lines (8 Oct 2026). Display only: no verdict, gap, score or stored value
changes, and the stored scorecards and evidence are shown as they are, only worded more plainly.

A new module, so the hosted app loads it fresh after a push (PROBLEMS_LOG P-059)."""

import re

HELD_OUT = (
    ("centralbank", "Central Bank"),
    ("dhanlaxmi", "Dhanlaxmi"),
    ("southindianbank", "South Indian Bank"),
)


def comparison_note(ev: dict, labels: dict[str, str]) -> str:
    """The "Text comparison" line of a finding.

    When the policy states one number differently, verify stores a reason that names both
    numbers. Its detail then may say "policy: no number" only because the policy's number also
    appears elsewhere in the RBI sentence (re-KYC every 2, 8 and 10 years; the policy says 8, 8
    and 10), so that detail is left out rather than shown beside a reason that contradicts it."""
    detail, reason = ev.get("detail") or "", ev.get("reason") or ""
    if reason and detail.endswith("policy: no number"):
        detail = ""
    note = labels[ev["kind"]] + (f": {detail}" if detail else "")
    return note + (f" ({reason})" if reason else "")


def precision_headline(summary: dict) -> str | None:
    """One line from eval/reports/heldout_precision/summary.json: real gaps among the blind
    samples of high-confidence findings, per bank and in total. None if a bank is missing."""
    parts, real, total = [], 0, 0
    for key, name in HELD_OUT:
        bank = (summary.get(key) or {}).get("precision_high_tier", {})
        value = bank.get("after_full_policy_check")
        found = re.fullmatch(r"(\d+) of (\d+)", value or "")
        if not found:
            return None
        real, total = real + int(found[1]), total + int(found[2])
        parts.append(f"{name} {value}")
    return (
        f"**On three banks it had never seen, {real} of {total} high-confidence findings in blind "
        f"samples were real gaps** ({', '.join(parts)}), after a check against the full policy. "
        "Each bank was run once with frozen code; per-bank results below."
    )


def shown_summary(lines: list[str]) -> list[str]:
    """Scorecard summary lines for the app. The "precision inputs" line counted reports still
    awaiting blind labelling when the card was scored; those samples have since been labelled
    and their result is the headline above, so the stale line is not shown."""
    return [line for line in lines if not line.startswith("precision inputs:")]


def procedure_note(note: str) -> str:
    """Plain wording for a scorecard's procedure note (the stored note is unchanged)."""
    if note.startswith("Corrected tail."):
        return (
            "First scoring corrected: three code-only steps first ran with the development "
            "bank's defaults, so its synthetic evidence log flagged a decoy. They were re-run with "
            "this bank's own setting, as for the other two banks; no model output changed. Decoys "
            "flagged: 2 of 3 at first scoring, 1 of 3 after."
        )
    return note


def gap_delta_line(delta: int) -> str:
    """Why the recorded projection can differ from the version counts shown beside it."""
    return (
        f"Projected gap delta {delta:+d}: the agent's count at its compare step, gaps that would "
        "open minus gaps judged closed (a gap no longer raised but not judged covered goes to a "
        "person and is not counted). The tables below count row versions instead: every row of "
        "the changed clause is closed in time and replaced, so a gap that continues appears both "
        "as closed and as new."
    )
