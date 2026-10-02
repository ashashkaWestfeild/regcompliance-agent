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


def test_internal_item_tags_never_reach_the_reader():
    from regcomp.remediation import scrub

    text = "The policy requires verification within 30 days, matching the obligation in O2."
    assert scrub(text) == "The policy requires verification within 30 days."
    assert (
        scrub("Align the passage with O1 and candidate C3.")
        == "Align the passage with and candidate."
    )
    plain = "Form No. 60 and Rule 9 (1C) are unchanged; 10 per cent stays."
    assert scrub(plain) == plain


def test_one_remedy_per_paragraph_and_the_choice_is_repeatable():
    from regcomp.remediation import one_per_paragraph

    def d(i, ref, priority, by="qwen3:8b", action="Update the policy.", criterion="Done."):
        return {
            "id": i,
            "ref": ref,
            "priority": priority,
            "drafted_by": by,
            "action": action,
            "success_criterion": criterion,
        }

    drafts = [
        d("a", "42(1)", 0.53),
        d(
            "b",
            "42(1)",
            0.60,
            by="qwen3:8b + verbatim obligation (draft failed the fidelity check)",
        ),
        d("c", "48(1)", 0.60, criterion="Matches the obligation in O2."),
        d("e", "48(1)", 0.60),
        d("f", "5(1)(iv)(a)", 0.60),
    ]
    kept, dropped = one_per_paragraph(drafts)
    assert [x["id"] for x in kept] == ["b", "e", "f"]  # priority first, then no internal tag
    assert [x["id"] for x in dropped] == ["a", "c"]
    assert one_per_paragraph(list(reversed(drafts)))[0] == kept


def test_scrub_leaves_the_quoted_wording_alone():
    from regcomp.remediation import scrub

    wording = ' Suggested wording: "Where the customer is a company , the bank shall act."'
    assert scrub("Fix it as in obligation O2." + wording) == "Fix it." + wording


def test_a_stored_rationale_is_shown_without_item_tags():
    from regcomp.remediation import readable

    text = "C3 applies to all risk categories, conflicting with O2's two-year requirement."
    assert readable(text) == (
        "The policy passage applies to all risk categories, conflicting with the obligation's "
        "two-year requirement."
    )
    assert readable("Form No. 60 is unchanged.") == "Form No. 60 is unchanged."


def test_a_list_of_passage_tags_reads_as_one_phrase():
    from regcomp.remediation import readable

    assert readable("C1, C2, and C3 do not address the scenario in O1.") == (
        "The candidate policy passages do not address the scenario in the obligation."
    )
    assert readable("Neither C2 and C4 nor the rest apply.") == (
        "Neither the candidate policy passages nor the rest apply."
    )
