"""Extended change-detection evaluation on real 2026 amendments of other RBI Directions.

User decision (27 Sep): enlarge the change-intelligence test set at zero cost. RBI's Master
Directions listing tags Directions for commercial banks as "Updated as on <date>". For each:
  1. fetch the current page from rbi.org.in (the amended version);
  2. find the latest Wayback Machine capture from before the amendments it carries;
  3. run the unchanged clause-level diff (regcomp.change.diff) old -> new;
  4. ground truth = clauses whose RBI marker ("... with effect from <date>" / "... dated <date>")
     names a date after the old capture. Independent of us: RBI writes the markers.
Counts per Direction: found / missed / extra. Nothing here uses a language model.

Sources are cached in data/raw/rbi/changecases/ (git-ignored); the manifest with URLs, capture
timestamps and sha256 is committed at data/change_cases.yaml so anyone can re-fetch and verify.

    uv run python scripts/change_cases.py
"""

import hashlib
import json
import re
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

import yaml

from regcomp.change.diff import diff, substantive
from regcomp.ingest.rbi_html import parse_file

# Selected 27 Sep 2026 from https://rbi.org.in/Scripts/BS_ViewMasterDirections.aspx: every
# commercial-bank Direction tagged "Updated as on ..." (KYC is scored in change_report.py).
DIRECTIONS = {
    13140: "Responsible Business Conduct",
    13143: "Financial Statements: Presentation and Disclosures",
    13145: "Resolution of Stressed Assets",
    13146: "Income Recognition, Asset Classification and Provisioning",
    13148: "Classification, Valuation and Operation of Investment Portfolio",
    13152: "Concentration Risk Management",
    13153: "Credit Risk Management",
    13154: "Credit Information Reporting",
    13156: "Credit Facilities",
    13157: "Interest Rate on Deposits",
    13159: "Prudential Norms on Capital Adequacy",
    13160: "Cash Reserve Ratio and Statutory Liquidity Ratio",
    13162: "Undertaking of Financial Services",
}
PAGE = "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id={}"
CDX = (
    "http://web.archive.org/cdx/search/cdx?url=rbi.org.in/scripts/BS_ViewMasDirections.aspx?id={}"
    "&output=json&filter=statuscode:200&collapse=digest&fl=timestamp,original"
)
RAW = "http://web.archive.org/web/{}id_/{}"  # id_ = the original bytes, no Wayback toolbar
UA = {"User-Agent": "Mozilla/5.0 (regcompliance-agent research; public documents)"}
CACHE = Path("data/raw/rbi/changecases")
DATE = r"([A-Z][a-z]+ \d{1,2}, \d{4})"
BASE_ISSUE = date(2025, 11, 28)  # the Directions were issued on this date


def get(url: str, tries: int = 5) -> bytes:
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=120
            ).read()
        except Exception as e:  # Wayback often answers 503 under load: back off and retry
            err = e
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def marker_date(marker: str) -> date | None:
    m = re.search(r"with effect from " + DATE, marker) or re.search(r"dated " + DATE, marker)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%B %d, %Y").date()


def under_marked(ref: str | None, parent: dict, truth: set) -> bool:
    """True if ref or one of its ancestors carries an RBI amendment marker."""
    while ref:
        if ref in truth:
            return True
        ref = parent.get(ref)
    return False


def cached(name: str, url: str) -> Path:
    path = CACHE / name
    if not path.exists():
        path.write_bytes(get(url))
        time.sleep(2)  # be polite to both servers
    return path


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest, rows, details = [], [], []
    path = Path("data/change_cases.yaml")
    known = (
        {m["rbi_page_id"]: m for m in yaml.safe_load(path.read_text("utf-8")) or []}
        if path.exists()
        else {}
    )
    for pid, name in DIRECTIONS.items():
        new_path = cached(f"{pid}_current.html", PAGE.format(pid))
        new = parse_file(str(new_path))
        dated = {
            c.ref: [d for d in (marker_date(m) for m in c.amended_by) if d and d > BASE_ISSUE]
            for c in new.clauses
        }
        amend_dates = sorted({d for ds in dated.values() for d in ds})
        if not amend_dates:
            rows.append(f"| {name} | - | - | - | - | - | no dated amendment markers |")
            continue
        if pid in known:  # capture already chosen and recorded: reproducible, no Wayback query
            captures = [[known[pid]["old_captured"], known[pid]["old_wayback"].split("id_/", 1)[1]]]
        else:
            captures = json.loads(get(CDX.format(pid)) or b"[]")[1:]
        before = [
            c for c in captures if datetime.strptime(c[0][:8], "%Y%m%d").date() < amend_dates[-1]
        ]
        if not before:
            rows.append(
                f"| {name} | - | - | - | - | - | no Wayback capture before the amendments |"
            )
            continue
        ts, original = before[-1]
        captured = datetime.strptime(ts[:8], "%Y%m%d").date()
        old_path = cached(f"{pid}_{ts}.html", RAW.format(ts, original))
        old = parse_file(str(old_path))
        truth = {ref for ref, ds in dated.items() if any(d > captured for d in ds)}
        reported = {c.new_ref or c.old_ref for c in substantive(diff(old, new))}
        found, missed, extra = reported & truth, truth - reported, reported - truth
        # RBI puts a "substituted" marker on a paragraph; its sub-clauses change with it.
        parent = {c.ref: c.parent_ref for c in old.clauses} | {
            c.ref: c.parent_ref for c in new.clauses
        }

        unexplained = {r for r in extra if not under_marked(parent.get(r), parent, truth)}
        amended = ", ".join(sorted({d.isoformat() for d in amend_dates if d > captured}))
        rows.append(
            f"| {name} | {captured.isoformat()} | {amended} | {len(found)}/{len(truth)} "
            f"| {len(missed)} | {len(extra)} | {len(unexplained)} |"
        )
        details.append(
            f"- {name}: found {sorted(found)}"
            + (f"; missed {sorted(missed)}" if missed else "")
            + (f"; extra not under a marked clause {sorted(unexplained)}" if unexplained else "")
        )
        manifest.append(
            {
                "rbi_page_id": pid,
                "title": name,
                "new_url": PAGE.format(pid),
                "new_sha256": hashlib.sha256(new_path.read_bytes()).hexdigest(),
                "old_wayback": RAW.format(ts, original),
                "old_captured": ts,
                "old_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
                "truth_clauses": sorted(truth),
            }
        )
    lines = [
        "# Change detection on real 2026 amendments of other RBI Directions",
        "",
        "Old = latest Wayback capture before the amendments; new = current rbi.org.in page.",
        "Ground truth = clauses RBI marked as amended after the old capture. Counts only; no",
        "language model involved. KYC (2 amendments) is in change_detection.md.",
        "",
        "| Direction | Old capture | Amendments (effective) | Found | Missed | Extra | Extra not "
        "under a marked clause |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        *details,
        "",
        "Reading the extras (checked 27 Sep): some are real edits RBI did not mark with a date",
        "(renumbered cross-references such as 'paragraph 36' -> 'paragraph 39', '(1)-(6)' ->",
        "'(1)-(5)', '[***]' deletions), which marker-based ground truth cannot credit. The rest",
        "expose two parser gaps the KYC corpus never exercised: inserted paragraphs numbered",
        "'5A.' / '121A.' and sub-clauses '(ia)' are not recognised (they become unnumbered 'U'",
        "clauses; this is also the one miss), and unnumbered clauses are aligned by position, so",
        "one insertion shifts every later 'U' clause.",
    ]
    Path("eval/reports/change_detection_extended.md").write_text("\n".join(lines) + "\n", "utf-8")
    Path("data/change_cases.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
