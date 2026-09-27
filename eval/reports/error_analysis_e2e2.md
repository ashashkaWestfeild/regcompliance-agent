# Error analysis: run e2e2 (Nainital dev), 30 unkeyed gaps

Sampled with seed 20260928 from the 153 unkeyed gaps that are NOT on the blind adjudication sheet,
so the analyst never read the user's gold-set pairs. One primary cause per gap; classified by Claude
from what the judge saw (per-obligation pgvector top-20 -> FlashRank top-5) plus the best lexical
matches from the whole policy. Single annotator: a spot-check by the user is recommended.

| Cause | Count |
|---|---|
| (a) applicability | 5/30 |
| (b) granularity / by reference | 2/30 |
| (c) retrieval | 1/30 |
| (d) judge | 9/30 |
| (e) real gap | 1/30 |
| (f) extraction | 11/30 |
| scorer bug (near miss counted as extra) | 1/30 |

Findings:
- (f) extraction 11/30: 8 are copies of one obligation: the model repeated 'undertake CDD of the
  proprietor' 69 times for RBI 26(1) (68 duplicate obligations; 30 of 186 gaps are duplicate
  copies). 3 are obligations anchored to a lead-in sentence ('shall have the following:').
- (d) judge 9/30: the right policy text was in the top-5 but the judge said partial, mostly on
  wording differences or on options the regulation permits (channels, 'may').
- (a) applicability 5/30: glossary definitions and system/SOP-level V-CIP controls.
- (b) granularity 2/30, (c) retrieval 1/30, (e) plausible real gap 1/30.
- Scorer bug 1/30: a near miss at a planted-gap ref (N04a) was also counted as an unkeyed extra.

Per-gap notes: eval/runs/e2e2/error_analysis.csv (git-ignored run folder).
