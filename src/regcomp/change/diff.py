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

Positional references are never trusted for alignment: unnumbered clauses are named "U1", "U2"
... and repeated numbers get "~2", "~3" suffixes in document order, so one inserted clause
renames every later one. Such clauses are paired by content (exact, then similar); found when
the diff was evaluated on nine more RBI Directions (27 Sep 2026).
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from regcomp.ingest.normalize import for_diff
from regcomp.ingest.structure import ParsedClause, ParsedDocument

RENUMBER_MIN_SIMILARITY = 0.9
POSITIONAL_MIN_SIMILARITY = 0.6  # same slot, edited text


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

    old_key = {r: for_diff(t) for r, t in old_own.items()}
    new_key = {r: for_diff(t) for r, t in new_own.items()}

    for ref in [c.ref for c in new.clauses if c.ref in old_own and not positional(c.ref)]:
        a, b = old_own[ref], new_own[ref]
        if a == b:
            changes.append(ClauseChange("unchanged", ref, ref, a, b, 1.0))
        elif old_key[ref] == new_key[ref]:
            changes.append(ClauseChange("cosmetic", ref, ref, a, b, 1.0))
        else:
            score = _ratio(old_key[ref], new_key[ref])
            changes.append(ClauseChange("modified", ref, ref, a, b, score))

    only_old = [r for r in old_own if r not in new_own or positional(r)]
    only_new = [r for r in new_own if r not in old_own or positional(r)]
    # Positional clauses whose text is unchanged (up to cosmetic differences): pair them first.
    by_key: dict[str, list[str]] = {}
    for r in only_old:
        if positional(r):
            by_key.setdefault(old_key[r], []).append(r)
    for nref in [r for r in only_new if positional(r)]:
        if by_key.get(new_key[nref]):
            oref = by_key[new_key[nref]].pop(0)
            only_old.remove(oref)
            only_new.remove(nref)
            cls = "unchanged" if old_own[oref] == new_own[nref] else "cosmetic"
            changes.append(ClauseChange(cls, oref, nref, old_own[oref], new_own[nref], 1.0))
    leftover = []
    for nref in only_new:
        best, score = _best_match(new_key[nref], only_old, old_key)
        if best and score >= RENUMBER_MIN_SIMILARITY:
            only_old.remove(best)
            cls = "cosmetic" if old_key[best] == new_key[nref] else "modified"
            changes.append(ClauseChange(cls, best, nref, old_own[best], new_own[nref], score))
        else:
            leftover.append(nref)
    for nref in leftover:
        # A positional clause edited in place: accept a looser match among positional ones.
        pool = [r for r in only_old if positional(r)] if positional(nref) else []
        best, score = _best_match(new_key[nref], pool, old_key, POSITIONAL_MIN_SIMILARITY)
        if best:
            only_old.remove(best)
            changes.append(
                ClauseChange("modified", best, nref, old_own[best], new_own[nref], score)
            )
        else:
            changes.append(ClauseChange("new", None, nref, None, new_own[nref], score))
    for oref in only_old:
        changes.append(ClauseChange("repealed", oref, None, old_own[oref], None, 0.0))
    return changes


def substantive(changes: list[ClauseChange]) -> list[ClauseChange]:
    return [c for c in changes if c.change_class in ("modified", "new", "repealed")]


def positional(ref: str) -> bool:
    """True for references that only encode document order ("U3", "137(1)~2")."""
    return "~" in ref or (ref.startswith("U") and ref[1:].isdigit())


def _best_match(
    key: str, candidates: list[str], keys: dict[str, str], floor: float = RENUMBER_MIN_SIMILARITY
) -> tuple[str | None, float]:
    """Most similar candidate, using difflib's cheap upper bounds to skip hopeless pairs."""
    best, best_score = None, 0.0
    for cand in candidates:
        other = keys[cand]
        shorter, longer = sorted((len(key), len(other)))
        if longer and 2 * shorter / (shorter + longer) < floor:
            continue  # length alone caps the ratio below the threshold
        sm = SequenceMatcher(None, key, other, autojunk=False)
        if sm.real_quick_ratio() < floor or sm.quick_ratio() < floor:
            continue
        score = sm.ratio()
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


def _ratio(a_key: str, b_key: str) -> float:
    return SequenceMatcher(None, a_key, b_key, autojunk=False).ratio()
