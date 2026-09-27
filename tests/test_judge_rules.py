"""Deterministic judge rules: element checks -> verdict, issue, gap type, confidence."""

from regcomp.pipeline.judge import confidence, decide, gap_type

OK = {"action": "same", "threshold": "same", "scope": "same", "owner_named": True}


def test_full_match_is_covered_without_gap():
    assert decide(OK, True, False) == ("covered", "none")
    assert gap_type("covered", "none") is None


def test_different_action_is_missing_even_if_model_says_covered():
    v, issue = decide({**OK, "action": "different", "verdict": "covered"}, True, False)
    assert (v, issue) == ("missing", "not_addressed")
    assert gap_type(v, issue) == "missing_control"


def test_no_control_is_missing():
    assert decide(OK, False, False)[0] == "missing"


def test_conflict_beats_threshold_and_scope():
    r = {**OK, "threshold": "weaker", "scope": "narrower"}
    assert decide(r, True, True) == ("partial", "conflicting_statements")
    assert gap_type("partial", "conflicting_statements") == "internal_contradiction"


def test_weaker_threshold_is_weak_or_stale():
    assert gap_type(*decide({**OK, "threshold": "weaker"}, True, False)) == "weak_threshold"
    stale = {**OK, "threshold": "weaker", "issue": "outdated_requirement"}
    assert gap_type(*decide(stale, True, False)) == "stale_control"


def test_stricter_or_unstated_threshold_is_not_a_gap():
    for t in ("stricter", "not_stated", "not_applicable"):
        assert decide({**OK, "threshold": t}, True, False) == ("covered", "none")


def test_narrower_scope_and_partial_action():
    assert gap_type(*decide({**OK, "scope": "narrower"}, True, False)) == "narrow_scope"
    assert decide({**OK, "action": "part", "issue": "none"}, True, False) == (
        "partial",
        "not_addressed",
    )


def test_missing_owner_is_design_deficiency_on_covered():
    v, issue = decide({**OK, "owner_named": False}, True, False)
    assert v == "covered" and gap_type(v, issue) == "design_deficiency"


def test_confidence_from_signals_not_self_report():
    assert confidence("covered", "covered", True) == 0.9
    assert confidence("covered", "missing", True) == 0.6
    assert confidence("covered", "covered", False) == 0.4
