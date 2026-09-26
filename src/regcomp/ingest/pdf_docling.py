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
