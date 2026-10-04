"""Reviewer decisions: validated before anything is written."""

import pytest

from regcomp.review import DECISIONS, decide


def test_decisions_and_their_effects_are_fixed():
    assert set(DECISIONS) == {"confirm", "dismiss", "resolve", "accept"}
    assert DECISIONS["confirm"] == ("open", "high", None)
    assert DECISIONS["dismiss"][2] == "covered"  # a false alarm corrects the verdict
    assert DECISIONS["accept"][0] == "accepted" and DECISIONS["resolve"][0] == "closed"


def test_a_decision_needs_a_known_action_a_reviewer_and_a_reason():
    with pytest.raises(ValueError, match="unknown decision"):
        decide(None, "g1", "delete", "A. Reviewer", "because")
    with pytest.raises(ValueError, match="reviewer name and a reason"):
        decide(None, "g1", "dismiss", "", "because")
    with pytest.raises(ValueError, match="reviewer name and a reason"):
        decide(None, "g1", "dismiss", "A. Reviewer", "  ")


def test_reviewer_code_check():
    from regcomp.review import code_matches

    assert code_matches("s3cret-code", "s3cret-code")
    assert not code_matches("wrong", "s3cret-code")
    assert not code_matches("", "s3cret-code")
    assert not code_matches("anything", "")  # no code configured: always a simulation
    assert not code_matches("", "")
