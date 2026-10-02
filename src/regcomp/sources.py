"""Source metadata for citations, read from data/sources.yaml (never from a model).

A regulation has three dates that must not be confused:
  issued_on        when the Direction was first issued
  version_date     the "updated as on" date of the version in use
  amendment date   when a marked clause was inserted or changed (from RBI's own clause marker)
A later version of a Direction keeps the title, reference number and issue date of the original.
"""

import re
from datetime import date, datetime
from pathlib import Path

import yaml

SOURCES = Path("data/sources.yaml")
_EFFECT = re.compile(r"with effect from\s+([A-Z][a-z]+ \d{1,2}, \d{4})")


def _load() -> dict:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8"))


def _url(entry: dict) -> str | None:
    if entry.get("retrieved_from"):
        return entry["retrieved_from"]
    files = entry.get("files", [])
    html = [f for f in files if str(f.get("file", "")).endswith(".html")]
    chosen = html or files
    return chosen[0].get("retrieved_from") if chosen else None


def regulation_meta(version_label: str) -> dict:
    """Citation fields for a version of the regulation, by its version label."""
    entries = _load()["regulation"]
    original = entries[0]
    entry = next((e for e in entries if e.get("version_label") == version_label), None)
    if entry is None:
        raise KeyError(f"no regulation version {version_label!r} in {SOURCES}")
    return {
        "source_title": original["title"],
        "reference_no": original["reference_no"],
        "issued_on": original["issued_on"],
        "version_date": entry["effective_from"],
        "amended_by": entry.get("amended_by"),
        "url": _url(entry),
    }


def policy_meta(policy_id: str) -> dict:
    """Citation fields for a bank policy, by its id."""
    entry = next((p for p in _load()["policies"] if p["id"] == policy_id), None)
    if entry is None:
        raise KeyError(f"no policy {policy_id!r} in {SOURCES}")
    return {
        "source_title": entry["title"],
        "issuer": entry["bank"],
        "stated_date": entry.get("stated_date"),
        "stated_date_kind": entry.get("stated_date_kind"),
        "url": entry.get("retrieved_from"),
    }


def marker_date(marker: str) -> date | None:
    """The effective date inside an RBI amendment marker, or None if it states none."""
    m = _EFFECT.search(marker or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None
