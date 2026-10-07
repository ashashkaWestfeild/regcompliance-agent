import json
from pathlib import Path

from regcomp.display import (
    comparison_note,
    gap_delta_line,
    precision_headline,
    procedure_note,
    shown_summary,
)

LABELS = {"number_differs": "a number differs", "same": "the policy states this near verbatim"}
ROOT = Path(__file__).resolve().parents[1]


def test_no_number_is_left_out_when_the_reason_names_the_policy_number():
    # live 42(1): RBI 2, 8 and 10 years; the policy 8, 8 and 10
    ev = {
        "kind": "number_differs",
        "detail": "obligation: 2; policy: no number",
        "reason": "the requirement sets a trigger, deadline or interval of 2 ('updation at least "
        "once in every ...'); the policy says 8",
    }
    note = comparison_note(ev, LABELS)
    assert "no number" not in note
    assert note.startswith("a number differs (the requirement sets") and note.endswith("says 8)")


def test_other_details_are_kept():
    absent = {"kind": "number_differs", "detail": "obligation: 10; policy: no number"}
    assert comparison_note(absent, LABELS) == "a number differs: obligation: 10; policy: no number"
    both = {"kind": "number_differs", "detail": "obligation: 2; policy: 8", "reason": "r"}
    assert comparison_note(both, LABELS) == "a number differs: obligation: 2; policy: 8 (r)"
    assert comparison_note({"kind": "same"}, LABELS) == LABELS["same"]


def test_precision_headline_from_the_frozen_summary():
    path = ROOT / "eval" / "reports" / "heldout_precision" / "summary.json"
    line = precision_headline(json.loads(path.read_text(encoding="utf-8")))
    assert "21 of 28" in line
    assert "Central Bank 8 of 9, Dhanlaxmi 9 of 9, South Indian Bank 4 of 10" in line


def test_precision_headline_needs_every_bank():
    one = {"centralbank": {"precision_high_tier": {"after_full_policy_check": "8 of 9"}}}
    assert precision_headline(one) is None


def test_stale_precision_inputs_line_is_not_shown():
    lines = ["decoys flagged 1/3", "precision inputs: 3 planted-gap hits, 51 unkeyed reports "
             "awaiting blind adjudication"]  # fmt: skip
    assert shown_summary(lines) == ["decoys flagged 1/3"]


def test_procedure_note_in_plain_words():
    path = ROOT / "eval" / "reports" / "scorecard_southindianbank.json"
    stored = json.loads(path.read_text(encoding="utf-8"))["procedure_note"]
    assert stored.startswith("Corrected tail.")  # the stored note itself is unchanged
    shown = procedure_note(stored)
    assert "Corrected tail" not in shown and "2 of 3 at first scoring, 1 of 3 after" in shown
    assert procedure_note("Something else.") == "Something else."


def test_gap_delta_line():
    line = gap_delta_line(1)
    assert line.startswith("Projected gap delta +1:") and "both as closed and as new" in line
