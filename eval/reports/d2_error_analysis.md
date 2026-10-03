# D2 error analysis: why v1 missed 8 planted gaps on the two held-out banks

Written 3 Oct 2026, before any detector code, as `eval/d2_bar.md` requires. From this analysis on,
Central Bank and Dhanlaxmi are **development banks**: their misses are read here and the detector
is built with them in view, so their numbers are no longer evidence of anything unseen.

**Method (read-only).** `scripts/d2_trace_misses.py` traces each miss through the frozen v1 run of
`eval-freeze-2026-10-03` (run files in the freeze checkout) and the model-call cache, which holds
every judge prompt with its candidate passages and the judge's answer. Nothing was re-run and no
database row was written. Full output: [d2_trace_misses.txt](d2_trace_misses.txt).

Stages: (1) was the RBI obligation extracted; (2) was the mutated text in an extracted control;
(3) which passages the judge saw; (4) the judge's verdict and reason; (5) what the run reported.

## Summary

| Row | Planted change | Lost at | Cause |
|---|---|---|---|
| **C04** | delete: intensified monitoring of high-risk accounts (RBI 41(2)) | 4, judge | Accepted a **narrower-subject** passage as cover: "accounts reported in STR should be classified as high risk and subjected to enhanced monitoring" (one category) for the general duty on all high-risk accounts |
| **L01** | delete: ongoing due diligence (RBI 39), all three statements | 4, judge | Accepted a **definition** as cover: "'On-going Due Diligence' means regular monitoring of transactions…" (4.2.10) for the duty to undertake it |
| **C05** | narrow: money-mule monitoring limited to **savings** accounts (RBI 68) | 4 judge, 5 code check | The narrowed sentence was the top candidate; the judge called it covered (confidence 1.0). The code check for added limits (`verify.inserted`) needs a multi-word limiting phrase ("only…", "except…"), so a **one-word qualifier** passes |
| **L03** | narrow: re-KYC periodicity limited to **individual customers** (RBI 42(1)) | 3, candidates | The narrowing sits in a **list lead-in** ("The frequency of periodic updation for individual customers shall be as follows:"). The judge saw the list items (2 / 8 / 10 years) **without** the lead-in, so the limit was invisible |
| C06 | contradict: second, conflicting re-KYC period (5 years) | 4, judge | Found at the right obligation (review tier) as a weaker threshold, not as a contradiction: the judge compares against one best passage |
| L04 | contradict: 30-day CKYCR upload beside the 10-day rule | 4, judge | The judge picked the matching 10-day sentence as best support; the conflicting 30-day sentence in another candidate was ignored |
| C07 | strip_design: STR alerts lose their named approver | 4, judge | Owner-level detail not checked: other passages naming the Principal Officer's general duties were taken as cover |
| L02 | weaken_modality: Principal Officer details to FIU-IND "may" | scoring location | The judge was **right** (partial, optional not mandatory) but pointed to the RBI-communication sentence (still "shall") as its best support, so the gap sat at a different passage: a near miss |

Stage 2 (extraction coverage) caused none of the eight: the passage candidates cover about 99% of
every policy's text, and in every case the judge saw passages from the right section. Dhanlaxmi's
low extraction-unit coverage did not decide L01 or L03.

## The four in scope for the detector (deletions and narrowed scope)

All four were judged **covered** by a passage that does not carry the duty as RBI states it. Three
patterns, each generic (no clause, threshold or theme from any key):

1. **Definition taken as duty (L01).** A sentence of the form "'X' means …" (or inside a
   definitions section) describes a term; it does not oblige anyone. If the only support for a
   covered verdict is a definition, the duty is missing.
2. **Narrower subject or scope (C04, C05).** The supporting passage applies the duty to a subset
   of what RBI names: a category ("accounts reported in STR" for "high-risk accounts") or a
   one-word qualifier on the same noun ("savings accounts" for "accounts"). Code can catch the
   near-verbatim case (an extra qualifier word in front of the obligation's own noun); the
   different-sentence case needs a scope question to the model.
3. **Limit hidden in a lead-in (L03).** A list item is shown without the sentence that introduces
   it, so a limit stated in the lead-in ("for individual customers") never reaches the judge.
   Showing each candidate with its parent lead-in makes the limit visible.

Not in scope (stays on the roadmap): the two contradictions (C06, L04: the judge looks for one
supporting passage, not for a conflicting one), the stripped owner (C07) and the scoring-location
near miss (L02).

## What the detector will be (design only; built next, on the `d2` branch)

A second pass over **covered** verdicts that asks whether the support really carries the duty for
the whole subject: (1) a code rule for definition-only support; (2) a code rule for an extra
qualifier on the obligation's noun in a near-verbatim passage, plus a schema-generic model
question for subject scope when the support is a different sentence; (3) candidates shown with
their parent lead-in. Findings go to the review queue by default and reach the high-confidence
tier only if the development gates in `eval/d2_bar.md` hold (at least 3 of C04, C05, L01, L03
found at the right obligation; no planted gap lost; no new high-confidence finding on a row the
author labelled "no gap").

Risk to watch: pattern 3 changes what the judge sees for every obligation, so it can move many
verdicts; it is measured on all four development keys before anything is promoted.
