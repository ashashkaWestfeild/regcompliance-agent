from datetime import date

import yaml

from regcomp.citation import (
    policy_citation,
    policy_lines,
    predates,
    regulation_citation,
    regulation_lines,
)
from regcomp.sources import SOURCES, document_fields, policy_meta, regulation_meta

RAW = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
MARKER = (
    "Inserted with effect from December 29, 2025 vide Reserve Bank of India (Commercial Banks - "
    "Know Your Customer) Amendment Directions, 2025 dated December 29, 2025"
)


def _regulation():
    latest = RAW["regulation"][2]
    return latest, document_fields(regulation_meta(latest["version_label"]))


def test_regulation_citation_fields_equal_the_source_record():
    original = RAW["regulation"][0]
    latest, doc = _regulation()
    c = regulation_citation(doc, "65(10)(iv)", [MARKER])
    assert c["document"] == original["title"]
    assert c["paragraph"] == "65(10)(iv)"
    assert c["reference_no"] == original["reference_no"]
    assert c["issued_on"] == original["issued_on"]
    assert c["version_date"] == latest["effective_from"]
    assert c["version_amended_by"] == latest["amended_by"]
    assert c["url"] == latest["retrieved_from"]
    assert c["amendments"] == [{"marker": MARKER, "effective": date(2025, 12, 29)}]


def test_the_three_dates_are_labelled_separately():
    _, doc = _regulation()
    lines = regulation_lines(regulation_citation(doc, "65(10)(iv)", [MARKER]))
    assert "First issued: 28 Nov 2025" in lines
    assert any(x.startswith("Version in force: updated as on 18 Sep 2026") for x in lines)
    assert any(
        x.startswith("This paragraph was amended, in effect from 29 Dec 2025") for x in lines
    )
    assert len({x.split(":")[0] for x in lines}) == len(lines)  # no label is used twice


def test_policy_citation_fields_equal_the_source_record():
    for entry in RAW["policies"]:
        c = policy_citation(document_fields(policy_meta(entry["id"])), "42")
        assert c["document"] == entry["title"]
        assert c["issuer"] == entry["bank"]
        assert c["stated_date"] == entry["stated_date"]
        assert c["stated_date_kind"] == entry["stated_date_kind"]
        assert c["url"] == entry["retrieved_from"]
        assert policy_lines(c)[0] == f"{entry['bank']}: {entry['title']}, section 42"


def test_a_policy_older_than_the_amendment_is_flagged():
    _, doc = _regulation()
    policy = policy_citation(document_fields(policy_meta("nainital")), "70")
    amended = regulation_citation(doc, "65(10)(iv)", [MARKER])
    plain = regulation_citation(doc, "42(1)", [])
    assert predates(policy, amended) == [
        "The policy's own date (review due on 31 Oct 2025) is earlier than the amendment to this "
        "paragraph (in effect from 29 Dec 2025)."
    ]
    assert predates(policy, plain) == []
    later = dict(policy, stated_date=date(2026, 1, 15))
    assert predates(later, amended) == []
