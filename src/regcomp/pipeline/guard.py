"""Code-level scan of an uploaded document for text that tries to instruct an automated reader.

The extraction model is also asked to flag such text, but a model can miss it (second dev key,
3 Oct 2026: a differently worded instruction was not flagged). This scan does not depend on a
model. It is written from the general principle only: a policy states rules for the bank; it has
no reason to address the program that reads it or to say what that program should conclude.

A sentence is flagged when it
- tells the reader to drop its instructions            (override)
- addresses a program that is reading this document    (addressed_reader, instruction_label)
- says what verdict to give                            (steer_verdict)
- tells the reader not to report findings              (suppress)
- uses prompt vocabulary                               (role)
A flag is a report for a person. It changes no verdict: the text is data either way.
"""

import re

_READER = (
    r"(?:ai|a\.i\.|artificial intelligence|(?:large )?language model|llm|chatbot|assistant|model|"
    r"bot|agent|algorithm|automated\s+(?:\w+\s+)?(?:checker|reviewer|reader|tool|agent|system|"
    r"assessor|analy[sz]er|process|pipeline)|(?:compliance|review|audit)\s+(?:tool|software|"
    r"engine))"
)
_READING = (
    r"(?:reading|processing|reviewing|analy[sz]ing|assessing|checking|evaluating|parsing|scanning)"
)
RULES = {
    "override": re.compile(
        r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|"
        r"all|any|your)\b[^.\n]{0,30}\b(?:instruction|prompt|rule|guideline|direction)s?\b",
        re.I,
    ),
    "addressed_reader": re.compile(rf"\b{_READER}\b[^.\n]{{0,80}}\b{_READING}\s+this\b", re.I),
    "instruction_label": re.compile(
        rf"\b(?:instruction|note|message|directive|command|attention)s?\s*(?:for|to|:)\s*"
        rf"(?:any|the|an?|all)?\s*{_READER}\b",
        re.I,
    ),
    "steer_verdict": re.compile(
        r"\b(?:mark|treat|classify|rate|report|consider|deem|score|label|record|certify)\b"
        r"[^.\n]{0,80}\bas\s+(?:fully\s+|being\s+)?(?:compliant|covered|satisfied|met|passed|"
        r"complete|no\s+gaps?)\b",
        re.I,
    ),
    "suppress": re.compile(
        r"\bdo\s+not\s+(?:flag|raise|list|report|mention|record|identify)\b[^.\n]{0,60}\b(?:gap|"
        r"exception|finding|issue|deficienc\w*|non-?compliance|violation)s?\b",
        re.I,
    ),
    "role": re.compile(r"\b(?:system prompt|you are now|as an ai\b|new instructions?\s*:)", re.I),
}
_BREAK = re.compile(r"[.\n]")


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    """The sentence around a match: back to the previous full stop or line break, forward to
    the next."""
    before = [m.end() for m in _BREAK.finditer(text, 0, start)]
    after = _BREAK.search(text, end)
    a = before[-1] if before else 0
    b = after.end() if after else len(text)
    while a < b and text[a].isspace():
        a += 1
    return a, b


def scan(text: str) -> list[dict]:
    """[{text, char_start, rule, by}] for each sentence that tries to instruct the reader, in
    document order, one entry per sentence (rule names joined when several match)."""
    found: dict[tuple[int, int], list[str]] = {}
    for name, pattern in RULES.items():
        for m in pattern.finditer(text):
            found.setdefault(_sentence(text, m.start(), m.end()), []).append(name)
    return [
        {
            "unit": "scan",
            "text": text[a:b].strip(),
            "char_start": a,
            "rule": "+".join(sorted(set(names))),
            "by": "rule",
        }
        for (a, b), names in sorted(found.items())
    ]
