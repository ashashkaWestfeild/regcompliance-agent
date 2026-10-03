# D2 attempt: closing note (3 Oct 2026)

**Stopped by its own gate, by the author's decision, on 3 Oct.** The claim stays **F3 / D1** with
the evaluation of record at tag `eval-freeze-2026-10-03`. This branch (`d2`) is left unmerged;
nothing from it is part of the submitted solution.

## What was pre-registered
`eval/d2_bar.md` (committed before the third bank was chosen, amended twice with logged reasons,
P-052 and P-054): one detector for duties missing or narrowed in the policy; development gates
before a second freeze (at least 3 of the 4 in-scope held-out misses found at the right
obligation, no planted gap lost, no new high-confidence finding on a row the author labelled
"no gap"); a ceiling of 12 new scope findings per development bank (P-056); then one run on a
third unseen bank (South Indian Bank, key frozen at `c556c42`) against a fixed bar.

## What happened
- Error analysis of the 8 held-out misses ([d2_error_analysis.md](d2_error_analysis.md)): the
  four in scope were lost at the judge or before it (a definition taken as the duty, a narrower
  subject, a one-word qualifier, a limit in a list lead-in).
- Detector built under guardrails P-055 and P-056: structural rules, development-bank text only,
  a leak check over every file changed since the freeze (0 leaks), the lead-in shown only in the
  second pass.
- Development measurements, local qwen3:8b ([d2_dev_measurements.md](d2_dev_measurements.md)):
  **1 of 4** target misses found (L01, by the definition rule, no model); the scope question
  answered "same" for "savings accounts" against "accounts" and for a list limited to
  "individual customers"; new scope findings **13 / 26 / 17** on Nainital, Central Bank and
  Dhanlaxmi, over the ceiling of 12 on all three. No v1 planted gap was lost and no
  high-confidence finding was added.

## What it shows
- A pre-registered bar works as a brake: the attempt stopped on development data, before a
  second freeze, without touching the third bank.
- The code rule caught a deleted duty without a model: when the only support for a "covered"
  verdict is a definition, the duty is missing.
- Judging scope (is the policy's subject narrower than RBI's?) needs a stronger model than the
  local 8B one. That is the next step, with the same bar and the same frozen third-bank key.

## What is kept
- The third bank's key stays frozen (`c556c42`). The frozen v1 runs on it once, reported whatever
  the result (see the pre-run note on `main`).
- Noted for after 10 Oct: the scorer gives policy-gap credit to an evidence-test finding that
  lands on a credit sentence; it did not change any v1 number (checked on Nainital key 1).
