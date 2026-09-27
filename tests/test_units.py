"""LLM units: definitions are split to leaf level; other provisions are unchanged."""

from regcomp.ingest.rbi_html import parse_file
from regcomp.pipeline.units import units

V3 = "data/raw/rbi/kycdir_v3_20260918.html"


def test_definitions_are_leaf_units_with_parent_context():
    us = {u.ref: u for u in units(parse_file(V3))}
    for ref in ("5(1)(iv)(a)", "5(1)(iv)(d)", "5(1)(xvii)"):
        assert us[ref].kind == "definition"
    # A sub-case of a defined term keeps the term's lead-in as read-only context.
    assert "Beneficial Owner" in us["5(1)(iv)(d)"].context
    assert "5(1)(iv)" not in us  # the parent is not sent whole


def test_provision_units_outside_definitions_are_unchanged():
    doc = parse_file(V3)
    us = units(doc)
    assert all(u.kind == "provision" for u in us if not u.ref.startswith("5("))
    by_ref = {c.ref: c for c in doc.clauses}
    for u in us:
        assert u.text == doc.text[u.start : u.start + len(u.text)]  # verbatim slice
        assert u.clause_ref in by_ref
