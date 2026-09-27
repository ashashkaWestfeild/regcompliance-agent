from datetime import date

from regcomp.evidence import (
    ckycr_late,
    design_test,
    generate_ckycr,
    generate_rekyc,
    operating_test,
    rekyc_overdue,
)

AS_OF = date(2026, 9, 30)


def test_design_test_lists_missing_attributes():
    ok = design_test({"owner": "Principal Officer", "frequency": "monthly", "evidence": "log"})
    assert ok.result == "effective"
    bad = design_test({"owner": None, "frequency": "monthly", "evidence": None})
    assert bad.result == "ineffective"
    assert "owner" in bad.rationale and "evidence" in bad.rationale


def test_operating_test_without_evidence_cannot_assess():
    assert operating_test([], lambda r: True).result == "cannot_assess"


def test_generators_are_deterministic_and_hit_their_rates():
    a = generate_ckycr(800, late_rate=0.12, seed=202, start=date(2026, 3, 1))
    assert a == generate_ckycr(800, late_rate=0.12, seed=202, start=date(2026, 3, 1))
    ckycr = operating_test(a, ckycr_late(10))
    assert ckycr.result == "ineffective" and 0.08 < ckycr.exception_rate < 0.16
    rekyc = operating_test(generate_rekyc(1200, 0.02, 101, AS_OF), rekyc_overdue(AS_OF))
    assert rekyc.result == "effective" and rekyc.exception_rate < 0.05


def test_evidence_rows_carry_no_personal_data():
    row = generate_rekyc(1, 0.0, 1, AS_OF)[0]
    assert set(row) == {"account_id", "risk_category", "last_kyc_update"}
