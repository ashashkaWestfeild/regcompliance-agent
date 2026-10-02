"""Deterministic text comparison between an obligation and the policy (no model).

Bank policies restate much of the regulation almost word for word. Where that is so, code can
compare the two sentences directly and say exactly what differs, which a small judge model does
unreliably:

- ``same``: the policy states the obligation near verbatim, same numbers, same force.
- ``number_differs``: near-verbatim text, but a number of the obligation is not in the policy
  sentence (a threshold, period or percentage was changed).
- ``optional``: the obligation is mandatory and the matching policy sentence says "may".
- ``adds_words``: closely matching text with a limiting phrase inserted in the policy sentence
  that the obligation does not have (a possible narrower scope).
- ``no_similar_text``: nothing in the policy resembles the obligation's wording. That is not
  proof of a gap (the policy may paraphrase), only the absence of this evidence.

The comparison is used to sort the judge's output into tiers, never to hide a finding.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

NEAR = 0.6  # share of the obligation's word pairs found in one policy passage: "near verbatim"
CLOSE = 0.5  # enough shared wording to look for an inserted qualifier
ABSENT = 0.35  # below this, nothing in the policy resembles the obligation's wording
MIN_INSERT = 3  # inserted policy words that count as an added phrase
# Words that make an inserted phrase a condition or a limit rather than a rewording.
_LIMITING = re.compile(
    r"\b(?:only|solely|except|excluding|other than|unless|provided|subject to|if|where|when|"
    r"in case of|at the time of|identified|limited to|up to|not exceeding)\b",
    re.I,
)

_STOP = frozenset(
    {
        "the", "a", "an", "of", "to", "and", "or", "in", "for", "by", "on", "with", "as", "is",
        "be", "shall", "such", "that", "this", "any", "at", "from", "it", "its", "their", "which",
        "bank", "banks", "re", "res", "regulated", "entity", "entities", "may", "will", "should",
        "must",
    }
)  # fmt: skip
_MARKER = re.compile(
    r"^\s*(?:\(?[0-9ivxlc]{1,5}\)|[0-9]{1,3}\.|[a-z]{1,2}\)|[ivxlc]{1,5}\.|[a-z]\.)\s*", re.I
)
_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90,
}  # fmt: skip
_SCALES = {
    "hundred": 100,
    "thousand": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "crore": 10_000_000,
}
# A number that points at another provision or names an instrument is not a requirement.
_REFERENCE = re.compile(
    r"(?:paragraphs?|paras?|clauses?|sub-?clauses?|sections?|sub-?sections?|rules?|sub-?rules?|"
    r"chapters?|annex(?:ure)?|schedules?|regulations?|notifications?|unscrs?|resolutions?|"
    r"forms?|fema|articles?)\s*(?:no\.?\s*)?(?:\(?[0-9ivxlc]+[a-z]?\)?(?:\s*(?:,|and|or|to|&)\s*)?)+",
    re.I,
)
_YEAR = re.compile(r"\b(?:19|20)\d\d\b")
_ACT_NO = re.compile(r"\(?\s*\d+\s+of\s+(?:19|20)\d\d\s*\)?")  # "(18 of 2016)"
_BRACKETED = re.compile(r"\((?:[0-9]{1,3}|[ivxlc]{1,6}|[a-z]{1,2})\)", re.I)
_DIGITS = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[a-z]+", re.I)
_SENTENCE = re.compile(r"[^\n.;]+(?:[.;]|\n|$)")
_TOKEN = re.compile(r"\w+")


def _content(text: str) -> list[str]:
    """Content words, with every number replaced by "#": a changed number must not make two
    sentences look less alike, or the changed sentence would escape the comparison."""
    return [
        "#" if w[0].isdigit() or w in _UNITS or w in _SCALES else w
        for w in re.findall(r"[a-z0-9]+", text.lower())
        if w not in _STOP
    ]


def _pairs(text: str) -> set[tuple[str, str]]:
    w = _content(text)
    return {(w[i], w[i + 1]) for i in range(len(w) - 1)}


def body(quote: str) -> str:
    """The sentence without its list marker ("(2) ", "iv) ", "21. ")."""
    return _MARKER.sub("", quote or "", count=1).strip()


def numbers(text: str) -> set[str]:
    """The requirement numbers in `text` as plain integers / decimals: digits and number words
    ("fifty thousand" -> 50000, "ten" -> 10), without cross-references, years and list markers."""
    text = _ACT_NO.sub(" ", _REFERENCE.sub(" ", body(text)))
    text = _BRACKETED.sub(" ", _YEAR.sub(" ", text))
    out = set()
    for m in _DIGITS.findall(text):
        value = m.replace(",", "").rstrip(".")
        out.add(str(int(float(value))) if float(value).is_integer() else value)
    out.discard("1")  # "one of", "(1)", "any one": never a threshold on its own
    words = _WORD.findall(_DIGITS.sub(" | ", text).lower())
    run = None
    for w in words + ["|"]:
        if w in _UNITS:
            run = (run or 0) + _UNITS[w] if run is None or run < 100 else run + _UNITS[w]
        elif w in _SCALES and run is not None:
            run *= _SCALES[w]
        else:
            if run is not None and run != 1:
                out.add(str(run))
            run = None
    return out


def force(text: str) -> str | None:
    """ "must" if the sentence imposes a duty, "may" if it only permits, None if neither."""
    if re.search(
        r"\b(?:shall|must|should|is required to|are required to|has to|have to)\b", text, re.I
    ):
        return "must"
    return "may" if re.search(r"\bmay\b", text, re.I) else None


@dataclass
class Evidence:
    kind: str  # same | number_differs | optional | adds_words | no_similar_text | loose
    overlap: float
    start: int  # the policy passage compared (character span), -1 if none
    end: int
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "overlap": round(self.overlap, 2),
            "char_start": self.start,
            "char_end": self.end,
            "detail": self.detail,
        }


class Comparer:
    """Finds, for an obligation sentence, the policy passage that restates it most closely and
    reports what differs. Built once per policy."""

    def __init__(self, policy_text: str):
        self.text = policy_text
        sents = [
            (m.start(), m.end())
            for m in _SENTENCE.finditer(policy_text)
            if len(m.group().strip()) > 25
        ]
        self.windows = sents + [(a[0], b[1]) for a, b in zip(sents, sents[1:], strict=False)]
        self.pairs = [_pairs(policy_text[a:b]) for a, b in self.windows]

    def closest(self, quote: str) -> tuple[int, int, float]:
        want = _pairs(body(quote))
        if len(want) < 3:
            return -1, -1, 0.0
        best = max(range(len(self.windows)), key=lambda i: len(want & self.pairs[i]))
        a, b = self.windows[best]
        return a, b, len(want & self.pairs[best]) / len(want)

    def compare(self, quote: str, modality: str) -> Evidence:
        start, end, overlap = self.closest(quote)
        if overlap < ABSENT:
            return Evidence("no_similar_text", overlap, start, end)
        passage, sentence = self.text[start:end], body(quote)
        if overlap < NEAR:
            added = inserted(sentence, passage) if overlap >= CLOSE else []
            if added:
                detail = "policy adds: " + "; ".join(added)
                return Evidence("adds_words", overlap, start, end, detail)
            return Evidence("loose", overlap, start, end)
        missing = numbers(sentence) - numbers(passage)
        if missing:
            other = sorted(numbers(passage) - numbers(sentence), key=float)
            detail = f"obligation: {', '.join(sorted(missing, key=float))}; policy: " + (
                ", ".join(other) if other else "no number"
            )
            return Evidence("number_differs", overlap, start, end, detail)
        if modality != "may" and force(sentence) == "must" and force(passage) == "may":
            return Evidence("optional", overlap, start, end, "policy sentence says 'may'")
        added = inserted(sentence, passage)
        if added:
            return Evidence("adds_words", overlap, start, end, "policy adds: " + "; ".join(added))
        return Evidence("same", overlap, start, end)


def inserted(obligation: str, passage: str) -> list[str]:
    """Limiting phrases (a condition, an exception, a "only ...") of at least MIN_INSERT content
    words that the policy passage has inside the part that otherwise matches the obligation.
    Text before and after the matched part is ignored, and so is plain rewording."""
    a = [w.lower() for w in _TOKEN.findall(obligation)]
    tokens = list(_TOKEN.finditer(passage))
    b = [t.group().lower() for t in tokens]
    ops = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    equal = [op for op in ops if op[0] == "equal" and op[2] - op[1] >= 2]
    if len(equal) < 2:
        return []
    first, last = equal[0][3], equal[-1][4]
    out = []
    for tag, _, _, j1, j2 in ops:
        if tag in ("insert", "replace") and first <= j1 and j2 <= last:
            words = [w for w in b[j1:j2] if w not in _STOP]
            phrase = passage[tokens[j1].start() : tokens[j2 - 1].end()]
            if len(words) >= MIN_INSERT and _LIMITING.search(phrase):
                out.append(phrase)
    return out


def sweep(regulation, comparer: Comparer) -> list[dict]:
    """Every regulation sentence that states a number and has a near-verbatim policy sentence
    without that number. Independent of obligation extraction: an explanation or a definition
    that carries a threshold is checked even if no obligation was extracted from it."""
    out = []
    for m in _SENTENCE.finditer(regulation.text):
        sentence = m.group().strip()
        words = [w for w in _content(sentence) if w != "#"]
        if len(sentence) < 40 or len(words) < 6 or not numbers(sentence):
            continue  # too short, or mostly a reference number / date line
        found = comparer.compare(sentence, "must")
        if found.kind != "number_differs":
            continue
        clause = max(
            (c for c in regulation.clauses if c.char_start <= m.start() < c.char_end),
            key=lambda c: c.depth,
            default=None,
        )
        out.append(
            {
                "ref": clause.ref if clause else None,
                "reg_start": m.start(),
                "reg_end": m.end(),
                "sentence": sentence,
                "evidence": found,
            }
        )
    return out
