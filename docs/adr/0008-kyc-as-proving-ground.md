# 0008. KYC as the proving ground; the engine is regulation-agnostic

- Status: accepted (2026-09-27)

## Context
Problem 1 is framed generically ("regulatory documents relevant to a particular bank" and the
bank's internal controls); it names no regulation, so a solution must demonstrate on a concrete
one. Depth (planted-gap evaluation, real amendments, real bank policies) needs one regulation
done thoroughly. The risk is that judges read a single-regulation demo as a narrow solution.

## Decision
- Build and evaluate end to end on the RBI (Commercial Banks – KYC) Directions, 2025:
  - It is heavily enforced and changes often (two real amendments in ten months).
  - Banks publish their KYC/AML policies, so real bank documents are available.
- Keep every stage regulation-agnostic (clauses, obligations, controls, gaps) and prove it:
  `scripts/generality_check.py` runs the unchanged parser on other RBI Directions for
  commercial banks.

Result (2026-09-27; all public rbi.org.in pages):

| Direction | Paragraphs | Numbering complete | Clauses | Span errors | Coverage |
|---|---|---|---|---|---|
| Know Your Customer (base) | 83 | yes | 548 | 0 | 99.2% |
| Fraud Risk Management | 70 | yes | 107 | 0 | 95.5% |
| Managing Risks in Outsourcing | 98 | yes | 336 | 0 | 97.2% |
| Compliance Function | 72 | yes | 101 | 0 | 97.9% |
| Interest Rate on Deposits | 48 | yes | 150 | 0 | 93.9% |
| Cybersecurity & IT Risk | 233 | yes | 414 | 0 | 97.0% |
| Credit & Debit Cards | 97 | yes | 169 | 0 | 97.3% |

## Consequences
- The deck frames KYC as the proving ground and shows this table as generality evidence.
- Feature 13 (cross-regulation) stays unclaimed; a second regulation through the full
  pipeline is not planned.
- Optional, only if ahead at the 4 Oct checkpoint: an applicability demo. RBI issues separate
  KYC Directions per entity type (commercial, small finance, co-operative banks, ...), so a
  bank profile can select the Directions that apply to it.
