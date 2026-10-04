"""Conflicting statements inside one policy: two passages that restate the same RBI sentence but
give different numbers or periods for it (a planted example: the body says high-risk re-KYC every
two years, an annex says five). Code only, no model; a development analysis, not a pipeline stage.

For each RBI sentence that states a period or a percentage, the policy sentences that restate it
are found by wording (most of their content words appear in the RBI sentence, and they share at
least one distinctive word pair with it, counting the sentence before as a lead-in). Their
quantities are grouped by dimension (a period in days, or a percentage), by the risk grade named
next to them (high, medium, low or none) and by the customer type the sentence is about (company,
partnership, trust, association; a beneficial-owner threshold differs by type on purpose). A
group holding two or more different values is a conflict.
"""

import re
from dataclasses import dataclass

from regcomp.pipeline.verify import _SENTENCE, _UNITS, body

COVER = 0.5  # share of the policy sentence's content words found in the RBI sentence
MIN_WORDS = 4  # content words a policy sentence needs before it can restate anything

_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
_ADVERBS = {
    "half-yearly": 182, "half yearly": 182, "six-monthly": 180, "six monthly": 180,
    "quarterly": 91, "annually": 365, "yearly": 365, "annual": 365,
}  # fmt: skip
_NUMBER = r"\d+(?:\.\d+)?|" + "|".join(sorted(_UNITS, key=len, reverse=True))
_QUANTITY = re.compile(
    rf"\b(?P<num>{_NUMBER})\s*(?:\(\s*\d+\s*\)\s*)?(?:calendar\s+|working\s+|financial\s+)?"
    r"(?P<unit>days?|weeks?|months?|years?|per\s*cent|percent|%)",
    re.I,
)
_ADVERB = re.compile(r"\b(" + "|".join(map(re.escape, _ADVERBS)) + r")\b", re.I)
_GRADE = re.compile(
    r"\b(high|medium|low)[\s-]*risk\b|\brisk\s*(?:category\s*)?(high|medium|low)\b", re.I
)
_ENTITY = re.compile(
    r"\b(company|partnership|trust|unincorporated association|body of individuals)\b", re.I
)
_WORD = re.compile(r"[a-z]+")
# Words too common in KYC text to show that two sentences are about the same duty.
_GENERIC = frozenset(
    {
        "the", "a", "an", "of", "to", "and", "or", "in", "for", "by", "on", "with", "as",
        "is", "be", "shall", "such", "that", "this", "any", "at", "from", "it", "its",
        "their", "which", "bank", "banks", "re", "res", "regulated", "entity", "entities",
        "may", "will", "should", "must", "are", "was", "were", "has", "have", "been",
        "being", "not", "no", "all", "also", "other", "than", "every", "least", "once",
        "within", "after", "before", "into", "upon", "customer", "customers", "account",
        "accounts", "day", "days", "week", "weeks", "month", "months", "year", "years",
        "risk", "high", "low", "medium", "per", "cent", "percent", "case", "cases", "time",
        "times", "period", "periodic", "carried", "carry", "out", "done", "made", "under",
        "where", "when", "if",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Quantity:
    dimension: str  # "days" | "percent"
    value: float
    grade: str  # "high" | "medium" | "low" | "" (no risk grade named next to it)
    text: str
    entity: str = ""  # the customer type the sentence is about, if it names one


def _stem(word: str) -> str:
    word = word.replace("isation", "ization").replace("ised", "ized").replace("ise", "ize")
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _words(text: str) -> list[str]:
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _UNITS]


def _distinctive_pairs(text: str) -> set[frozenset]:
    """Neighbouring distinctive words, in either order ("updation of KYC" = "KYC updation")."""
    w = [x for x in _words(text) if _stem(x) not in {_stem(g) for g in _GENERIC}]
    return {frozenset((w[i], w[i + 1])) for i in range(len(w) - 1) if w[i] != w[i + 1]}


def _grade(text: str, start: int, end: int) -> str:
    """The risk grade right after the quantity ("two years for high-risk customers"), else the
    last one before it in the same sentence ("High-risk customers: at least once every two
    years"), else none."""
    after = _GRADE.search(text[end : end + 45])
    if after:
        return (after.group(1) or after.group(2)).lower()
    before = list(_GRADE.finditer(text[:start]))
    return (before[-1].group(1) or before[-1].group(2)).lower() if before else ""


def _entity(text: str) -> str:
    m = _ENTITY.search(text)
    return (
        m.group(1).lower().replace("body of individuals", "unincorporated association") if m else ""
    )


def quantities(text: str) -> list[Quantity]:
    """Periods (in days) and percentages stated in `text`, each with the risk grade beside it."""
    out, entity = [], _entity(text)
    for m in _QUANTITY.finditer(text):
        raw, unit = m.group("num").lower(), m.group("unit").lower()
        value = float(raw) if raw[0].isdigit() else float(_UNITS[raw])
        if unit.startswith(("per", "%")):
            dim = "percent"
        else:
            dim, value = "days", value * _DAYS[unit.rstrip("s")]
        out.append(Quantity(dim, value, _grade(text, m.start(), m.end()), m.group(), entity))
    for m in _ADVERB.finditer(text):
        days = float(_ADVERBS[m.group(1).lower()])
        out.append(Quantity("days", days, _grade(text, m.start(), m.end()), m.group(), entity))
    return out


def restates(rbi: str, sentence: str, lead_in: str = "") -> bool:
    """True when the policy sentence (with its lead-in) reads as a restatement of the RBI one."""
    own = set(_words(sentence)) - {_stem(g) for g in _GENERIC}
    if len(own) < MIN_WORDS - 2 or len(_words(sentence)) < MIN_WORDS:
        return False
    rbi_words = set(_words(rbi))
    if len(own & rbi_words) / len(own) < COVER:
        return False
    return bool(_distinctive_pairs(rbi) & _distinctive_pairs(lead_in + " " + sentence))


def sentences(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _SENTENCE.finditer(text) if len(m.group().strip()) > 25]


def conflicts(rbi_sentence: str, policy_text: str, spans: list[tuple[int, int]] | None = None):
    """The conflicts for one RBI sentence: a list of {dimension, grade, rbi, values: {value:
    [(start, end, quantity text)]}} with two or more different values."""
    rbi_q = quantities(rbi_sentence)
    if not rbi_q:
        return []
    dims = {q.dimension for q in rbi_q}
    spans = spans if spans is not None else sentences(policy_text)
    groups: dict[tuple[str, str, str], dict[float, list]] = {}
    for i, (s, e) in enumerate(spans):
        sentence = policy_text[s:e]
        found = [q for q in quantities(sentence) if q.dimension in dims]
        if not found:
            continue
        lead = policy_text[spans[i - 1][0] : spans[i - 1][1]] if i else ""
        if not restates(rbi_sentence, sentence, lead):
            continue
        for q in found:
            groups.setdefault((q.dimension, q.grade, q.entity), {}).setdefault(q.value, []).append(
                (s, e, q.text)
            )
    out = []
    for (dim, grade, entity), values in groups.items():
        if len(values) < 2:
            continue
        rbi_values = sorted(
            {q.value for q in rbi_q if q.dimension == dim and q.grade == grade}
        )  # fmt: skip
        out.append({"dimension": dim, "grade": grade, "entity": entity, "rbi": rbi_values,
                    "values": values})  # fmt: skip
    return out


def rbi_sentences(quote: str) -> list[str]:
    """The sentences of an obligation's source quote that state a period or a percentage."""
    return [m.group().strip() for m in _SENTENCE.finditer(body(quote)) if quantities(m.group())]
