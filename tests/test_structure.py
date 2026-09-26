from regcomp.change.diff import diff, substantive
from regcomp.ingest.structure import Block, build


def blocks(*texts, heading=()):
    return [Block(text=t, is_heading=(i in heading)) for i, t in enumerate(texts)]


def test_nesting_refs_and_verbatim_spans():
    doc = build(
        blocks(
            "Chapter I – Preliminary",
            "5. In these Directions:",
            "(1) Terms from the Act:",
            "(i) 'Aadhaar number' means ...",
            "(ii) Beneficial Owner",
            "(a) Where the customer is a company ...",
            "Explanation: more than 10 percent.",
            "(b) Where the customer is a partnership firm ...",
            "(iii) 'Certified Copy' means ...",
            "6. Next paragraph.",
            heading={0},
        )
    )
    refs = [c.ref for c in doc.clauses]
    assert refs == [
        "5",
        "5(1)",
        "5(1)(i)",
        "5(1)(ii)",
        "5(1)(ii)(a)",
        "5(1)(ii)(b)",
        "5(1)(iii)",
        "6",
    ]
    for c in doc.clauses:
        assert doc.text[c.char_start : c.char_end] == c.quote
    a = next(c for c in doc.clauses if c.ref == "5(1)(ii)(a)")
    assert "Explanation: more than 10 percent." in a.quote  # unmarked block joins deepest clause
    assert "(b)" not in a.quote
    assert next(c for c in doc.clauses if c.ref == "5").chapter == "Chapter I – Preliminary"


def test_letter_i_after_h_is_alpha_not_roman():
    doc = build(blocks("1. Documents:", "(g) seven", "(h) eight", "(i) nine", "(j) ten"))
    assert [c.kind for c in doc.clauses[1:]] == ["alpha"] * 4
    assert doc.clauses[3].ref == "1(i)"


def test_amendment_marker_attaches_to_clause():
    b = blocks("1. Rule.", "(1) sub-rule.")
    b[1].amended_by = ["Inserted with effect from September 18, 2026"]
    doc = build(b)
    assert doc.clauses[1].amended_by == ["Inserted with effect from September 18, 2026"]


def test_diff_ignores_pdf_word_split_noise():
    old = build(blocks("1. The bank shall tak e cognizance of the per son.", "2. Unchanged."))
    new = build(blocks("1. The bank shall take cognizance of the person.", "2. Unchanged."))
    classes = {c.new_ref: c.change_class for c in diff(old, new)}
    assert classes == {"1": "cosmetic", "2": "unchanged"}


def test_diff_reports_change_once_at_deepest_clause():
    old = build(blocks("5. Definitions:", "(1) NRIs and PIOs may use route X."))
    new = build(blocks("5. Definitions:", "(1) NRIs, PIOs and FPIs may use route X."))
    changed = substantive(diff(old, new))
    assert [(c.change_class, c.new_ref) for c in changed] == [("modified", "5(1)")]


def test_diff_new_and_repealed():
    old = build(blocks("1. Keep.", "2. Drop me."))
    new = build(blocks("1. Keep.", "3. Brand new obligation about CKYCR uploads."))
    classes = sorted((c.change_class, c.old_ref, c.new_ref) for c in substantive(diff(old, new)))
    assert classes == [("new", None, "3"), ("repealed", "2", None)]
