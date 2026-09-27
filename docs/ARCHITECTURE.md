# Architecture

> Stub created 2026-09-27; the full document is written on Thu 8 Oct (see docs/PLAN.md).
> Sections: process flow, agent graph, model per stage, reliability mechanisms, guardrails,
> data provenance, evaluation, grid claim.

## Evaluation integrity disclosures

- **Same toolchain.** The planted-gap answer keys (`data/mutations/*.yaml` ->
  `eval/answer_key_*.jsonl`) were authored with the same AI coding assistant (Claude Code) that
  helped build the system under test. Mitigations:
  - Mutations are hand-written, exact find/replace edits applied by a deterministic script. No
    LLM generates or grades them.
  - Every mutation was reviewed and approved by the author (a data engineer familiar with bank
    KYC practice); the review decisions are recorded in the spec notes.
  - A redundant-coverage check (lexical + semantic search of the altered policy) confirmed each
    deleted, narrowed or weakened obligation is not satisfied elsewhere.
  - The keys were committed and pushed to GitHub before any model processed either policy; the
    commit timestamp is the evidence.
  - Pipeline prompts are schema-generic and never reference key clauses, thresholds or themes.
  - Central Bank of India is a held-out test set, run only once at feature freeze; Nainital
    Bank is the development set. Metrics are reported per split.
  - System-reported gaps that are not in the key are adjudicated blind by the author before
    precision is computed.
- **Correlated-error risk.** The redundancy check used bge-m3, which the pipeline also uses for
  retrieval, so both could miss the same passage. Lexical search, manual reading, a FlashRank
  reranker and blind adjudication reduce this; it is disclosed rather than assumed away.
- **Reporting.** All results are counts per row type (e.g. "6/7 gaps, 0/3 decoys, 1/1
  injection"), never bare percentages.
- **Real findings.** Passages of the real published policies that differ from the current RBI
  Directions are labelled separately (`data/mutations/real_findings.yaml`) and scored by their
  own rules, never as false positives.
