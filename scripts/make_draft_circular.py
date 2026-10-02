"""Write the SYNTHETIC draft circular used for the what-if demo (feature 12).

The draft is the current KYC Directions (18 Sep 2026 version) with one invented sentence added to
paragraph 18. It is not an RBI document: the file name, the sources entry and the sentence itself
say so. The change agent runs on it with --dry-run only.

    uv run python scripts/make_draft_circular.py
"""

from pathlib import Path

BASE = Path("data/raw/rbi/kycdir_v3_20260918.html")
OUT = Path("data/synthetic/kycdir_draft_whatif.html")
ANCHOR = "The officer concerned shall duly record the reason(s) for rejection."
ADDED = (
    " The bank shall inform the applicant in writing of the reason(s) for rejection within"
    " seven working days."
)


def main() -> None:
    html = BASE.read_text(encoding="utf-8")
    if html.count(ANCHOR) != 1:
        raise SystemExit(f"anchor sentence occurs {html.count(ANCHOR)}x in {BASE}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html.replace(ANCHOR, ANCHOR + ADDED), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: paragraph 18 + {ADDED.strip()!r} (synthetic, not an RBI text)")


if __name__ == "__main__":
    main()
