"""Policy passages: verbatim, sentence-aligned, and skipped where controls already cover them."""

import json
from pathlib import Path

from regcomp.ingest.pdf_docling import parse_policy_items
from regcomp.pipeline.passages import MAX_CHARS, MIN_CHARS, passage_controls, split

POLICY = "data/mutated/nainital.items.json"


def test_split_is_verbatim_and_breaks_at_sentences():
    text = "First rule applies here. " * 20 + "Second part; third part: the end."
    pieces = split(text, limit=120)
    assert len(pieces) > 1
    assert all(b - a <= 120 for a, b in pieces)
    assert all(text[a:b] == text[a:b].strip() for a, b in pieces)
    assert all(text[a:b][-1] in ".;:" for a, b in pieces)
    assert "".join(text[a:b] for a, b in pieces).replace(" ", "") == text.replace(" ", "")


def test_split_keeps_a_sentence_longer_than_the_limit_whole():
    text = "word " * 100
    assert split(text, limit=50) == [(0, len(text.rstrip()))]


def test_passages_are_slices_of_the_policy_and_skip_covered_text():
    doc = parse_policy_items(json.loads(Path(POLICY).read_text(encoding="utf-8")))
    all_passages = passage_controls(doc, [])
    assert all(p["quote"] == doc.text[p["char_start"] : p["char_end"]] for p in all_passages)
    assert all(len(p["quote"]) >= MIN_CHARS for p in all_passages)
    assert sum(len(p["quote"]) > MAX_CHARS for p in all_passages) < len(all_passages) // 20
    # The sentence the dev error analysis found missing from the candidates (RBI 21(2)).
    assert any("international money transfer operations" in p["quote"] for p in all_passages)
    # Text a parent clause holds itself, before its children (RBI 4(1)), is offered too.
    assert any("bring such issue to the notice" in p["quote"] for p in all_passages)
    spans = sorted((p["char_start"], p["char_end"]) for p in all_passages)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))  # no overlaps
    first = all_passages[0]
    control = {"char_start": first["char_start"], "char_end": first["char_end"]}
    assert len(passage_controls(doc, [control])) == len(all_passages) - 1
