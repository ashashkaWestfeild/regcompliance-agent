"""Full source citation for a finding. Every field comes from stored source data (the document
row loaded from data/sources.yaml and RBI's clause markers kept by the parser), never from a model.

Three dates are kept apart and labelled:
  issued         when the Direction was first issued
  version        the "updated as on" date of the version in force
  amendment      when the cited paragraph was inserted or changed, from RBI's own marker
"""

from datetime import date

from regcomp.sources import marker_date

DOC_FIELDS = (
    "source_title",
    "issuer",
    "reference_no",
    "issued_on",
    "effective_from",
    "amended_by",
    "url",
    "stated_date",
    "stated_date_kind",
)


def day(value) -> str:
    return f"{value.day} {value:%b %Y}" if isinstance(value, date) else ""


def regulation_citation(doc: dict, paragraph: str, markers: list[str] | None = None) -> dict:
    """doc: the regulation's document row (DOC_FIELDS). markers: RBI's amendment markers on the
    cited paragraph or a paragraph that contains it."""
    return {
        "document": doc["source_title"],
        "paragraph": paragraph,
        "reference_no": doc["reference_no"],
        "issued_on": doc["issued_on"],
        "version_date": doc["effective_from"],
        "version_amended_by": doc["amended_by"],
        "url": doc["url"],
        "amendments": [{"marker": m, "effective": marker_date(m)} for m in markers or []],
    }


def policy_citation(doc: dict, section: str | None) -> dict:
    """doc: the bank policy's document row (DOC_FIELDS)."""
    return {
        "document": doc["source_title"],
        "issuer": doc["issuer"],
        "section": section,
        "stated_date": doc["stated_date"],
        "stated_date_kind": doc["stated_date_kind"],
        "url": doc["url"],
    }


def predates(policy: dict, regulation: dict) -> list[str]:
    """One sentence per amendment of the cited paragraph that is later than the policy's own
    date: the policy could not have reflected it when it was written."""
    stated = policy.get("stated_date")
    if not isinstance(stated, date):
        return []
    return [
        f"The policy's own date ({policy['stated_date_kind']} {day(stated)}) is earlier than "
        f"the amendment to this paragraph (in effect from {day(a['effective'])})."
        for a in regulation["amendments"]
        if a["effective"] and stated < a["effective"]
    ]


def regulation_lines(c: dict) -> list[str]:
    """The citation in words, one fact per line, each date with its own label."""
    lines = [
        f"{c['document']}, paragraph {c['paragraph']}",
        f"RBI reference: {c['reference_no']}",
        f"First issued: {day(c['issued_on'])}",
        f"Version in force: updated as on {day(c['version_date'])}"
        + (f" (last amended by: {c['version_amended_by']})" if c["version_amended_by"] else ""),
    ]
    for a in c["amendments"]:
        when = f", in effect from {day(a['effective'])}" if a["effective"] else ""
        lines.append(f"This paragraph was amended{when}: {a['marker']}")
    if c["url"]:
        lines.append(f"Source: {c['url']}")
    return lines


def policy_lines(c: dict) -> list[str]:
    lines = [
        f"{c['issuer']}: {c['document']}" + (f", section {c['section']}" if c["section"] else "")
    ]
    if c["stated_date"]:
        lines.append(f"The policy's own date: {c['stated_date_kind']} {day(c['stated_date'])}")
    if c["url"]:
        lines.append(f"Source: {c['url']}")
    return lines
