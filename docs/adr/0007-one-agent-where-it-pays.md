# 0007. Ingestion is a workflow; the change agent is the agent

- Status: accepted (2026-09-26)

## Context
Agents add latency, cost and non-determinism. Ingestion steps are fixed and known in advance;
responding to a regulatory change is not (scope, affected edges and recovery vary per event).

## Decision
Ingestion (parse → extract → retrieve → judge → verify → score) is a deterministic workflow.
The change agent (LangGraph, `src/regcomp/change/agent.py`) handles amendments. Its nodes:
`diff` (compare the versions clause by clause, and classify each change), `scope` (query the
compliance graph for the obligations, mappings and gaps touched), `gate` (pause for a person
when a change would re-open more than 20% of mappings), `plan`, `re_extract` (extraction model
on the changed clauses), `re_map` (candidate retrieval and the judge on those obligations only),
`compare` (gaps that would open or close) and `commit` (a new version beside the old). A failed
model call in `re_extract` or `re_map` is tried up to three times; state is checkpointed after
every node; an obligation the judge leaves without a usable answer goes to review ("cannot
assess"). The same agent with `dry_run=True` provides what-if analysis: it stops after `compare`
and has no path to `commit`.

Corrected 8 Oct 2026 to match the code: the first version listed tools the agent does not have
(evidence lookup, remediation writer) and an escalation on judge disagreement that was not
built.

## Consequences
- Agentic capability is concentrated where it adds value and is easy to demonstrate.
- The workflow's numbers are reproducible for evaluation.
