from regcomp.applicability import (
    build_profile,
    condition_of,
    decide,
    hits,
    load_vocab,
    without,
)

VOCAB = load_vocab()


def _profile(**has):
    return {
        "bank": "Test Bank",
        "has": {
            attribute: [{"value": v, "basis": "policy"} for v in values]
            for attribute, values in has.items()
        },
        "not_offered": [],
    }


VCIP = "video-based customer identification (V-CIP)"


def test_whole_words_only():
    assert [t.value for t in hits("customer is a trust", VOCAB)] == ["trusts"]
    assert hits("the entrusted officer", VOCAB) == []
    assert hits("pepper", VOCAB) == []
    assert [t.value for t in hits("customer or the beneficial owner is a PEP", VOCAB)] == [
        "politically exposed persons"
    ]


def test_stem_terms_match_plurals():
    assert [t.value for t in hits("cross-border wire transfers", VOCAB)] == ["wire transfers"]


def test_no_condition_applies_by_rule():
    d = decide({"applies_to": None, "quote": "Banks shall have a policy."}, _profile(), VOCAB)
    assert (d["answer"], d["decided_by"], d["reason"]) == ("yes", "rule", "no limiting condition")


def test_the_word_null_is_not_a_condition():
    assert condition_of({"applies_to": " null "}) == ""


def test_attribute_the_bank_has_applies():
    d = decide(
        {"applies_to": "bank opting to undertake V-CIP", "quote": "x"},
        _profile(channels=[VCIP]),
        VOCAB,
    )
    assert d["answer"] == "yes" and d["decided_by"] == "rule"
    assert (d["attribute"], d["value"], d["matched_in"]) == ("channels", VCIP, "condition")


def test_a_silent_profile_is_conditional_never_no():
    d = decide({"applies_to": "customers who are non-profit organisations"}, _profile(), VOCAB)
    assert d["answer"] == "conditional"
    assert "does not say" in d["reason"] and d["value"] == "non-profit organisations"


def test_stated_absence_in_the_condition_is_no():
    profile = without(_profile(channels=[VCIP]), "channels", VCIP, basis="policy")
    d = decide({"applies_to": "accounts opened through V-CIP", "quote": "x"}, profile, VOCAB)
    assert d["answer"] == "no" and d["basis"] == "policy"


def test_assumed_absence_is_conditional():
    profile = without(_profile(), "channels", VCIP, basis="assumption")
    d = decide({"applies_to": "accounts opened through V-CIP"}, profile, VOCAB)
    assert d["answer"] == "conditional" and "assumption" in d["reason"]


def test_a_match_only_in_the_sentence_cannot_exclude():
    profile = without(_profile(), "channels", VCIP, basis="policy")
    d = decide(
        {"applies_to": None, "quote": "The V-CIP application shall be secure."}, profile, VOCAB
    )
    assert d["answer"] == "conditional" and d["matched_in"] == "sentence"


def test_mixed_condition_is_conditional():
    profile = without(_profile(customer_segments=["trusts"]), "channels", VCIP, basis="policy")
    d = decide({"applies_to": "a trust onboarded through V-CIP"}, profile, VOCAB)
    assert d["answer"] == "conditional"


def test_circumstance_and_unknown_attribute_come_from_the_model_kind():
    kinds = {
        "in case of no change in the kyc information": {"kind": "circumstance", "attribute": ""},
        "banks with a treasury desk": {"kind": "bank_attribute", "attribute": "treasury desk"},
    }
    a = decide(
        {"applies_to": "In case of no change in the KYC information"}, _profile(), VOCAB, kinds
    )
    b = decide({"applies_to": "banks with a treasury desk"}, _profile(), VOCAB, kinds)
    assert (a["answer"], a["decided_by"]) == ("yes", "model")
    assert (b["answer"], b["decided_by"], b["attribute"]) == (
        "conditional",
        "model",
        "treasury desk",
    )


def test_an_unclassified_condition_is_never_excluded():
    d = decide({"applies_to": "something the model skipped"}, _profile(), VOCAB, {})
    assert (d["answer"], d["decided_by"]) == ("yes", "rule") and d["matched_in"] is None


def test_profile_is_built_from_the_policy_with_evidence():
    text = (
        "The Bank shall follow this policy. "
        "The Bank may undertake V-CIP for customer onboarding. "
        "Accounts of a Trust need the trust deed."
    )
    p = build_profile("Test Bank", "commercial bank", text, lambda pos: f"at {pos}", VOCAB)
    assert [e["value"] for e in p["has"]["channels"]] == [VCIP]
    assert p["has"]["channels"][0]["where"] == f"at {text.index('V-CIP')}"
    assert "V-CIP" in p["has"]["channels"][0]["evidence"]
    assert [e["value"] for e in p["has"]["customer_segments"]] == ["trusts"]
    assert p["not_offered"] == []
