"""Text comparison: numbers, force and inserted limits between an obligation and the policy."""

from regcomp.pipeline.verify import Comparer, direction, force, inserted, numbers, sweep

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


def test_direction_of_a_changed_number_follows_the_wording_around_it():
    trigger = "the natural person with ownership of more than 10 per cent of the capital"
    assert direction(trigger, trigger.replace("10 per cent", "25 percent"))[0] == "weaker"
    assert direction(trigger, trigger.replace("10 per cent", "five per cent"))[0] == "stricter"
    interval = "periodic updation at least once in every two years for high risk customers"
    assert direction(interval, interval.replace("two", "eight"))[0] == "weaker"
    deadline = "upload the records within 10 days of opening the account"
    assert direction(deadline, deadline.replace("10", "seven"))[0] == "stricter"
    floor = "preserve the records for at least five years after the relationship ends"
    assert direction(floor, floor.replace("five", "three"))[0] == "weaker"
    assert direction(floor, floor.replace("five", "eight"))[0] == "stricter"
    # no wording that decides it, or more than one number changed: left to a model or a person
    assert (
        direction("the limit is rupees 50,000 per day", "the limit is rupees 25,000 per day")
        is None
    )
    assert direction(interval, "something else entirely about 9 branches") is None


def test_technical_requirement_convention_matches_system_wording_only():
    import re
    from pathlib import Path

    import yaml

    rule = yaml.safe_load(Path("data/triage.yaml").read_text(encoding="utf-8"))
    pattern = re.compile(rule["technical_requirement"]["pattern"], re.IGNORECASE)
    for technical in (
        "The bank shall ensure end-to-end encryption of data between the device and the server.",
        "The application shall prevent connection from IP addresses outside India.",
        "The bank shall store the entire data and recordings in systems located in India.",
        "The software and relevant APIs shall be tested before use in live environment.",
    ):
        assert pattern.search(technical), technical
    for governance in (
        "The bank shall put in place a system of periodic review of risk categorisation.",
        "The bank shall carry out periodic updation at least once in every two years.",
        "The beneficial owner is the natural person with more than 10 per cent ownership.",
        "The Principal Officer shall be responsible for ensuring compliance.",
        "The bank shall subject high-risk accounts to more intensified monitoring.",
    ):
        assert not pattern.search(governance), governance
    assert rule["technical_requirement"]["tier"] == "review"


def test_the_number_one_counts_only_when_it_measures_something():
    assert numbers("ensure the updation of KYC within one year of its falling due") == {"1"}
    assert numbers("ownership of more than 1 per cent of the capital") == {"1"}
    assert numbers("within one (1) month of the request") == {"1"}
    assert numbers("any one of the following documents shall be obtained") == set()
    assert numbers("one or more natural persons") == set()
    assert numbers("(1) The bank shall act on the request") == set()
    assert numbers("holding 1.5 per cent or 11 per cent, within 21 days") == {"1.5", "11", "21"}


def test_one_year_against_two_years_is_a_changed_number_and_weaker():
    regulation = (
        "The bank shall ensure the updation of KYC within one year of its falling due for KYC."
    )
    policy = (
        "Some other clause of the policy about records. The bank shall ensure the updation of "
        "KYC within two years of its falling due for KYC. Another clause follows here."
    )
    found = Comparer(policy).compare(regulation, "must")
    assert found.kind == "number_differs"
    assert found.detail == "obligation: 1; policy: 2"
    way, why = direction(regulation, policy[found.start : found.end])
    assert way == "weaker" and "deadline" in why


def test_one_year_and_twelve_months_are_the_same_period():
    regulation = (
        "The bank shall ensure the updation of KYC within one year of its falling due for KYC."
    )
    same = "The bank shall ensure the updation of KYC within 12 months of its falling due for KYC."
    other = "The bank shall ensure the updation of KYC within 12 days of its falling due for KYC."
    assert Comparer(same).compare(regulation, "must").kind == "same"
    assert (
        Comparer(same).compare(regulation.replace("one year", "twelve months"), "must").kind
        == "same"
    )
    assert Comparer(regulation).compare(same, "must").kind == "same"
    assert Comparer(other).compare(regulation, "must").kind == "number_differs"
    two_years = regulation.replace("one year", "two years")
    assert Comparer(same).compare(two_years, "must").kind == "number_differs"
    assert (
        Comparer(same.replace("12 months", "24 months")).compare(two_years, "must").kind == "same"
    )
