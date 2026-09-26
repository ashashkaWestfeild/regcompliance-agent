# 0002. Postgres + pgvector, typed bitemporal tables

- Status: accepted (2026-09-26)

## Context
The traceability chain (regulation → obligation → control → evidence → gap → remediation) must
answer "what did we believe was in force on date X?" after amendments. Graph databases (Neo4j)
and separate vector stores (Qdrant) add infrastructure and split one transaction into several.

## Decision
One Postgres database with pgvector. One table per entity; edges (mappings, gaps) reference a
specific *version row*, not a stable key. Every versioned row carries valid time
(`effective_from/to`) and transaction time (`recorded_at/superseded_at`). A partial unique
index enforces one current belief per key.

## Consequences
- A new obligation version makes every mapping to the old version stale by construction, which
  is exactly the set the change agent must re-map.
- Vectors, graph and versions commit atomically.
- Graph views are queries, not a separate store.
