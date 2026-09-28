"""Turn an ordered list of text blocks into a numbered clause tree with verbatim spans.

RBI Directions number paragraphs ``1.``, ``2.`` ... and nest sub-clauses as ``(1)``, ``(i)``,
``(a)`` in varying orders (definitions go ``5. (1) (i) (a)``, other paragraphs ``N. (a) (i)``).
A stack of marker *types* handles any order: a marker whose type is already open closes
everything below it and becomes a sibling; a new type opens a child.

Bank policies add other styles: ``a)``, ``iv.``, and decimal numbering (``2.2.8``). Marker
variants are recognised for detection only; the stored text is never rewritten. Decimal numbers
nest by their own components (``2.2.8`` is a child of ``2.2``).

Unmarked blocks ("Explanation: ...", "Provided that ...") belong to the deepest open clause.
Every clause span runs from its own first block to the start of the next clause at the same or
a higher level, so ``text[start:end] == quote`` holds by construction.
"""

import re
from dataclasses import dataclass, field

from regcomp.ingest.normalize import canonical

_DEC = re.compile(r"^(\d{1,2}(?:\.\d{1,2})+)\.?\s+")
# "121A." is how RBI numbers a paragraph inserted by an amendment (seen in 2026 amendments).
_PARA = re.compile(r"^(\d{1,3}[A-Z]?)\.\s+")
_LABEL = r"[0-9]{1,2}|[a-z]{1,2}|[ivxl]{1,6}"
_PAREN = re.compile(
    rf"^(?:\((?P<p>{_LABEL})\)\s*|(?P<r>{_LABEL})\)\s+|(?P<d>[a-z]{{1,2}}|[ivxl]{{1,6}})\.\s+)"
)
_ROMAN = re.compile(r"^[ivxl]+$")
# "(ia)" is a sub-clause inserted after "(i)" by an amendment: a roman sibling, not a letter.
_ROMAN_INSERT = re.compile(r"^(?P<base>[ivxl]{1,6})(?P<suffix>[a-z])$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50}


@dataclass
class Block:
    """One paragraph-like unit from the source, in reading order."""

    text: str
    is_heading: bool = False
    amended_by: list[str] = field(default_factory=list)  # e.g. "Inserted with effect from ..."
    # (source item index, offset of that item's text inside this block's canonical text)
    sources: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class ParsedClause:
    ref: str  # "38", "38(2)", "5(1)(iv)(a)"
    label: str  # the marker itself: "38", "2", "iv", "a"
    kind: str  # "para" | "dec" | "num" | "roman" | "alpha"
    depth: int  # 1 for numbered paragraphs; number of components for decimals
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
    source_positions: dict[int, int] = field(default_factory=dict)  # source item -> char pos


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
    inserted = _ROMAN_INSERT.match(label)
    if inserted and open_types.get("roman") == inserted.group("base"):
        return "roman"
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
    seen: dict[str, int] = {}  # ref -> times used, for de-duplication
    base_depth = 1
    context: list[tuple[int, int, bool, str | None, str | None]] = []  # per block
    source_positions: dict[int, int] = {}

    pending: list[str] = []  # markers seen where no clause is open yet
    for block in blocks:
        text = canonical(block.text)
        if not text:
            continue
        start = offset

        if block.is_heading:
            # A marker on a heading ("[Chapter VI-A ..." inserted by an amendment) belongs to
            # the content it introduces: carry it to the next clause instead of dropping it.
            pending.extend(block.amended_by)
            boundaries.append((start, 0))
            stack.clear()
            open_nodes.clear()
            if text.lower().startswith("chapter"):
                chapter, section = text, None
            else:
                section = text
        else:
            dec = _DEC.match(text)
            para = None if dec else _PARA.match(text)
            paren = None if (dec or para) else _PAREN.match(text)
            if dec or para:
                number = (dec or para).group(1)
                depth = number.count(".") + 1
                parent_ref = _decimal_parent(number, seen) if dec else None
                ref = _unique(number, seen)
                kind = "dec" if dec else "para"
                base_depth = depth
                stack[:] = [(kind, number)]
                node = _new_node(ref, kind, parent_ref, chapter, section, start, depth=depth)
                boundaries.append((start, depth))
                opened.append(node)
                open_nodes[:] = [node]
                node["amended_by"].extend(pending)
                pending.clear()
            elif paren and stack:
                label = paren.group("p") or paren.group("r") or paren.group("d")
                kind = _classify(label, stack)
                types = [t for t, _ in stack]
                if kind in types[1:]:
                    cut = types.index(kind, 1)
                    del stack[cut:]
                    del open_nodes[cut:]
                parent = open_nodes[-1]
                stack.append((kind, label))
                depth = base_depth + len(stack) - 1
                ref = _unique(f"{parent['ref']}({label})", seen)
                node = _new_node(
                    ref,
                    kind,
                    parent["ref"],
                    chapter,
                    section,
                    start,
                    label=label,
                    depth=depth,
                )
                boundaries.append((start, depth))
                opened.append(node)
                open_nodes.append(node)
                node["amended_by"].extend(pending)
                pending.clear()
            # Unmarked block: nothing to open; it extends the deepest open clause.
            if block.amended_by and open_nodes:
                open_nodes[-1]["amended_by"].extend(block.amended_by)
            elif block.amended_by:
                pending.extend(block.amended_by)

        context.append((start, start + len(text), block.is_heading, chapter, section))
        for item, off in block.sources:
            source_positions[item] = start + off
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
    clauses.extend(_unnumbered(doc_text, clauses, context))
    clauses.sort(key=lambda c: c.char_start)
    return ParsedDocument(text=doc_text, clauses=clauses, source_positions=source_positions)


UNNUMBERED_MIN_CHARS = 80


def _unnumbered(doc_text, clauses, context) -> list[ParsedClause]:
    """Body text outside every numbered clause (e.g. lists under a sub-heading, annex prose)
    becomes clauses "U1", "U2", ... so nothing downstream silently loses it."""
    covered = sorted((c.char_start, c.char_end) for c in clauses if c.depth == 1)
    out: list[ParsedClause] = []
    run: list[tuple[int, int, str | None, str | None]] = []

    def flush():
        if run and sum(e - s for s, e, _, _ in run) >= UNNUMBERED_MIN_CHARS:
            s0, e0 = run[0][0], run[-1][1]
            ref = f"U{len(out) + 1}"
            out.append(
                ParsedClause(
                    ref=ref,
                    label=ref,
                    kind="unnumbered",
                    depth=1,
                    parent_ref=None,
                    chapter=run[0][2],
                    section=run[0][3],
                    char_start=s0,
                    char_end=e0,
                    quote=doc_text[s0:e0],
                )
            )
        run.clear()

    for start, end, is_heading, chapter, section in context:
        inside = any(cs <= start < ce for cs, ce in covered)
        if inside or is_heading:
            flush()
        else:
            run.append((start, end, chapter, section))
    flush()
    return out


def _unique(ref: str, seen: dict[str, int]) -> str:
    """Repeated numbering (e.g. a list restarting at "1.") gets "~2", "~3" suffixes."""
    seen[ref] = seen.get(ref, 0) + 1
    return ref if seen[ref] == 1 else f"{ref}~{seen[ref]}"


def _decimal_parent(number: str, seen: dict[str, int]) -> str | None:
    parts = number.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in seen:
            return prefix
    return None


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
