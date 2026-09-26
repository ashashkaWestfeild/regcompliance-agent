# Architecture Decision Records

One file per settled decision (context, decision, consequences). New decisions get the next
number; superseded ones are marked, never deleted.

| # | Decision | Status |
|---|---|---|
| [0001](0001-deterministic-structural-parsing.md) | Parse regulations by their own numbering, no fixed-size chunks | accepted |
| [0002](0002-postgres-pgvector-bitemporal.md) | Postgres + pgvector, typed bitemporal tables | accepted |
| [0003](0003-open-weights-models.md) | Open-weights models behind LiteLLM, exact-match cache | accepted |
| [0004](0004-llm-judges-code-decides.md) | LLM judges and explains; deterministic code verifies and scores | accepted |
| [0005](0005-answer-key-before-first-run.md) | Planted gaps with an answer key committed before any system run | accepted |
| [0006](0006-regulation-source-and-diff.md) | 2025 KYC Directions as base; clause-level, noise-filtered diff | accepted |
| [0007](0007-one-agent-where-it-pays.md) | Ingestion is a workflow; the change agent is the agent | accepted |
