# 0006. 2025 KYC Directions as base; clause-level, noise-filtered diff

- Status: accepted (2026-09-26)

## Context
The 2016 KYC Master Direction was repealed on 28 Nov 2025 and replaced by entity-specific
Directions. Commercial banks follow the RBI (Commercial Banks – KYC) Directions, 2025. Line
diffs of two PDF versions produced 507 "changes" for a one-paragraph amendment, almost all of
them text-extraction noise.

## Decision
- Base regulation: the 2025 Directions, three real versions (original, 29 Dec 2025, 18 Sep 2026).
- Prefer the HTML source; use Docling for PDF-only versions.
- Diff at clause level on each clause's own text (children excluded), aligned by reference, with
  similarity matching for renumbered clauses.
- Whitespace/quote/case-only differences are `cosmetic` and never reach the LLM.

## Consequences
- The Sep 2026 amendment diff reports exactly 1 substantive change out of 546 clauses (tested).
- Change intelligence precision does not depend on PDF extraction quality.
