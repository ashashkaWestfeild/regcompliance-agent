# 0003. Open-weights models behind LiteLLM, exact-match cache

- Status: accepted (2026-09-26)

## Context
Hackathon rules explicitly permit open-source models. Banks often cannot send policy data to
third-party APIs. The author's laptop has an RTX 4060 (8 GB). Budget target is zero cash cost.

## Decision
- Local Ollama serves an 8B-14B open-weights model for extraction and first-pass judging.
- A larger open-weights model on a free hosted tier handles escalations only.
- LiteLLM maps each pipeline stage to a model in config; eval mode pins models with fallback off.
- An exact-match cache keyed on (prompt hash, model, input hash). Never a semantic cache: two
  clauses that differ only in "10 days" vs "30 days" must not share an answer.

## Consequences
- The whole system can run inside a bank's perimeter.
- Model quality is lower than frontier APIs, so reliability comes from verification
  (0004), not from the model alone.
- A paid API model remains possible as an explicit, logged opt-in.
