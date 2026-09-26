"""Integration tests on the real RBI Directions (committed public HTML)."""

from collections import Counter

import pytest

from regcomp.change.diff import diff, substantive
from regcomp.ingest.rbi_html import parse_file

V2 = "data/raw/rbi/kycdir_v2_20251229.html"
V3 = "data/raw/rbi/kycdir_v3_20260918.html"


@pytest.fixture(scope="module")
def v2():
    return parse_file(V2)


@pytest.fixture(scope="module")
def v3():
    return parse_file(V3)


def test_all_83_paragraphs_in_order_without_duplicates(v3):
    paras = [int(c.ref) for c in v3.clauses if c.kind == "para"]
    assert paras == list(range(1, 84))
    assert not [r for r, n in Counter(c.ref for c in v3.clauses).items() if n > 1]


def test_every_span_is_verbatim(v3):
    assert all(v3.text[c.char_start : c.char_end] == c.quote for c in v3.clauses)


def test_known_obligations_present(v3):
    by_ref = {c.ref: c.quote for c in v3.clauses}
    assert any("once in every two years for high-risk customers" in q for q in by_ref.values())
    assert any(
        "within 10 days of commencement of an account-based relationship" in q
        for q in by_ref.values()
    )


def test_rbi_amendment_markers_located(v3):
    marked = {c.ref: c.amended_by for c in v3.clauses if c.amended_by}
    assert set(marked) == {"5(1)(v)", "65(10)(iv)"}
    assert "September 18, 2026" in marked["5(1)(v)"][0]
    assert "December 29, 2025" in marked["65(10)(iv)"][0]


def test_sep_2026_amendment_is_the_only_substantive_change(v2, v3):
    changed = substantive(diff(v2, v3))
    assert [(c.change_class, c.new_ref) for c in changed] == [("modified", "5(1)(v)")]
    assert "Foreign Portfolio Investors (FPIs)" in changed[0].new_text
    assert "Foreign Portfolio Investors" not in changed[0].old_text
