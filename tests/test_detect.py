"""Second-pass detector rules (D2). Text from the development banks only (Central Bank,
Dhanlaxmi, Nainital) and from the RBI Directions; never from the third held-out bank."""

from regcomp.pipeline.detect import added_modifiers, definition_support, is_definition

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


# RBI 5(2)(xiii) is itself a definition; Nainital defines the same term: right support, no finding.
RBI_PU = (
    "‘Periodic Updation’ means the steps taken to ensure that documents, data or "
    "information collected under the CDD process are kept up-to-date and relevant by undertaking "
    "reviews of existing records at the periodicity prescribed by the RBI."
)
NAINITAL_PU = (
    "ii. 'Periodic Updation' means steps taken to ensure that documents, data or information "
    "collected under the CDD process is kept up-to-date and relevant by undertaking reviews of "
    "existing records at periodicity prescribed by the Reserve Bank."
)
DH_DEF = (
    "4.2.10 On-going Due Diligence' means regular monitoring of transactions in accounts to ensure "
    "that those are consistent with the Bank's knowledge about the customers."
)


def test_definition_support_needs_a_duty():
    assert not definition_support(RBI_PU, NAINITAL_PU)
    assert definition_support(RBI_68, DH_DEF)
    assert not definition_support(RBI_68, CB_MULES)


# Dhanlaxmi 30.6 b: a list with a lead-in (structure of the L03 miss, different subject).
PO_TEXT = (
    "b. Responsibilities of the Principal Officer: "
    "i. Compliance Oversight: Oversee the bank's compliance with KYC regulations and internal "
    "policies. "
    "ii. Transaction Monitoring: Monitor customer transactions for any suspicious activities."
)


def _po_clauses():
    from regcomp.pipeline.detect import Clause

    first = PO_TEXT.index("i. Compliance")
    second = PO_TEXT.index("ii. Transaction")
    return [
        Clause("b", 0, len(PO_TEXT)),
        Clause("b(i)", first, second - 1),
        Clause("b(ii)", second, len(PO_TEXT)),
    ]


def test_lead_in_of_a_list_item():
    from regcomp.pipeline.detect import lead_in

    clauses = _po_clauses()
    item = clauses[2]
    # the last sentence of the lead-in; a list marker such as "b." is not part of it
    assert lead_in(clauses, PO_TEXT, item.start, item.end) == (
        "Responsibilities of the Principal Officer:"
    )
    # the lead-in itself has no lead-in; nor does text outside any list
    assert lead_in(clauses, PO_TEXT, 0, 20) is None
    assert lead_in([], PO_TEXT, item.start, item.end) is None


def test_support_overlap():
    from regcomp.pipeline.detect import support_overlap
    from regcomp.pipeline.verify import CLOSE

    assert support_overlap(RBI_68, CB_MULES) >= 0.9
    assert support_overlap(RBI_68, CB_46) < CLOSE


def test_limiting_words_must_be_in_the_policy_text():
    from regcomp.pipeline.detect import limiting_words_found, scope_prompt

    item = {"id": "1", "obligation": RBI_68, "passage": CB_MULES, "lead_in": None}
    assert limiting_words_found({"limiting_words": "savings  accounts"}, item)
    assert not limiting_words_found({"limiting_words": "current accounts"}, item)
    assert not limiting_words_found({"limiting_words": None}, item)
    listed = item | {"lead_in": "b. Responsibilities of the Principal Officer:"}
    assert "<lead_in>b. Responsibilities" in scope_prompt([listed])
    assert "<lead_in>" not in scope_prompt([item])
