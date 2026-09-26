# 0004. LLM judges and explains; deterministic code verifies and scores

- Status: accepted (2026-09-26)

## Context
The D2 claim requires high, *demonstrable* reliability. LLMs can fabricate quotes, drop "shall
not", and alter thresholds. Risk scores that change between runs are not auditable.

## Decision
- LLMs do reading and judgment: extraction, mapping verdicts, rationales, remediation drafts.
- Code does verification and scoring:
  - citation gate (quote must equal the source slice exactly),
  - number and negation fidelity (thresholds and "must not" must appear in the cited span),
  - schema validation with one repair-retry,
  - gap type and risk score from rules over control attributes.
- Judge disagreement or low confidence routes to a stronger model, then a human review queue.

## Consequences
- Every accepted claim has a verifiable citation; rejections are counted as a metric.
- The same inputs always produce the same risk ranking.
- The review queue is where "humans in the lead" is demonstrated.
