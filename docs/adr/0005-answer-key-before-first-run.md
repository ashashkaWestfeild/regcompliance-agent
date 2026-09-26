# 0005. Planted gaps with an answer key committed before any system run

- Status: accepted (2026-09-26)

## Context
Real bank policies have no published list of gaps, so gap detection cannot be scored against
them. Grading a system with labels produced after seeing its output is self-grading.

## Decision
A script applies hand-written mutations (delete control, weaken threshold, narrow scope,
contradict, make stale, strip owner/evidence) plus decoy edits that must *not* raise a gap,
and writes an answer key. The key is committed and pushed to GitHub before the first LLM run;
the push timestamp is the proof. See `docs/mutation_taxonomy.md`.

## Consequences
- Per-operator precision and recall, plus a decoy false-positive rate.
- Real, unplanted gaps in the public policies are labelled separately and never counted as
  false positives.
- Mutation realism depends on the author's review.
