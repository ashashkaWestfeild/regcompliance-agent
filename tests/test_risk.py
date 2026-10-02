"""Risk rubric: subject sets the inherent level, gap type scales it, and reasons are given."""

from regcomp.risk import LEVELS, assess, rubric


def test_subject_sets_inherent_risk_and_gap_type_scales_it():
    bo = "identify the beneficial owner holding more than 10 per cent"
    missing = assess(bo, "D. Identification of Beneficial Owner", "missing_control")
    weak = assess(bo, "D. Identification of Beneficial Owner", "weak_threshold")
    assert missing.inherent == weak.inherent == "high"
    assert missing.residual == "high" and weak.residual == "high"
    assert missing.priority > weak.priority > assess(bo, "", "design_deficiency").priority
    assert assess(bo, "", "design_deficiency").residual == "medium"


def test_sanctions_outrank_training():
    top = assess("freeze the assets of designated individuals under UAPA", "", "missing_control")
    low = assess("conduct training of staff", "", "missing_control")
    assert (top.inherent, top.residual, top.priority) == ("critical", "critical", 1.0)
    assert (low.inherent, low.residual) == ("low", "low")


def test_text_wins_over_heading_and_unmatched_text_gets_the_default():
    by_heading = assess(
        "obtain the documents listed below", "F.1 Enhanced Due Diligence", "narrow_scope"
    )
    assert by_heading.inherent == "high" and "enhanced due diligence" in by_heading.reasons[0]
    by_text = assess(
        "report the suspicious transaction", "Chapter X – Other Instructions", "stale_control"
    )
    assert "suspicious transaction reporting" in by_text.reasons[0]
    assert assess("do something unrelated", "Other", "narrow_scope").inherent == rubric()["default"]


def test_rubric_file_is_well_formed():
    r = rubric()
    assert all(t["level"] in LEVELS for t in r["themes"]) and r["default"] in LEVELS
    assert all(0 < f <= 1 for f in r["gap_factors"].values())
    assert list(r["residual_bounds"]) == ["critical", "high", "medium", "low"]
