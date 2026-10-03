"""Second pass over "covered" verdicts: does the supporting policy text carry the duty as RBI
states it? (D2 attempt; eval/reports/d2_error_analysis.md.)

Two code rules, no model:
  - definition support: the passage the judge relied on defines a term ("'X' means ...") rather
    than obliging anyone to do it;
  - added modifier: in a policy sentence that follows RBI's sentence closely, words are added
    directly in front of one of RBI's own words, and those words appear nowhere in RBI's
    sentence ("identify savings accounts" for "identify accounts"). Found by word alignment, not
    by a list of qualifier words; a reordering of RBI's own words is not an addition.
Findings go to the review queue unless the development gates in eval/d2_bar.md allow more.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from regcomp.pipeline.verify import _MARKER, _STOP, CLOSE

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:'[a-z]+)?", re.I)  # "pre-existing" is one word
MAX_ADDED = 3  # a modifier in front of a noun is short; longer insertions are headers or names
# Closed-class English words (grammar, not qualifiers): articles and determiners, negation,
# pronouns, prepositions, conjunctions, auxiliaries and modals. A modifier neither starts nor
# ends with one, and the word it stands in front of is not one.
_FUNCTION = _STOP | frozenset(
    {
        "no", "not", "nor", "all", "each", "every", "some", "other", "these", "those", "there",
        "he", "she", "they", "them", "his", "her", "we", "our", "you", "your", "who", "whom",
        "whose", "what", "where", "when", "while", "whether", "if", "but", "so", "than", "then",
        "into", "onto", "upon", "under", "over", "about", "after", "before", "between", "during",
        "through", "within", "without", "against", "per", "via", "are", "was", "were", "been",
        "being", "has", "have", "had", "do", "does", "did", "can", "could", "would", "might",
    }
)  # fmt: skip
# A definition: a named term of at most eight words, then a defining verb. The term is a name:
# quoted ("'Customer' means") or written with capitals ("KYC Templates means"), so an ordinary
# sentence that happens to contain "means" is not a definition.
_DEFINITION = re.compile(
    r"^\s*(?P<term>[\"'‘“]?(?:[\w/()-]+\s+){0,7}[\w/()-]+[\"'’”]?)\s+"
    r"(?:means|shall mean|refers to|is defined as|has the (?:same )?meaning)\b",
    re.I,
)
_QUOTES = "\"'‘’“”"
_NUMBERED = re.compile(r"^\s*(?:\d+(?:\.\d+)+|[ivxlc]{1,5}\.|\(?[a-z]{1,2}\)|[a-z]\.)\s*", re.I)
_SENTENCES = re.compile(r"[^.;:]+[.;:]?")


def is_definition(passage: str) -> bool:
    """True when the passage opens by defining a term ("'On-going Due Diligence' means ...")."""
    text = _NUMBERED.sub("", _MARKER.sub("", passage.strip()), count=1)
    m = _DEFINITION.match(text)
    if not m:
        return False
    term = m.group("term")
    if any(q in term for q in _QUOTES):
        return True
    return all(w[0].isupper() or w[0].isdigit() for w in term.split())


def definition_support(obligation: str, passage: str) -> bool:
    """The judge relied on a definition for a duty. When RBI's own text is a definition, a
    policy definition is the right support and this is not a finding."""
    return is_definition(passage) and not is_definition(obligation)


def _tokens(text: str) -> list[str]:
    """Lower-case words; a possessive is the same word ("owner's" is "owner")."""
    return [t.lower().removesuffix("'s") for t in _TOKEN.findall(text.replace("’", "'"))]


def _content(words: list[str]) -> list[str]:
    return [w for w in words if w not in _STOP and not w.isdigit()]


@dataclass
class Modifier:
    added: str  # the words the policy adds
    before: str  # RBI's word they stand in front of
    sentence: str  # the policy sentence
    overlap: float  # share of RBI's content words aligned in that sentence


def added_modifiers(obligation: str, passage: str) -> list[Modifier]:
    """Words a policy sentence adds directly in front of one of RBI's own content words, inside
    the part of the sentence that follows RBI's wording. Only words absent from RBI's sentence
    count, and only when the sentence aligns with at least CLOSE of RBI's content words."""
    a = _tokens(obligation)
    rbi_words = set(a)
    need = len(_content(a)) or 1
    best: list[Modifier] = []
    for m in _SENTENCES.finditer(passage):
        sentence = m.group().strip()
        b = _tokens(sentence)
        ops = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
        aligned = _content([w for tag, i1, i2, _, _ in ops if tag == "equal" for w in a[i1:i2]])
        overlap = len(aligned) / need
        if overlap < CLOSE:
            continue
        found = []
        for n, (tag, i1, _, j1, j2) in enumerate(ops):
            if tag != "insert" or n == 0 or ops[n - 1][0] != "equal":
                continue
            if n + 1 >= len(ops) or ops[n + 1][0] != "equal":
                continue
            span = b[j1:j2]
            noun = a[i1] if i1 < len(a) else ""
            if (
                len(span) > MAX_ADDED
                or span[0] in _FUNCTION
                or span[-1] in _FUNCTION
                or not noun
                or noun in _FUNCTION
                or any(any(ch.isdigit() for ch in w) for w in span)
            ):
                continue
            if [w for w in span if w not in _FUNCTION and w not in rbi_words]:
                found.append(Modifier(" ".join(span), noun, sentence, round(overlap, 2)))
        if found and (not best or overlap > best[0].overlap):
            best = found
    return best
