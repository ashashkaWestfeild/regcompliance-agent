"""Deterministic gap rules: the same judge verdict + issue always gives the same gap type."""

from regcomp.pipeline.judge import GAP_BY_ISSUE, ISSUES, gap_type
from regcomp.schemas import GapType


def test_partial_issues_map_to_named_gap_types():
    assert gap_type("partial", "optional_not_mandatory") == "weak_modality"
    assert gap_type("partial", "weaker_threshold") == "weak_threshold"
    assert gap_type("partial", "none") == "unspecified"  # partial without a named reason
    assert gap_type("missing", "none") == "missing_control"


def test_covered_is_a_gap_only_for_a_design_deficiency():
    assert gap_type("covered", "none") is None
    assert gap_type("covered", "stricter_than_required") is None
    # The judge may say "covered" and still name the issue: code decides it is a gap ...
    assert gap_type("covered", "optional_not_mandatory", "must") == "weak_modality"
    assert gap_type("covered", "optional_not_mandatory", "must_not") == "weak_modality"
    # ... unless the obligation itself is only a permission.
    assert gap_type("covered", "optional_not_mandatory", "may") is None
    assert gap_type("partial", "optional_not_mandatory", "may") is None
    assert gap_type("covered", "no_owner_or_evidence") == "design_deficiency"


def test_every_issue_and_gap_type_is_known():
    assert set(GAP_BY_ISSUE) <= set(ISSUES)
    assert set(GAP_BY_ISSUE.values()) <= {g.value for g in GapType}
