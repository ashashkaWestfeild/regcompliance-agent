"""The change agent (LangGraph): a new version of a regulation arrives, what has to be redone?

Part 1 (this file today): diff -> classify -> scope -> approval gate -> plan.

    diff      parse both versions, compare clause by clause (change/diff.py)
    classify  what each change means: an option ("may") is an advisory, not a gap; a new duty or
              a changed number is re-analysed (change/classify.py)
    scope     which obligations, mappings and gaps the change touches (change/scope.py)
    gate      if one event would re-open more than BLAST_LIMIT of all mappings, stop and wait for
              a person (LangGraph interrupt); skipped in dry-run, which writes nothing anyway
    plan      the steps part 2 will execute: re-extract the changed clauses, re-map only the
              obligations in scope, raise advisories

State is checkpointed after every node (Postgres in normal use), so a crashed or paused run
resumes from where it stopped with the same thread id. The graph, the regulation text and the
policy are read-only here; with dry_run=True the same graph is the what-if mode.
"""

import operator
from functools import lru_cache
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from regcomp.change.classify import classify
from regcomp.change.diff import diff, substantive
from regcomp.change.scope import BLAST_LIMIT, scope
from regcomp.pipeline.units import DEFINITIONS_SECTION


class ChangeState(TypedDict, total=False):
    old_path: str
    new_path: str
    dry_run: bool
    counts: dict  # change class -> number of clauses
    changes: list[dict]  # classified substantive changes
    scope: dict
    approved: bool
    plan: list[dict]
    status: str  # no_change | planned | rejected
    log: Annotated[list[str], operator.add]


@lru_cache(maxsize=4)
def parse(path: str):
    if path.endswith(".html"):
        from regcomp.ingest.rbi_html import parse_file

        return parse_file(path)
    from regcomp.ingest.pdf_docling import parse_rbi_pdf  # heavy; only for PDF versions

    return parse_rbi_pdf(path)


def graph_from_db(conn) -> dict:
    """The current compliance graph in the shape scope() reads."""
    obligations = conn.execute(
        "SELECT id::text, source_clause_ref, action, source_span->>'quote' FROM obligation"
    ).fetchall()
    mappings = conn.execute("SELECT id::text, obligation_id::text, control_id::text FROM mapping")
    gaps = conn.execute("SELECT id::text, obligation_id::text FROM gap WHERE status = 'open'")
    return {
        "obligations": [
            {"id": i, "ref": ref, "action": action, "quote": quote}
            for i, ref, action, quote in obligations
        ],
        "mappings": [
            {"id": i, "obligation_id": o, "control_id": c} for i, o, c in mappings.fetchall()
        ],
        "gaps": [{"id": i, "obligation_id": o} for i, o in gaps.fetchall()],
    }


def build(load_graph, checkpointer=None):
    """Compile the agent. `load_graph()` returns the compliance graph (see graph_from_db)."""

    def node_diff(state: ChangeState) -> dict:
        old, new = parse(state["old_path"]), parse(state["new_path"])
        changes = diff(old, new)
        counts: dict[str, int] = {}
        for c in changes:
            counts[c.change_class] = counts.get(c.change_class, 0) + 1
        section = {c.ref: c.section for c in old.clauses} | {c.ref: c.section for c in new.clauses}
        classified = [
            classify(
                c, bool(DEFINITIONS_SECTION.search(section.get(c.new_ref or c.old_ref) or ""))
            ).as_dict()
            for c in substantive(changes)
        ]
        return {
            "counts": counts,
            "changes": classified,
            "log": [
                f"diff: {len(changes)} clauses compared, {len(classified)} changed in substance"
            ]
            + [f"classify: {c['ref']} -> {c['effect']}" for c in classified],
        }

    def node_scope(state: ChangeState) -> dict:
        found = scope(state["changes"], load_graph())
        return {
            "scope": found.as_dict(),
            "log": [
                f"scope: {len(found.direct)} obligations from the changed clauses, "
                f"{len(found.by_definition)} through a changed definition; "
                f"{len(found.mappings)} of {found.total_mappings} mappings "
                f"({found.blast_radius:.1%}), {len(found.open_gaps)} open gaps"
            ],
        }

    def node_gate(state: ChangeState) -> dict:
        found = state["scope"]
        if state.get("dry_run") or not found["needs_approval"]:
            return {"approved": True}
        answer = interrupt(
            {
                "question": "This change re-opens a large part of the mapping. Continue?",
                "blast_radius": found["blast_radius"],
                "limit": BLAST_LIMIT,
                "mappings": len(found["mappings"]),
            }
        )
        approved = bool(answer)
        return {
            "approved": approved,
            "log": [f"gate: blast radius above {BLAST_LIMIT:.0%}; reviewer answered {approved}"],
        }

    def node_plan(state: ChangeState) -> dict:
        found, steps = state["scope"], []
        for c in state["changes"]:
            if c["effect"] == "advisory":
                steps.append(
                    {
                        "action": "advise",
                        "ref": c["ref"],
                        "note": "Policy update recommended: the regulation now allows an option. "
                        "Not a compliance gap.",
                        "summary": c["summary"],
                    }
                )
            elif c["effect"] == "repealed":
                steps.append({"action": "retire", "ref": c["ref"], "summary": c["summary"]})
            else:
                steps.append({"action": "re_extract", "ref": c["ref"], "summary": c["summary"]})
        redo = [c for c in state["changes"] if c["reanalyse"]]
        if redo:
            in_scope = found["direct"] + found["by_definition"]
            steps.append({"action": "re_map", "obligations": in_scope, "reasons": found["reasons"]})
            steps.append({"action": "re_score_gaps", "gaps": found["open_gaps"]})
        mode = "dry run: nothing will be written" if state.get("dry_run") else "commit"
        return {
            "plan": steps,
            "status": "planned",
            "log": [f"plan: {', '.join(s['action'] for s in steps)} ({mode})"],
        }

    def node_no_change(state: ChangeState) -> dict:
        return {"status": "no_change", "plan": [], "log": ["no change in substance: nothing to do"]}

    def node_rejected(state: ChangeState) -> dict:
        return {"status": "rejected", "plan": [], "log": ["stopped by the reviewer"]}

    g = StateGraph(ChangeState)
    for name, fn in (
        ("diff", node_diff),
        ("scope", node_scope),
        ("gate", node_gate),
        ("plan", node_plan),
        ("no_change", node_no_change),
        ("rejected", node_rejected),
    ):
        g.add_node(name, fn)
    g.add_edge(START, "diff")
    g.add_conditional_edges("diff", lambda s: "scope" if s["changes"] else "no_change")
    g.add_edge("scope", "gate")
    g.add_conditional_edges("gate", lambda s: "plan" if s["approved"] else "rejected")
    for last in ("plan", "no_change", "rejected"):
        g.add_edge(last, END)
    return g.compile(checkpointer=checkpointer)
