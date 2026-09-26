"""Text normalization.

Two different normal forms, on purpose:

- ``canonical``: the text we store and cite. Only whitespace is changed, so a quote an LLM
  copies from the canonical text can be checked verbatim by the citation gate.
- ``for_diff``: an aggressive form used only to decide whether two clause versions differ in
  substance. It folds quotes/dashes, drops footnote brackets and removes all whitespace, so
  PDF word-splitting ("per son" vs "person") and layout noise compare equal.
"""

import re
import unicodedata

_WS = re.compile(r"\s+")
_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        " ": " ",
    }
)


def canonical(text: str) -> str:
    """Collapse runs of whitespace (including NBSP) to one space and strip the ends."""
    return _WS.sub(" ", text.replace(" ", " ")).strip()


def for_diff(text: str) -> str:
    """Comparison key: case-folded, punctuation-folded, whitespace-free."""
    t = unicodedata.normalize("NFKC", text).translate(_QUOTES).casefold()
    t = t.replace("[", "").replace("]", "")
    return _WS.sub("", t)
