"""Clause-level diff between two parsed versions of a regulation.

Each clause is compared on its *own* text (the clause minus its sub-clauses), so a change in
``5(1)(v)`` is reported once, at ``5(1)(v)``, and not again at ``5(1)`` and ``5``.

Classification is deterministic and happens before any LLM call:
- ``unchanged``: identical canonical text.
- ``cosmetic``: identical after ``for_diff`` normalization (whitespace, quotes, dashes, case,
  footnote brackets), which absorbs PDF word-splitting noise.
- ``modified`` / ``new`` / ``repealed``: a substantive difference. Only these go to the agent.

Clauses are aligned by reference first. Clauses left unmatched (e.g. after renumbering) are
paired by content similarity so a moved paragraph is not reported as repealed-plus-new.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from regcomp.ingest.normalize import for_diff
from regcomp.ingest.structure import ParsedClause, ParsedDocument

RENUMBER_MIN_SIMILARITY = 0.9


@dataclass
class ClauseChange:
    change_class: str  # unchanged | cosmetic | modified | new | repealed
    old_ref: str | None
    new_ref: str | None
    old_text: str | None
    new_text: str | None
    similarity: float


def own_text(clause: ParsedClause, doc: ParsedDocument) -> str:
    """The clause's text without its sub-clauses (children start inside its span)."""
    child_starts = [
        c.char_start
        for c in doc.clauses
        if c.parent_ref == clause.ref and c.char_start > clause.char_start
    ]
    end = min(child_starts) if child_starts else clause.char_end
    return doc.text[clause.char_start : end].strip()


def diff(old: ParsedDocument, new: ParsedDocument) -> list[ClauseChange]:
    old_own = {c.ref: own_text(c, old) for c in old.clauses}
    new_own = {c.ref: own_text(c, new) for c in new.clauses}
    changes: list[ClauseChange] = []

    for ref in [c.ref for c in new.clauses if c.ref in old_own]:
        a, b = old_own[ref], new_own[ref]
        if a == b:
            cls = "unchanged"
        elif for_diff(a) == for_diff(b):
            cls = "cosmetic"
        else:
            cls = "modified"
        changes.append(ClauseChange(cls, ref, ref, a, b, _ratio(a, b)))

    only_old = [r for r in old_own if r not in new_own]
    only_new = [r for r in new_own if r not in old_own]
    for nref in only_new:
        best = max(only_old, key=lambda o: _ratio(old_own[o], new_own[nref]), default=None)
        score = _ratio(old_own[best], new_own[nref]) if best else 0.0
        if best and score >= RENUMBER_MIN_SIMILARITY:
            only_old.remove(best)
            same = for_diff(old_own[best]) == for_diff(new_own[nref])
            cls = "cosmetic" if same else "modified"
            changes.append(ClauseChange(cls, best, nref, old_own[best], new_own[nref], score))
        else:
            changes.append(ClauseChange("new", None, nref, None, new_own[nref], score))
    for oref in only_old:
        changes.append(ClauseChange("repealed", oref, None, old_own[oref], None, 0.0))
    return changes


def substantive(changes: list[ClauseChange]) -> list[ClauseChange]:
    return [c for c in changes if c.change_class in ("modified", "new", "repealed")]


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, for_diff(a), for_diff(b), autojunk=False).ratio()
