"""Change-detection evaluation against RBI's own amendment markers (independent ground truth).

RBI marks every amended provision in the HTML with "Inserted/Substituted with effect from <date>".
For each real amendment, the ground truth is the set of clauses whose marker names that date in
the version after it. The clause diff is scored against it in counts.

    uv run python scripts/change_report.py   # writes eval/reports/change_detection.md
"""

from collections import Counter
from pathlib import Path

from regcomp.change.diff import diff, substantive
from regcomp.ingest.pdf_docling import parse_rbi_pdf
from regcomp.ingest.rbi_html import parse_file

AMENDMENTS = [
    # (name, marker date text, old parse, new parse, format, marker source for ground truth)
    (
        "29 Dec 2025 (CKYCR reliance)",
        "December 29, 2025",
        "data/raw/rbi/kycdir_v1_20251128.pdf",
        "data/raw/rbi/kycdir_v2_20251229.pdf",
        "PDF -> PDF",
        "data/raw/rbi/kycdir_v2_20251229.html",
    ),
    (
        "18 Sep 2026 (FPIs, certified copy)",
        "September 18, 2026",
        "data/raw/rbi/kycdir_v2_20251229.html",
        "data/raw/rbi/kycdir_v3_20260918.html",
        "HTML -> HTML",
        "data/raw/rbi/kycdir_v3_20260918.html",
    ),
]


def parse(path: str):
    return parse_file(path) if path.endswith(".html") else parse_rbi_pdf(path)


def main() -> None:
    lines = [
        "# Change detection vs RBI amendment markers",
        "",
        'Ground truth: clauses carrying RBI\'s own "with effect from <date>" marker for the '
        "amendment. Counts only.",
        "",
        "| Amendment | Diff | Clauses compared | Unchanged | Cosmetic | Substantive "
        "reported | Marked by RBI | Found | Missed | Extra |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    details = []
    for name, date, old_path, new_path, fmt, marker_path in AMENDMENTS:
        changes = diff(parse(old_path), parse(new_path))
        classes = Counter(c.change_class for c in changes)
        reported = {c.new_ref or c.old_ref for c in substantive(changes)}
        truth = {
            c.ref for c in parse_file(marker_path).clauses if any(date in m for m in c.amended_by)
        }
        found, missed, extra = reported & truth, truth - reported, reported - truth
        lines.append(
            f"| {name} | {fmt} | {len(changes)} | {classes['unchanged']} | {classes['cosmetic']} "
            f"| {len(reported)} | {len(truth)} | {len(found)}/{len(truth)} | {len(missed)} "
            f"| {len(extra)} |"
        )
        detail = f"  - {name}: found {sorted(found)}"
        if missed:
            detail += f"; missed {sorted(missed)}"
        if extra:
            detail += f"; extra {sorted(extra)}"
        details.append(detail)
    lines += [
        "",
        *details,
        "",
        "Cosmetic = differs only in whitespace, quotes, hyphens, case or footnote brackets; "
        "never sent to the model. A naive line diff of the same PDF pair reported 507 changes.",
    ]
    out = Path("eval/reports/change_detection.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
