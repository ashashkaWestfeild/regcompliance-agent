"""Second-pass detector rules (D2). Text from the development banks only (Central Bank,
Dhanlaxmi, Nainital) and from the RBI Directions; never from the third held-out bank."""

from regcomp.pipeline.detect import added_modifiers, is_definition

# RBI 68 and Central Bank 7.5.7.1 as planted (C05): "savings" added in front of "accounts".
RBI_68 = (
    "The bank shall undertake diligence measures and meticulous monitoring to identify accounts "
    "which are operated as Money Mules and take appropriate action, including reporting of "
    "suspicious transactions to FIU-IND."
)
CB_MULES = (
    "7.5.7.1 -Money mules can be used to launder the proceeds of fraud schemes. Banks shall "
    "undertake diligence measures and meticulous monitoring to identify savings accounts which are "
    "operated as Money Mules and take appropriate action, including reporting of suspicious "
    "transactions to FIU-IND."
)
# RBI 46 condition (1) and Central Bank's copy: same duty, no added words.
RBI_46 = (
    "The bank shall gather sufficient information about a respondent bank to understand fully the "
    "nature of the respondent bank's business and to determine from publicly available "
    "information the reputation of the respondent bank and the quality of supervision, including "
    "whether it has been subjected to a ML / TF investigation or regulatory action."
)
CB_46 = (
    "Banks shall gather sufficient information about a respondent bank to understand fully the "
    "nature of the respondent bank's business and to determine from publicly available "
    "information the reputation of the respondent bank and the quality of supervision, including "
    "whether it has been subjected to a ML/TF investigation or regulatory action."
)
# RBI beneficial-owner wording and Dhanlaxmi's rephrased decoy (L-D01): reordered, not narrowed.
RBI_BO = (
    "Determining whether a customer is acting on behalf of a beneficial owner, and identifying the "
    "beneficial owner and taking all steps to verify the identity of the beneficial owner"
)
DH_BO = (
    "b) establish whether a client acts on behalf of a beneficial owner, identify that beneficial "
    "owner, and take all steps to verify the beneficial owner's identity:"
)


def test_added_modifier_found_by_alignment():
    found = added_modifiers(RBI_68, CB_MULES)
    assert [(m.added, m.before) for m in found] == [("savings", "accounts")]
    assert found[0].overlap >= 0.9


def test_verbatim_copy_adds_nothing():
    assert added_modifiers(RBI_46, CB_46) == []


def test_reordered_rbi_words_are_not_an_addition():
    assert added_modifiers(RBI_BO, DH_BO) == []


def test_unrelated_sentence_is_not_compared():
    assert added_modifiers(RBI_68, CB_46) == []


def test_added_number_is_left_to_the_number_rules():
    policy = RBI_46.replace("a respondent bank to", "a respondent bank within 30 days to")
    assert all(not any(c.isdigit() for c in m.added) for m in added_modifiers(RBI_46, policy))


def test_definition_support():
    # Dhanlaxmi 4.2.10 (the passage the judge relied on for L01)
    assert is_definition(
        "4.2.10 On-going Due Diligence' means regular monitoring of transactions in accounts to "
        "ensure that those are consistent with the Bank's knowledge about the customers."
    )
    # Central Bank definitions: one quoted term, one capitalised name
    assert is_definition("Small Account' means a saving account in a banking company where:")
    assert is_definition(
        "Customer Identification means undertaking the process of Customer due diligence (CDD)."
    )


def test_duty_is_not_a_definition():
    assert not is_definition(CB_46)
    assert not is_definition(CB_MULES.split(". ", 1)[1])
    # Central Bank: "by means such as" is not a definition
    assert not is_definition(
        "Positive confirmation may be carried out by means such as address verification letter, "
        "contact point verification, deliverables, etc."
    )
    assert not is_definition("The bank shall keep records which means keeping them for 5 years.")
