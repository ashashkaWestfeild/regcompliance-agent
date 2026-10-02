"""Which part of the compliance graph a clause change touches (the agent's "graph query").

Given the classified changes and the current graph (obligations, their mappings to policy
controls, open gaps), work out the smallest set that has to be looked at again:

- obligations taken from the changed clause or from a clause under it;
- when the changed clause is a definition, obligations elsewhere that use the defined term;
- the mappings and open gaps of those obligations.

Nothing outside this set is re-extracted or re-judged. The share of all mappings inside the set
is the blast radius; above ``BLAST_LIMIT`` the agent stops and asks a person before continuing.
"""

import re
from dataclasses import asdict, dataclass, field

BLAST_LIMIT = 0.20  # share of mappings one change event may re-open without human approval


@dataclass
class Scope:
    direct: list[str] = field(default_factory=list)  # obligation ids from the changed clauses
    by_definition: list[str] = field(default_factory=list)  # obligation ids that use the term
    mappings: list[str] = field(default_factory=list)
    open_gaps: list[str] = field(default_factory=list)
    controls: list[str] = field(default_factory=list)  # policy controls on those mappings
    total_mappings: int = 0
    blast_radius: float = 0.0
    needs_approval: bool = False
    reasons: dict[str, str] = field(default_factory=dict)  # obligation id -> why it is in scope

    def as_dict(self) -> dict:
        return asdict(self)


def under(ref: str, clause: str) -> bool:
    """True when `ref` is `clause` or a sub-clause of it: 5(1)(iv)(a) is under 5(1)(iv)."""
    return ref == clause or ref.startswith(clause + "(")


def _uses(term: str, text: str) -> bool:
    words = [re.escape(w) for w in term.split()]
    return bool(re.search(r"\b" + r"\s+".join(words) + r"(?:s|es)?\b", text or "", re.I))


def scope(changes: list[dict], graph: dict) -> Scope:
    """changes: Classified.as_dict() items that need re-analysis.
    graph: {"obligations": [{id, ref, action, quote}], "mappings": [{id, obligation_id,
    control_id}], "gaps": [{id, obligation_id}]}."""
    out = Scope(total_mappings=len(graph["mappings"]))
    for change in changes:
        for o in graph["obligations"]:
            if o["id"] in out.reasons:
                continue
            if under(o["ref"], change["ref"]):
                out.direct.append(o["id"])
                out.reasons[o["id"]] = f"taken from changed clause {change['ref']}"
            elif change.get("defined_term") and _uses(
                change["defined_term"], f"{o['action']} {o['quote']}"
            ):
                out.by_definition.append(o["id"])
                out.reasons[o["id"]] = f"uses the changed definition '{change['defined_term']}'"
    hit = set(out.reasons)
    out.mappings = [m["id"] for m in graph["mappings"] if m["obligation_id"] in hit]
    out.controls = sorted(
        {
            m["control_id"]
            for m in graph["mappings"]
            if m["obligation_id"] in hit and m["control_id"]
        }
    )
    out.open_gaps = [g["id"] for g in graph["gaps"] if g["obligation_id"] in hit]
    out.blast_radius = len(out.mappings) / out.total_mappings if out.total_mappings else 0.0
    out.needs_approval = out.blast_radius > BLAST_LIMIT
    return out
