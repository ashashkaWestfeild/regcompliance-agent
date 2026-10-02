"""Remediation: owner and due date by rule; drafted wording must keep numbers and duties."""

from datetime import date

from regcomp import remediation
from regcomp.remediation import clean, draft, due_date, owner_for, unfaithful

OB = "(2) The bank shall upload KYC records within 10 days and shall not open anonymous accounts."
GAP = {
    "type": "weak_threshold",
    "residual": "high",
    "obligation": OB,
    "reason": "30 days",
    "policy_passage": "…",
}
TODAY = date(2026, 10, 2)


def test_owner_and_due_date_are_rules():
    assert owner_for("weak_threshold")[0] == "2LoD" and owner_for("operating_failure")[0] == "1LoD"
    assert due_date("critical", TODAY) == date(2026, 11, 1)
    assert due_date("high", TODAY) < due_date("medium", TODAY) < due_date("low", TODAY)


def test_fidelity_check_catches_changed_numbers_and_lost_duties():
    assert clean(OB).startswith("The bank shall upload")
    good = "The bank shall upload KYC records within 10 days and shall not open anonymous accounts."
    assert unfaithful(OB, good) == []  # the list marker "(2)" is not a number to keep
    assert "drops: 10" in unfaithful(OB, "The bank shall upload records promptly and shall not …")
    assert "adds: 30" in unfaithful(OB, good.replace("10 days", "10 to 30 days"))
    assert "the prohibition is lost" in unfaithful(OB, "The bank shall upload within 10 days.")
    assert "the duty is no longer mandatory" in unfaithful(
        OB, "The bank may upload within 10 days and will not open them."
    )


def _model(answers):
    calls = []

    def fake(stage, system, user, schema, conn=None):
        calls.append(user)
        return answers[min(len(calls), len(answers)) - 1]

    return fake, calls


def test_unfaithful_draft_is_retried_then_replaced_by_the_obligation(monkeypatch):
    bad = {
        "action": "Tighten it.",
        "policy_wording": "Upload within 30 days.",
        "success_criterion": "Seen.",
    }
    fake, calls = _model([bad])
    monkeypatch.setattr(remediation, "complete_json", fake)
    out = draft(GAP, TODAY)
    assert len(calls) == 2 and "rejected_wording" in calls[1]
    assert clean(OB) in out["action"] and "fidelity check" in out["drafted_by"]
    assert out["checks"] and out["owner_line"] == "2LoD" and out["due_date"] == date(2026, 12, 1)


def test_faithful_draft_is_kept_and_evidence_gaps_need_no_model(monkeypatch):
    ok = {
        "action": "Change the deadline.",
        "policy_wording": "The bank shall upload them within 10 days and shall not open them.",
        "success_criterion": "Policy shows 10 days.",
    }
    fake, calls = _model([ok])
    monkeypatch.setattr(remediation, "complete_json", fake)
    out = draft(GAP, TODAY)
    assert len(calls) == 1 and out["checks"] == [] and "within 10 days" in out["action"]
    evidence = draft(dict(GAP, type="operating_failure", reason="88/800 late"), TODAY)
    assert len(calls) == 1 and evidence["drafted_by"] == "rule" and "88/800" in evidence["action"]
