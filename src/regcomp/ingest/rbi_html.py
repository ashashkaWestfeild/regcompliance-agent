"""Read an RBI Master Direction web page (rbi.org.in BS_ViewMasDirections.aspx) into blocks.

The Directions body starts at the first "Chapter I" heading after the table of contents and
ends at the signature. Inline amendment markers are ``<sup title="Inserted with effect from
...">n</sup>``: the number is removed from the text and the title is kept as metadata on the
block, which gives the change agent ground truth about which paragraph an amendment touched.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from regcomp.ingest.structure import Block, ParsedDocument, build

_CHAPTER_ONE = re.compile(r"^Chapter I\s*[–-]", re.IGNORECASE)
_SIGNATURE = re.compile(r"Chief General Manager", re.IGNORECASE)


def read_blocks(html: str) -> list[Block]:
    soup = BeautifulSoup(html, "lxml")
    elements = [
        el
        for el in soup.find_all(["p", "li"])
        if not (el.name == "li" and el.find("p"))  # the inner <p> carries the text
    ]

    blocks: list[Block] = []
    in_body = False
    for el in elements:
        if "footnote" in (el.get("class") or []):
            continue
        amended = []
        for sup in el.find_all("sup"):
            if isinstance(sup, Tag) and sup.get("title"):
                amended.append(sup["title"].strip())
            sup.decompose()
        text = el.get_text(" ", strip=True)
        is_heading = "head" in (el.get("class") or [])

        if not in_body:
            # The TOC repeats chapter titles as links; the body heading is a <p class="head">.
            if is_heading and _CHAPTER_ONE.match(text) and not el.find("a", href=True):
                in_body = True
            else:
                continue
        if _SIGNATURE.search(text):
            break
        blocks.append(Block(text=text, is_heading=is_heading, amended_by=amended))
    return blocks


def parse_file(path: str | Path) -> ParsedDocument:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return build(read_blocks(html))
