"""Split a parsed document into LLM-sized units along its own clause structure.

A top-level clause that fits in MAX_CHARS is one unit. A longer one is split into its direct
children; each child keeps the parent's lead-in as read-only context ("The bank shall ensure:"),
because a sub-clause like "(2) within 10 days" is meaningless without it. Quotes returned by the
model must come from the unit's own text, never from the context.
"""

import re
from dataclasses import dataclass

from regcomp.change.diff import own_text
from regcomp.ingest.structure import ParsedClause, ParsedDocument

MAX_CHARS = 2500
# Deterministic pre-filter: only text with normative wording goes to the model.
NORMATIVE = re.compile(
    r"\b(shall|must|may|should|will|is to be|are to be|has to|have to|required|responsible|"
    r"not permitted|prohibited|ensure)\b",
    re.IGNORECASE,
)
# Clauses in a section titled "Definitions" define terms ("'X' means ..."). They rarely say
# "shall", yet a definition fixes what an obligation requires (who counts, which threshold), so
# they are extracted with their own prompt, one leaf definition per unit.
DEFINITIONS_SECTION = re.compile(r"\bdefinitions?\b", re.IGNORECASE)
DEFINES = re.compile(r"\b(means|mean|includes?|shall include|is the|are the)\b", re.IGNORECASE)


@dataclass
class Unit:
    ref: str
    clause_ref: str  # clause the unit belongs to (for the clause_id foreign key)
    text: str  # quotable text: a verbatim slice of the document
    start: int  # character offset of `text` in the document
    context: str  # read-only lead-in from the parent (may be empty)
    kind: str = "provision"  # provision | definition


def units(doc: ParsedDocument, max_chars: int = MAX_CHARS) -> list[Unit]:
    children: dict[str, list[ParsedClause]] = {}
    for c in doc.clauses:
        if c.parent_ref:
            children.setdefault(c.parent_ref, []).append(c)

    out: list[Unit] = []

    def visit(c: ParsedClause, context: str) -> None:
        kind = "definition" if DEFINITIONS_SECTION.search(c.section or "") else "provision"
        # Definitions always split to leaves: each defined term (or sub-case) is its own unit.
        whole = len(c.quote) <= max_chars and kind == "provision"
        if whole or not children.get(c.ref):
            text = c.quote[:max_chars] if len(c.quote) > max_chars else c.quote
            out.append(Unit(c.ref, c.ref, text, c.char_start, context, kind))
            return
        lead = own_text(c, doc)
        if lead:
            out.append(Unit(f"{c.ref}#lead", c.ref, lead, c.char_start, context, kind))
        for child in children[c.ref]:
            visit(child, (context + " " + lead).strip()[-600:])

    for c in doc.clauses:
        if c.depth == 1:
            visit(c, "")
    return [
        u
        for u in out
        if NORMATIVE.search(u.text)
        or (u.kind == "definition" and len(u.text) >= 50 and DEFINES.search(u.text))
    ]
