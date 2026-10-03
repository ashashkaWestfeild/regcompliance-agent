# D2 detector: development measurements (3 Oct 2026)

Local qwen3:8b on the RTX 4060, on the separate `d2` database; the hosted app's Groq model is not
measured for the detector (P-056 d). Central Bank and Dhanlaxmi were rebuilt from the frozen v1
run files and the model-call cache: every stage before the detector matched v1 exactly (same
mappings, same tiers), then `scripts/run_detect.py` ran. All detector findings are in the review
queue. Scorecards: `d2_dev_scorecard_centralbank.json`, `d2_dev_scorecard_dhanlaxmi.json`.

## Gate 1: the four in-scope misses (need at least 3 of 4)

| Miss | Pattern | Result | Why |
|---|---|---|---|
| L01 (Dhanlaxmi, deleted ongoing due diligence) | definition taken as duty | **found at the right obligation** (review) | the code rule flags the definition the judge relied on |
| C05 (Central Bank, "savings" accounts) | added one-word qualifier | missed | the code rule proposed "savings"; the model answered "same" ("covers savings accounts, matching the regulation's focus on accounts") |
| L03 (Dhanlaxmi, lead-in "for individual customers") | limit in a list lead-in | missed | the lead-in was shown; the model answered "same" for all three list items |
| C04 (Central Bank, monitoring of high-risk accounts) | narrower subject in another sentence | missed | the supporting passage did not trigger a scope question |

**1 of 4.** The gate needs 3. The code rules work where code decides (L01); every case that
depends on the 8-billion-parameter model judging scope was answered "same".

## Ceiling: new scope-question findings per development bank (at most 12)

| Bank | Scope questions asked | "narrower" answers | Kept after the code checks | Definition findings |
|---|---|---|---|---|
| Nainital (key 1) | 219 | 65 | **13** | 0 |
| Central Bank | 291 | 62 | **26** | 0 |
| Dhanlaxmi | 301 | 74 | **17** | 5 |

Over the ceiling on all three. The code checks on the answers (limiting words must be in the
policy, not only a cross-reference, not RBI's own limit, support must share at least ABSENT of
RBI's wording) remove most "narrower" answers; what is left comes mostly from generic list
lead-ins. No high-confidence finding was added (the detector writes only to the review queue),
so the precision gate on the author's "no gap" rows is not touched.

## Planted gaps on the development keys (detector on, location-tolerant)

| Bank | v1 | with detector |
|---|---|---|
| Central Bank | 4 of 7 at the right obligation | 4 of 7 (no change) |
| Dhanlaxmi | 3 of 6 | 4 of 6 (+L01); one further row (L04) shows as found only through an evidence-test finding from the rebuild sequence (an operating failure on the CKYCR log, scored on L04's credit sentence), not through the detector, so it is not counted |

No planted gap found by v1 was lost.

## Reading

The detector's code rule is sound (it found the deleted duty L01 with no model). The scope
question is the weak link: the local model does not recognise a subset as narrower ("savings
accounts" against "accounts", "individual customers" against "customers") and over-reports
generic lead-ins. A stronger model is not available within the rules (P-056 d keeps the numbers
on local qwen3:8b; Groq's free tier cannot carry 300 questions a bank). The gate (3 of 4) cannot
be met with this design; letting the code rule decide modifiers alone would add C05 at best
(2 of 4) at the cost of precision.

Also noted: the scorer gives policy-gap credit to an evidence-test finding (operating failure)
that lands on a credit sentence. Worth separating after 10 Oct; it did not affect v1.
