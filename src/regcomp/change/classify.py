"""What a clause change means for a bank, decided by rules on the changed words.

The diff says *that* a clause changed (modified / new / repealed). This step says what kind of
change it is, from the words that were added and removed, before any model is involved:

- ``advisory``: the new words only permit something ("may") and add no duty. The bank is not out
  of compliance; its policy may be updated to use the option. Never a gap.
- ``new_duty``: the new words impose or forbid something ("shall", "must", "shall not").
- ``threshold``: a number changed (a limit, a period, a percentage).
- ``relaxed``: a duty was removed and none was added.
- ``repealed``: the clause is gone.
- ``wording``: none of the above; reviewed like a changed duty, because a quiet edit can matter.

Everything except ``advisory`` is sent on for re-analysis.
"""

import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

from regcomp.change.diff import ClauseChange

_WORD = re.compile(r"\w+(?:[.,]\d+)*%?|[^\w\s]")
_DUTY = re.compile(r"\b(shall|must|required to|is to|are to|not permitted|prohibited)\b", re.I)
_MAY = re.compile(r"\bmay\b(?!\s+not\b)", re.I)
_NUMBER = re.compile(
    r"\b\d[\d,.]*%?|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|"
    r"thirty|fifty|hundred|thousand|lakh|crore)\b",
    re.I,
)
_TERM = re.compile(r"^\W*\(?[\w.]*\)?\s*[‘'\"“]([^’'\"”]{2,80})[’'\"”]")

REANALYSE = ("new_duty", "threshold", "relaxed", "repealed", "wording")


@dataclass
class Classified:
    change_class: str  # from the diff: modified | new | repealed
    ref: str  # the clause reference in the new version (old version if repealed)
    effect: str  # advisory | new_duty | threshold | relaxed | repealed | wording
    added: str  # words present only in the new text
    removed: str  # words present only in the old text
    defined_term: str | None  # set when the clause defines a term
    summary: str
    reanalyse: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _spans(old: str, new: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Character spans of the words only in `new` (added) and only in `old` (removed), by
    word-level alignment of the two versions."""
    a, b = list(_WORD.finditer(old)), list(_WORD.finditer(new))
    matcher = SequenceMatcher(None, [m.group() for m in a], [m.group() for m in b], autojunk=False)
    added, removed = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed.append((a[i1].start(), a[i2 - 1].end()))
        if tag in ("replace", "insert"):
            added.append((b[j1].start(), b[j2 - 1].end()))
    return added, removed


def word_delta(old: str, new: str) -> tuple[str, str]:
    """(added, removed) as verbatim text; separate edits are joined with " … "."""
    added, removed = _spans(old, new)
    return " … ".join(new[s:e] for s, e in added), " … ".join(old[s:e] for s, e in removed)


def defined_term(text: str) -> str | None:
    """The term a definition clause defines: the quoted phrase it opens with."""
    m = _TERM.match(text or "")
    return m.group(1).strip() if m else None


def _governing_modal(text: str, spans: list[tuple[int, int]]) -> str | None:
    """The modal verb of the sentence(s) the added words sit in ("may" or a duty word), for an
    insertion that carries no modal of its own."""
    found = None
    for at, _ in spans:
        start = max(text.rfind(". ", 0, at), text.rfind(";", 0, at)) + 1
        end = min(
            (p for p in (text.find(". ", at), text.find(";", at)) if p >= 0), default=len(text)
        )
        sentence = text[start:end]
        if _DUTY.search(sentence):
            return "duty"
        if _MAY.search(sentence):
            found = "may"
    return found


def classify(change: ClauseChange, in_definitions: bool = False) -> Classified:
    old, new = change.old_text or "", change.new_text or ""
    ref = change.new_ref or change.old_ref or ""
    term = defined_term(new or old) if in_definitions else None
    if change.change_class == "repealed":
        return Classified("repealed", ref, "repealed", "", old, term, "Clause removed.", True)
    added_spans, _ = ([(0, len(new))], []) if change.change_class == "new" else _spans(old, new)
    added, removed = (new, "") if change.change_class == "new" else word_delta(old, new)

    numbers_changed = sorted(set(_NUMBER.findall(added))) != sorted(set(_NUMBER.findall(removed)))
    modal = "duty" if _DUTY.search(added) else "may" if _MAY.search(added) else None
    modal = modal or _governing_modal(new, added_spans)
    if _DUTY.search(removed) and not added.strip():
        effect = "relaxed"
    elif modal == "duty":
        effect = "threshold" if numbers_changed and removed else "new_duty"
    elif modal == "may" and not _DUTY.search(removed):
        effect = "advisory"
    elif numbers_changed:
        effect = "threshold"
    else:
        effect = "wording"

    what = {
        "advisory": "adds an option the bank may use; no new duty",
        "new_duty": "adds or changes a duty",
        "threshold": "changes a number (limit, period or percentage)",
        "relaxed": "removes a duty",
        "wording": "changes wording; meaning to be checked",
    }[effect]
    subject = f"the definition of '{term}'" if term else f"clause {ref}"
    summary = f"The amendment to {subject} {what}."
    if added:
        summary += f' Added: "{added[:240]}".'
    if removed:
        summary += f' Removed: "{removed[:240]}".'
    return Classified(
        change.change_class, ref, effect, added, removed, term, summary, effect in REANALYSE
    )
