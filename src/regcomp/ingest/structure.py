"""Turn an ordered list of text blocks into a numbered clause tree with verbatim spans.

RBI Directions number paragraphs ``1.``, ``2.`` ... and nest sub-clauses as ``(1)``, ``(i)``,
``(a)`` in varying orders (definitions go ``5. (1) (i) (a)``, other paragraphs ``N. (a) (i)``).
A stack of marker *types* handles any order: a marker whose type is already open closes
everything below it and becomes a sibling; a new type opens a child.

Unmarked blocks ("Explanation: ...", "Provided that ...") belong to the deepest open clause.
Every clause span runs from its own first block to the start of the next clause at the same or
a higher level, so ``text[start:end] == quote`` holds by construction.
"""

import re
from dataclasses import dataclass, field

from regcomp.ingest.normalize import canonical

_PARA = re.compile(r"^(\d{1,3})\.\s+")
_PAREN = re.compile(r"^\(([0-9]{1,2}|[a-z]{1,2}|[ivxl]{1,6})\)\s*")
_ROMAN = re.compile(r"^[ivxl]+$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50}


@dataclass
class Block:
    """One paragraph-like unit from the source, in reading order."""

    text: str
    is_heading: bool = False
    amended_by: list[str] = field(default_factory=list)  # e.g. "Inserted with effect from ..."


@dataclass
class ParsedClause:
    ref: str  # "38", "38(2)", "5(1)(iv)(a)"
    label: str  # the marker itself: "38", "2", "iv", "a"
    kind: str  # "para" | "num" | "roman" | "alpha"
    depth: int  # 1 for numbered paragraphs
    parent_ref: str | None
    chapter: str | None
    section: str | None
    char_start: int
    char_end: int
    quote: str
    amended_by: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    text: str  # canonical text; every clause quote is a slice of it
    clauses: list[ParsedClause]


def _roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def _classify(label: str, stack: list[tuple[str, str]]) -> str:
    """Decide the marker type, resolving the (i)/(v)/(x) letter-vs-roman ambiguity."""
    if label.isdigit():
        return "num"
    open_types = {t: lab for t, lab in stack}
    if _ROMAN.match(label):
        prev_alpha = open_types.get("alpha")
        # "(i)" right after "(h)" is a letter, not the roman numeral one.
        if prev_alpha and len(label) == 1 and ord(label) == ord(prev_alpha) + 1:
            return "alpha"
        prev_roman = open_types.get("roman")
        if prev_roman and _roman_to_int(label) == _roman_to_int(prev_roman) + 1:
            return "roman"
        if len(label) > 1 or label == "i":
            return "roman"
        return "alpha" if prev_alpha else "roman"
    return "alpha"


def build(blocks: list[Block]) -> ParsedDocument:
    parts: list[str] = []
    offset = 0
    chapter = section = None
    # Open clause path: (type, label) per level; nodes hold span starts until closed.
    stack: list[tuple[str, str]] = []
    opened: list[dict] = []  # clause dicts in document order
    open_nodes: list[dict] = []  # parallel to stack
    boundaries: list[tuple[int, int]] = []  # (position, depth) where clauses at >= depth end

    for block in blocks:
        text = canonical(block.text)
        if not text:
            continue
        start = offset

        if block.is_heading:
            boundaries.append((start, 0))
            stack.clear()
            open_nodes.clear()
            if text.lower().startswith("chapter"):
                chapter, section = text, None
            else:
                section = text
        else:
            para = _PARA.match(text)
            paren = None if para else _PAREN.match(text)
            if para:
                stack[:] = [("para", para.group(1))]
                node = _new_node(para.group(1), "para", None, chapter, section, start)
                boundaries.append((start, 1))
                opened.append(node)
                open_nodes[:] = [node]
            elif paren and stack:
                label = paren.group(1)
                kind = _classify(label, stack)
                types = [t for t, _ in stack]
                if kind in types:
                    cut = types.index(kind)
                    del stack[cut:]
                    del open_nodes[cut:]
                parent = open_nodes[-1]
                stack.append((kind, label))
                node = _new_node(
                    f"{parent['ref']}({label})",
                    kind,
                    parent["ref"],
                    chapter,
                    section,
                    start,
                    label=label,
                    depth=len(stack),
                )
                boundaries.append((start, len(stack)))
                opened.append(node)
                open_nodes.append(node)
            # Unmarked block: nothing to open; it extends the deepest open clause.
            if block.amended_by and open_nodes:
                open_nodes[-1]["amended_by"].extend(block.amended_by)

        parts.append(text)
        offset += len(text) + 1  # "\n" separator

    doc_text = "\n".join(parts)
    boundaries.append((len(doc_text) + 1, 0))

    clauses = []
    for node in opened:
        end = next(pos for pos, d in boundaries if pos > node["start"] and d <= node["depth"])
        end = min(end - 1, len(doc_text))  # drop the trailing separator
        clauses.append(
            ParsedClause(
                ref=node["ref"],
                label=node["label"],
                kind=node["kind"],
                depth=node["depth"],
                parent_ref=node["parent"],
                chapter=node["chapter"],
                section=node["section"],
                char_start=node["start"],
                char_end=end,
                quote=doc_text[node["start"] : end],
                amended_by=node["amended_by"],
            )
        )
    return ParsedDocument(text=doc_text, clauses=clauses)


def _new_node(ref, kind, parent, chapter, section, start, label=None, depth=1) -> dict:
    return {
        "ref": ref,
        "label": label or ref,
        "kind": kind,
        "parent": parent,
        "chapter": chapter,
        "section": section,
        "start": start,
        "depth": depth,
        "amended_by": [],
    }
