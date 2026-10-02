from datetime import date

import yaml

from regcomp.sources import SOURCES, marker_date, policy_meta, regulation_meta

RAW = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))


def test_a_later_version_keeps_the_original_reference_and_issue_date():
    original = RAW["regulation"][0]
    latest = RAW["regulation"][2]
    meta = regulation_meta(latest["version_label"])
    assert meta["reference_no"] == original["reference_no"]
    assert meta["issued_on"] == original["issued_on"] == date(2025, 11, 28)
    assert meta["source_title"] == original["title"]
    # the three dates are kept apart: issue date and version date differ
    assert meta["version_date"] == latest["effective_from"] == date(2026, 9, 18)
    assert meta["amended_by"] == latest["amended_by"]
    assert meta["url"] == latest["retrieved_from"]


def test_a_version_with_several_files_cites_the_page_that_was_parsed():
    second = RAW["regulation"][1]
    html = next(f for f in second["files"] if f["file"].endswith(".html"))
    assert regulation_meta(second["version_label"])["url"] == html["retrieved_from"]


def test_policy_fields_equal_the_source_record():
    for entry in RAW["policies"]:
        meta = policy_meta(entry["id"])
        assert meta["source_title"] == entry["title"]
        assert meta["issuer"] == entry["bank"]
        assert meta["url"] == entry["retrieved_from"]
        assert meta["stated_date"] == entry["stated_date"]
        assert meta["stated_date_kind"] == entry["stated_date_kind"]
        assert isinstance(meta["stated_date"], date)


def test_marker_date_is_read_from_the_marker_text():
    marker = (
        "Inserted with effect from December 29, 2025 vide Reserve Bank of India (Commercial "
        "Banks - Know Your Customer) Amendment Directions, 2025 dated December 29, 2025"
    )
    assert marker_date(marker) == date(2025, 12, 29)
    assert marker_date("Substituted vide a later notification") is None
    assert marker_date("") is None


def test_a_file_is_traced_to_its_version_and_a_draft_to_none():
    from regcomp.sources import regulation_meta_for_file

    second = RAW["regulation"][1]
    for f in second["files"]:
        assert regulation_meta_for_file(f["file"])["version_date"] == second["effective_from"]
    assert regulation_meta_for_file("data/synthetic/kycdir_draft_whatif.html") is None
