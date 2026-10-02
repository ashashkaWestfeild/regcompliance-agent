"""Text comparison: numbers, force and inserted limits between an obligation and the policy."""

from regcomp.pipeline.verify import Comparer, force, inserted, numbers, sweep

POLICY = (
    "20. Periodic updation of KYC is carried out at least once in every eight years for high "
    "risk customers.\n"
    "21. Explanation: High risk accounts identified at the time of account opening will be "
    "subjected to more intensified monitoring.\n"
    "22. The name and address of the compliance head may be informed to the regulator.\n"
    "23. The bank shall verify the identity of the customer before opening an account and "
    "shall keep a copy of the document obtained.\n"
)


def test_numbers_are_requirement_numbers_only():
    assert numbers("within ten days, or 30 days for ₹50,000 and above") == {"10", "30", "50000"}
    assert numbers("more than rupees fifty thousand or one lakh") == {"50000", "100000"}
    assert numbers("(2) as specified in paragraph 23 and Rule 9(1A) of the Rules, 2005") == set()
    assert numbers("the Act, 2016 (18 of 2016) and any one of the following") == set()
    assert numbers("10 percent") == numbers("ten per cent") == {"10"}


def test_force_reads_duty_and_permission():
    assert force("The bank shall verify") == "must" and force("The bank may verify") == "may"
    assert force("The bank may verify and shall record") == "must" and force("A register") is None


def test_changed_number_is_reported_with_both_values():
    found = Comparer(POLICY).compare(
        "The bank shall carry out periodic updation of KYC at least once in every two years for "
        "high risk customers.",
        "must",
    )
    assert found.kind == "number_differs" and "obligation: 2" in found.detail
    assert "policy: 8" in found.detail and "eight years" in POLICY[found.start : found.end]


def test_optional_and_inserted_limit_and_same_and_absent():
    c = Comparer(POLICY)
    optional = c.compare(
        "The name and address of the compliance head shall be informed to the regulator.", "must"
    )
    assert optional.kind == "optional"
    limited = c.compare(
        "Explanation: The bank shall subject high risk accounts to more intensified monitoring.",
        "must",
    )
    assert limited.kind == "adds_words" and "at the time of account opening" in limited.detail
    same = c.compare(
        "The bank shall verify the identity of the customer before opening an account.", "must"
    )
    assert same.kind == "same"
    assert c.compare("The bank shall appoint an ombudsman for complaints.", "must").kind in (
        "no_similar_text",
        "loose",
    )


def test_plain_rewording_is_not_an_inserted_limit():
    assert (
        inserted(
            "The bank shall strictly adhere to the instructions on opening of accounts.",
            "The instructions on opening of accounts shall be strictly adhered to by all branches.",
        )
        == []
    )


def test_sweep_checks_regulation_sentences_that_no_obligation_covers():
    class Clause:
        ref, depth, char_start, char_end = "5(1)", 2, 0, 10_000

    class Regulation:
        text = (
            "Explanation: Periodic updation of KYC shall be carried out at least once in every "
            "two years for high risk customers.\nThe bank shall appoint an ombudsman."
        )
        clauses = [Clause]

    (hit,) = sweep(Regulation, Comparer(POLICY))
    assert hit["ref"] == "5(1)" and hit["evidence"].kind == "number_differs"
