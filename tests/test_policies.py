"""Integration tests on the two public bank policies (parsed from the committed Docling cache)."""

import pytest

from regcomp.ingest.pdf_docling import parse_policy_pdf

POLICIES = {
    "nainital": "data/raw/policies/nainital_kyc_aml_policy.pdf",
    "centralbank": "data/raw/policies/centralbank_kyc_aml_policy_2025-26.pdf",
}


@pytest.fixture(scope="module", params=list(POLICIES))
def policy(request):
    return request.param, parse_policy_pdf(POLICIES[request.param])


def test_spans_verbatim_and_refs_unique(policy):
    _, doc = policy
    assert all(doc.text[c.char_start : c.char_end] == c.quote for c in doc.clauses)
    refs = [c.ref for c in doc.clauses]
    assert len(refs) == len(set(refs))


def test_body_text_coverage(policy):
    _, doc = policy
    covered = bytearray(len(doc.text))
    for c in doc.clauses:
        covered[c.char_start : c.char_end] = b"\x01" * (c.char_end - c.char_start)
    assert sum(covered) / len(doc.text) > 0.99


def test_page_furniture_removed(policy):
    name, doc = policy
    furniture = {
        "nainital": "Document Name KYC AML POLICY Document Number ORPKYC",
        "centralbank": "_" * 40,
    }[name]
    assert doc.text.count(furniture) <= 2  # a few partial fragments may survive


def test_theme_anchors_present(policy):
    _, doc = policy
    text = " ".join(doc.text.split())
    assert "once in every two years for high risk customers" in text
    assert "once in every six months" in text
