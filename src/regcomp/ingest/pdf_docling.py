"""Read a text PDF into blocks with Docling (layout analysis, reading order, tables; no OCR).

Docling's conversion is slow on CPU, so its output is cached as JSON next to the parsed data
(keyed by the PDF's sha256) and reused on every later run.
"""

import hashlib
import json
import re
from pathlib import Path

from regcomp.ingest.structure import Block, ParsedDocument, build

CACHE_DIR = Path("data/parsed/docling_cache")
_CHAPTER_ONE = re.compile(r"^Chapter I\s*[–-]", re.IGNORECASE)
_FIRST_PARA = re.compile(r"^1\.\s+\S")
_SIGNATURE = re.compile(r"Chief General Manager", re.IGNORECASE)
_SKIP_LABELS = {"page_header", "page_footer", "footnote", "picture", "caption"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docling_items(path: str | Path) -> list[dict]:
    """[{label, text}] in reading order, from cache or a fresh Docling conversion."""
    path = Path(path)
    cache = CACHE_DIR / f"{_sha256(path)}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    doc = converter.convert(str(path)).document

    items = []
    for item, _level in doc.iterate_items():
        label = str(getattr(item, "label", "")).split(".")[-1].lower()
        if label == "table":
            text = item.export_to_markdown(doc=doc)
        else:
            text = getattr(item, "text", "") or ""
            marker = getattr(item, "marker", "") or ""
            if marker and not text.startswith(marker):
                text = f"{marker} {text}"
        items.append({"label": label, "text": text})

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
    return items


def rbi_blocks(items: list[dict]) -> list[Block]:
    """Regulation PDFs: body runs from the Chapter I heading before paragraph 1 to the signature."""
    first_para = next(i for i, it in enumerate(items) if _FIRST_PARA.match(it["text"].strip()))
    start = max(
        (i for i in range(first_para) if _CHAPTER_ONE.match(items[i]["text"].strip())),
        default=first_para,
    )
    blocks = []
    for it in items[start:]:
        if it["label"] in _SKIP_LABELS:
            continue
        if _SIGNATURE.search(it["text"]):
            break
        blocks.append(Block(text=it["text"], is_heading=it["label"] in ("section_header", "title")))
    return blocks


def parse_rbi_pdf(path: str | Path) -> ParsedDocument:
    return build(rbi_blocks(docling_items(path)))


# ---------------------------------------------------------------- bank policies

_MARKER = re.compile(
    r"^(\d{1,2}(\.\d{1,2})+\.?|\d{1,3}\.|\([0-9a-z]{1,6}\)|[0-9a-z]{1,6}\)|[a-z]{1,2}\.|[ivxl]{1,6}\.)\s"
)
_TOC = re.compile(r"^(table of )?contents$", re.IGNORECASE)
_BODY_START = re.compile(r"^(chapter\b|preamble|introduction|1\.\s|1\.1\b)", re.IGNORECASE)
# In policies only these headings are hard boundaries; other sub-headings ("A. Terms ...",
# "Example:") are ordinary text inside the current clause, so their lists keep a parent.
_HARD_HEADING = re.compile(r"^(chapter|part|annex)", re.IGNORECASE)
_FURNITURE_MIN_REPEATS = 8  # page headers repeat on every page; real text almost never does
_SENTENCE_END = (".", ":", ";", "?", "!")


def _furniture(items: list[dict]) -> set[str]:
    counts: dict[str, int] = {}
    for it in items:
        key = " ".join(it["text"].split())
        if key:
            counts[key] = counts.get(key, 0) + 1
    return {k for k, n in counts.items() if n >= _FURNITURE_MIN_REPEATS}


def policy_blocks(items: list[dict]) -> list[Block]:
    """Bank policy PDFs: drop page furniture, start after the table of contents, and re-join
    paragraphs that a page break split in two."""
    furniture = _furniture(items)
    kept = [
        it
        for it in items
        if it["label"] not in _SKIP_LABELS and " ".join(it["text"].split()) not in furniture
    ]

    toc = next((i for i, it in enumerate(kept) if _TOC.match(it["text"].strip())), -1)
    start = next(
        (
            i
            for i, it in enumerate(kept)
            if i > toc and it["label"] != "table" and _BODY_START.match(it["text"].strip())
        ),
        0,
    )

    blocks: list[Block] = []
    for it in kept[start:]:
        text = it["text"].strip()
        if not text:
            continue
        marked = bool(_MARKER.match(text))
        heading = (
            it["label"] in ("section_header", "title")
            and not marked
            and bool(_HARD_HEADING.match(text))
        )
        prev = blocks[-1] if blocks else None
        if (
            prev
            and not prev.is_heading
            and not heading
            and not marked
            and text[0].islower()
            and not prev.text.rstrip().endswith(_SENTENCE_END)
        ):
            prev.text = f"{prev.text.rstrip()} {text}"
            continue
        blocks.append(Block(text=text, is_heading=heading))
    return blocks


def parse_policy_pdf(path: str | Path) -> ParsedDocument:
    return build(policy_blocks(docling_items(path)))
