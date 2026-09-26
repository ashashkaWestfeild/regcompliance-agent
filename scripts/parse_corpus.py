"""Parse every source listed in data/sources.yaml into data/parsed/<id>.json.

Deterministic and idempotent: same inputs give byte-identical outputs. Run with
    uv run python scripts/parse_corpus.py
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import yaml

from regcomp.ingest import rbi_html
from regcomp.ingest.pdf_docling import parse_rbi_pdf

OUT = Path("data/parsed")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regulation_files(sources: dict) -> list[tuple[str, Path]]:
    """(output id, file) for every regulation version; versions with two formats give both."""
    out = []
    for entry in sources["regulation"]:
        files = entry.get("files") or [{"file": entry["file"]}]
        for f in files:
            path = Path(f["file"])
            out.append((f"{entry['id']}_{path.suffix.lstrip('.')}", path))
    return out


def main() -> None:
    sources = yaml.safe_load(Path("data/sources.yaml").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for out_id, path in regulation_files(sources):
        doc = rbi_html.parse_file(path) if path.suffix == ".html" else parse_rbi_pdf(path)
        record = {
            "id": out_id,
            "source_file": path.as_posix(),
            "source_sha256": sha256(path),
            "text": doc.text,
            "clauses": [asdict(c) for c in doc.clauses],
        }
        target = OUT / f"{out_id}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{out_id}: {len(doc.clauses)} clauses -> {target}")


if __name__ == "__main__":
    main()
