"""Policy passages as mapping candidates, cut deterministically from the clause tree.

Control extraction is an LLM step and it is lossy: on the dev policy 443 of 769 leaf clauses had
no extracted control (2 Oct), so an obligation the policy copies word for word could be judged
"missing" because its text was never a candidate. All policy text is therefore also offered to
retrieval as plain text, in sentence-aligned pieces, unless extracted controls already cover it.
A passage carries no control attributes (owner, frequency, ...): those were never extracted.
"""

import re

MAX_CHARS = 700  # one passage; a long clause becomes several
MIN_CHARS = 40  # headings and stubs are not candidates
COVERED = 0.8  # share of a passage inside extracted control spans that makes it redundant

_BREAK = re.compile(r"(?<=[.;:])\s+|\n+")


def split(text: str, limit: int = MAX_CHARS) -> list[tuple[int, int]]:
    """(start, end) offsets of consecutive pieces of `text`, each at most `limit` characters
    where a sentence boundary allows it. Pieces are verbatim slices; whitespace between them is
    dropped."""
    cuts = [m.end() for m in _BREAK.finditer(text)] + [len(text)]
    pieces, start, last = [], 0, 0
    for cut in cuts:
        if cut - start > limit and last > start:
            pieces.append((start, last))
            start = last
        last = cut
    pieces.append((start, len(text)))
    out = []
    for a, b in pieces:
        body = text[a:b]
        lead = len(body) - len(body.lstrip())
        if body.strip():
            out.append((a + lead, a + len(body.rstrip())))
    return out


def _covered(start: int, end: int, spans: list[tuple[int, int]]) -> float:
    inside = sum(max(0, min(end, e) - max(start, s)) for s, e in spans)
    return inside / max(end - start, 1)


def _own_text(doc) -> list[tuple[object, int, int]]:
    """(clause, start, end) for the text each clause holds itself, outside the clauses nested in
    it: a leaf's whole span, and a parent's lead-in and any text between its children. Nesting is
    read from the character spans, because a repeated clause number makes parent_ref ambiguous."""
    out = []
    for clause in doc.clauses:
        size = clause.char_end - clause.char_start
        inner = sorted(
            (c.char_start, c.char_end)
            for c in doc.clauses
            if c is not clause
            and clause.char_start <= c.char_start
            and c.char_end <= clause.char_end
            and c.char_end - c.char_start < size
        )
        at = clause.char_start
        for start, end in inner:
            if start > at:
                out.append((clause, at, start))
            at = max(at, end)
        if at < clause.char_end:
            out.append((clause, at, clause.char_end))
    return out


def passage_controls(doc, controls: list[dict]) -> list[dict]:
    """Control-shaped records for the policy text that extracted controls do not already cover.
    Same keys as an extracted control; attributes are None."""
    spans = [(c["char_start"], c["char_end"]) for c in controls]
    out = []
    for clause, seg_start, seg_end in _own_text(doc):
        text = doc.text[seg_start:seg_end]
        for a, b in split(text):
            start, end = seg_start + a, seg_start + b
            if end - start < MIN_CHARS or _covered(start, end, spans) >= COVERED:
                continue
            out.append(
                {
                    "passage": True,
                    "objective": "",
                    "type": None,
                    "nature": None,
                    "owner": None,
                    "scope": None,
                    "evidence": None,
                    "frequency": None,
                    "threshold": None,
                    "unit_ref": f"{clause.ref}#passage",
                    "unit_kind": "passage",
                    "clause_ref": clause.ref,
                    "quote": doc.text[start:end],
                    "char_start": start,
                    "char_end": end,
                }
            )
    return out
