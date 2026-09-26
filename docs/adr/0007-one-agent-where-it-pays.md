# 0007. Ingestion is a workflow; the change agent is the agent

- Status: accepted (2026-09-26)

## Context
Agents add latency, cost and non-determinism. Ingestion steps are fixed and known in advance;
responding to a regulatory change is not (scope, affected edges and recovery vary per event).

## Decision
Ingestion (parse → extract → retrieve → judge → verify → score) is a deterministic workflow.
The change agent (LangGraph) handles amendments: it plans the scope of re-analysis, calls tools
(diff, re-extract, graph query, judge, evidence lookup, remediation writer), recovers from
invalid output, escalates on disagreement, and says "cannot assess" when evidence is missing.
The same agent with `dry_run=True` provides what-if analysis without writing.

## Consequences
- Agentic capability is concentrated where it adds value and is easy to demonstrate.
- The workflow's numbers are reproducible for evaluation.
