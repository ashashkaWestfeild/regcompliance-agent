"""Evidence that the regulation parser is not KYC-specific.

Downloads other RBI Directions for commercial banks (public pages on rbi.org.in) and runs the
unchanged parser on them. Nothing is stored in the repo; results go to stdout.

    uv run python scripts/generality_check.py
"""

import tempfile
import urllib.request
from pathlib import Path

from regcomp.ingest.rbi_html import read_blocks
from regcomp.ingest.structure import build

DIRECTIONS = {
    13141: "Know Your Customer (project base)",
    13641: "Fraud Risk Management",
    13139: "Managing Risks in Outsourcing",
    13645: "Compliance Function",
    13157: "Interest Rate on Deposits",
    13643: "Cybersecurity & IT Risk",
    13155: "Credit & Debit Cards",
}
URL = "https://rbi.org.in/scripts/BS_ViewMasDirections.aspx?id={}"


def fetch(page_id: int, folder: Path) -> str:
    target = folder / f"{page_id}.html"
    req = urllib.request.Request(URL.format(page_id), headers={"User-Agent": "Mozilla/5.0"})
    target.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return target.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    header = (
        f"{'Direction':34} {'paras':>5} {'seq ok':>6} {'clauses':>7} {'span err':>8} {'cover':>6}"
    )
    print(header)
    with tempfile.TemporaryDirectory() as tmp:
        for page_id, name in DIRECTIONS.items():
            doc = build(read_blocks(fetch(page_id, Path(tmp))))
            paras = [c for c in doc.clauses if c.kind == "para"]
            numbers = [int(c.ref) for c in paras if c.ref.isdigit()]
            sequential = len(numbers) == len(paras) and numbers == list(range(1, len(numbers) + 1))
            covered = bytearray(len(doc.text))
            for c in doc.clauses:
                covered[c.char_start : c.char_end] = b"\x01" * (c.char_end - c.char_start)
            errors = sum(doc.text[c.char_start : c.char_end] != c.quote for c in doc.clauses)
            coverage = 100 * sum(covered) / max(1, len(covered))
            print(
                f"{name:34} {len(paras):>5} {sequential!s:>6} {len(doc.clauses):>7} "
                f"{errors:>8} {coverage:>5.1f}%"
            )


if __name__ == "__main__":
    main()
