from regcomp.conflicts import conflicts, quantities, restates

RBI = (
    "The bank shall carry out periodic updation of KYC at least once in every two years for "
    "high-risk customers and once in every ten years for low-risk customers."
)


def test_quantities_read_periods_grades_and_customer_types():
    q = quantities("High-risk customers: at least once every two years from the last updation.")
    assert [(x.dimension, x.value, x.grade) for x in q] == [("days", 730.0, "high")]
    q = quantities("within 10 days of opening, or more than 15 percent of the partnership")
    assert [(x.dimension, x.value, x.entity) for x in q] == [
        ("days", 10.0, "partnership"),
        ("percent", 15.0, "partnership"),
    ]
    assert quantities("review risk categorisation half-yearly")[0].value == 182


def test_restates_needs_shared_wording_in_either_order():
    assert restates(RBI, "KYC updation is done once in every five years for high risk customers.")
    assert not restates(RBI, "Customers shall submit changed documents within 30 days.")


def test_two_values_for_the_same_grade_are_a_conflict():
    policy = (
        "Periodic updation of KYC is carried out once in every two years for high risk "
        "customers. Other text about something else entirely here. Annex: periodic updation "
        "of KYC once in every five years for high risk customers."
    )
    found = conflicts(RBI, policy)
    assert len(found) == 1
    assert found[0]["grade"] == "high" and sorted(found[0]["values"]) == [730.0, 1825.0]


def test_different_grades_or_customer_types_are_not_a_conflict():
    policy = (
        "Periodic updation of KYC once in every two years for high risk customers. Periodic "
        "updation of KYC once in every ten years for low risk customers."
    )
    assert conflicts(RBI, policy) == []
    bo = "the beneficial owner holds more than 10 percent of the company's shares."
    policy = (
        "The beneficial owner holds more than 10 percent of the company's shares. Where the "
        "customer is a partnership, the beneficial owner holds more than 15 percent of capital."
    )
    assert conflicts(bo, policy) == []
