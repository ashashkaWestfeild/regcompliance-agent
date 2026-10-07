# Architecture

RegCompliance Agent checks a bank's KYC policy against an RBI Direction and keeps that check
current when the Direction is amended. This document describes how it is built, what decides
what, how it is evaluated, and where it falls short.

## 1. Principle: the model reads, code decides

A small open-weights model is good at reading a clause and saying what it requires. It is not
reliable at copying text exactly, comparing two numbers, or being consistent. So every step is
split:

| The model does | Code does |
|---|---|
| Extract obligations and controls as structured items | Cut every quote from the source by position; reject an item whose quote is not found; collapse repeats |
| Give a verdict and name an issue | Turn verdict + issue into a gap type by fixed rules |
| (not asked) | Compare near-identical sentences: numbers, "shall" against "may", inserted conditions |
| Draft a remediation | Set owner and due date; reject wording that drops a number or a duty |
| (never sees evidence rows) | Compute exception rates and test them against a tolerance |
| (not asked) | Rank risk from a rubric file |
| (not asked) | Decide whether an obligation applies to the bank, against a profile built from the bank's own policy |

Decision records: [`adr/`](adr/).

## 2. Process flow

```mermaid
flowchart LR
  R[RBI Direction] --> P1[Clause tree<br/>code]
  B[Bank policy PDF] --> P2[Docling + clause tree<br/>code]
  P1 --> E1[Obligations<br/>model + citation gate]
  P2 --> E2[Controls<br/>model + citation gate]
  P2 --> PS[Every policy passage<br/>code]
  E1 --> L[Obligation level<br/>model + rule]
  L --> AP[Applicability<br/>bank profile, code]
  E2 --> RT[Candidate search<br/>bge-m3 + pgvector]
  PS --> RT
  E1 --> RT
  RT --> J[Judge<br/>model] --> G[Gap rules<br/>code]
  G --> V[Wording comparison<br/>and tiers, code]
  EV[Evidence logs] --> T[Control tests<br/>code] --> V
  V --> K[Risk ranking<br/>rubric] --> M[Remediation drafts<br/>model + checks]
  V --> Q[Review queue] --> H[Reviewer decision]
```

Everything is stored in Postgres with pgvector. Rows are versioned: a change adds a new row and
closes the old one in time; nothing is deleted.

### Stages

| # | Stage | Detail |
|---|---|---|
| 1 | Parse | The regulation and the policy become trees of numbered clauses with exact character spans. No fixed-size chunks. |
| 2 | Extract | Obligations (actor, modality, action, threshold) and controls. The model returns the first words of the sentence; code locates them and cuts the sentence. Definitions are extracted clause by clause. A citation at a lead-in ("the bank shall:") moves to the list item that states the duty. |
| 3 | Level | Each obligation is marked policy-level, procedure/system-level or not applicable. A quantified requirement is always policy-level. |
| 3b | Applicability | Each obligation's limiting condition is matched against a bank profile ([`applicability.py`](../src/regcomp/applicability.py)). The profile is built by code from the bank's published policy: a product, channel, customer segment or geography is listed when the policy deals with it, with the clause as evidence. Applies: the bank has every attribute the condition names, or the condition names none. Does not apply: only when the profile states, with a source, that the bank does not offer what the condition names; the gap then leaves both tiers and stays visible with the reason. To confirm: the profile is silent; this is a note on the finding and moves nothing. Each decision is stored with its reason, the attribute relied on and who decided. A model fallback exists but is off: two models marked ordinary conditions (customer risk grades, for example) as bank attributes. |
| 4 | Candidates | For each obligation, the closest policy text by embedding, over extracted controls and every raw policy passage (control extraction misses text, so it is not the only source). Repeats of the same text are dropped; the top five go to the judge. A cross-encoder reranker was removed after it lowered the share of cases where the right passage was in the top five. |
| 5 | Judge | One call per regulation unit. Verdict (covered, partial, missing) and an issue from a fixed list. Fixed rules map these to a gap type. |
| 6 | Tests | Design: does the control name an owner, a frequency, evidence. Operating: exception rate in an evidence log against a tolerance. |
| 7 | Wording comparison and tiers | See section 3. |
| 8 | Risk | [`data/risk_rubric.yaml`](../data/risk_rubric.yaml): the subject of the obligation sets the inherent level; the gap type scales it. |
| 9 | Remediation | Drafted for every open high-confidence gap (dev: 24 gaps, 16 remedies); a draft that fails the fidelity check is replaced by the regulation's own sentence. One remedy is kept per regulation paragraph, and prompt tags never reach the reader. |
| 10 | Citation | Every finding shows the document, paragraph, RBI reference number, link and three separately labelled dates: first issued, version in force ("updated as on"), and, where RBI marks the paragraph, the amendment and its effective date. The bank side shows the policy title, section and the policy's own stated date, and flags a policy dated before the amendment to the cited paragraph. All fields come from [`data/sources.yaml`](../data/sources.yaml) and the parser ([`citation.py`](../src/regcomp/citation.py)); a test checks them against the source record. |

### Feature → stage map

| # | Brief feature | Where it is built | Demo |
|---|---|---|---|
| 1 | Regulatory ingestion | Stage 1 (parse), stage 10 (source metadata) | Overview; the change agent parses v1-v3 live |
| 2 | Change intelligence | §4 diff and classify (code) | Change agent, scenarios 1 and 3 |
| 3 | Obligation extraction | Stages 2-3 (model + citation gate, level) | Gaps tab; scenario 3 re-extracts live |
| 4 | Control-framework understanding (partial) | Stage 2 controls, every policy passage | Gaps tab (policy text, not a control library) |
| 5 | Regulation-to-control mapping | Stages 4-5 (candidates, judge) | Gaps tab; scenario 3 re-maps live |
| 6 | Control effectiveness | Stage 6 (design and operating tests, code) | Evidence tab: design tests of 213 cited controls; operating results |
| 7 | Evidence-based assessment and monitoring | Stage 6 and the evidence trigger (`scripts/run_evidence.py`, `monitor.preview_batch`) | Evidence tab: a new batch tested live in memory |
| 8 | Gap identification | Stage 5 gap rules, §3 wording comparison and tiers | Gaps and Review queue |
| 9 | Risk-based prioritisation | Stage 8 (rubric) | Gaps tab |
| 10 | Remediation recommendations | Stage 9 (model draft + fidelity check) | Gaps tab |
| 11 | Autonomous impact analysis | §4 change agent | Change agent, with the injected failure |
| 12 | What-if / simulation | §4 dry run; stage 3b profile what-if | Scenario 2; Applicability tab |
| 13 | Cross-regulation intelligence | Not built | - |
| 14 | Contradiction detection | Not claimed (the judge has a "conflicting statements" issue; 0 of 2 on the unseen banks). Development analysis only: numeric conflicts inside one policy (`regcomp/conflicts.py`, [report](../eval/reports/policy_conflicts_dev.md)) | - |

### Data model

```mermaid
erDiagram
  DOCUMENT ||--o{ CLAUSE : has
  DOCUMENT ||--o{ CONTROL : "policy has"
  DOCUMENT ||--o| DOCUMENT : supersedes
  CLAUSE ||--o{ OBLIGATION : states
  OBLIGATION ||--o{ APPLICABILITY_DECISION : "per bank profile"
  OBLIGATION ||--o{ MAPPING : "judged against"
  CONTROL ||--o{ MAPPING : "cited by"
  CONTROL ||--o{ EVIDENCE : "tested with"
  CONTROL ||--o{ CONTROL_TEST : "design and operating"
  MAPPING ||--o{ GAP : opens
  OBLIGATION ||--o{ GAP : about
  CONTROL_TEST ||--o{ GAP : "operating failure"
  GAP ||--o{ REMEDIATION : "remedied by"
  MAPPING ||--o{ REVIEW_OVERRIDE : "reviewer decision"
  DOCUMENT ||--o{ CHANGE_EVENT : "old and new version"
  CHANGE_EVENT ||--o{ CLAUSE_DIFF : lists
  CHANGE_EVENT ||--o{ GAP : detected
```

Versioned rows (`effective_from`/`effective_to`, `recorded_at`/`superseded_at`): clause, obligation,
control, mapping, gap. A change adds rows and closes the old ones; nothing is deleted. Beside these:
`embedding` (vectors for any row, 1,024 dimensions), `llm_cache` (every model call, exact-match),
the LangGraph checkpoint tables, and bank profiles as YAML files (`data/profiles/`). In the live
demo database no row has been superseded yet and `change_event` is empty: the demo runs the change
agent as a dry run only. One commit was recorded on a copy of the database (d2) and is shown
read-only in the Change agent tab: change event `c56ec4c8`, clause 18 (a new duty), 3 obligations
and 3 mappings closed in time with 4 added beside them, 2 gaps closed and 2 opened.

## 3. Wording comparison and the two tiers

Bank policies restate much of the regulation almost word for word. Where that is so, code compares
the two sentences directly ([`pipeline/verify.py`](../src/regcomp/pipeline/verify.py)):

- **Number sweep.** Every regulation sentence that states a number is lined up with its closest
  policy sentence. The number one counts only when a unit follows it ("one year", "1 per
  cent"), and "one year" equals "12 months". A number the policy sentence lacks becomes a gap at that passage, even if no
  obligation was extracted from the sentence.
- **Weaker or stricter.** Decided by the words before the number: after "more than", "within",
  "once in every" a larger policy number is weaker; after "at least" a smaller one is. A model is
  asked only when the wording does not decide.
- **Force.** A mandatory obligation whose matching policy sentence says "may".
- **Inserted limits.** A limiting phrase ("only", "at the time of", "in case of") that the policy
  sentence adds inside otherwise matching text.

The result is two tiers:

| High-confidence | Review queue |
|---|---|
| A judge gap the comparison does not contradict | A judge gap where the policy states the text near verbatim |
| A changed number where the policy is weaker | A changed number where the policy is stricter or the direction is unclear |
| | An obligation judged covered whose policy sentence adds a limit or says "may" |
| | A gap on a procedure-level obligation (shown, not dropped) |
| | A gap on a technical system requirement ([`data/triage.yaml`](../data/triage.yaml)) |
| | A control whose latest evidence has recovered |

The comparison sorts findings; it never deletes one.

## 4. The change agent

The one agentic component (LangGraph). A new version of the regulation arrives:

```mermaid
flowchart LR
  A[diff<br/>clause by clause] --> B{anything changed<br/>in substance?}
  B -- no --> Z[done]
  B -- yes --> C[classify<br/>advisory / new duty / number / relaxed / repealed]
  C --> D[scope<br/>obligations, mappings, gaps touched]
  D --> E{more than 20%<br/>of mappings?}
  E -- yes --> W[pause for a person] --> F
  E -- no --> F[plan]
  F --> G[re-extract<br/>changed clauses]
  G --> H[re-map<br/>only what is in scope]
  H --> I[compare<br/>gaps that open or close]
  I --> J{dry run?}
  J -- yes --> Z2[report only<br/>what-if]
  J -- no --> K[commit<br/>new version beside the old]
```

- **An added option is an advisory, not a gap.** The 18 Sep 2026 amendment lets banks use a
  certified-copy route for one more customer type; it is permissive ("may"). The agent reports
  "policy update recommended" and re-maps nothing.
- **Scope.** Obligations taken from the changed clause, and obligations that use a changed
  definition. On the real amendments this is 3 of 458 mappings.
- **Recovery.** A failed model step is retried by the graph; a unit with no answer goes to
  review. State is checkpointed in Postgres after every step, so a paused or crashed run resumes.
- **What-if.** The dry run ends after "compare". It has no path to the step that writes.

A second trigger needs no agent: a new batch of operating evidence is tested and compared with
the control's previous result (newly failing, still failing, recovered, healthy).

## 5. Models

Every stage, the model it uses and what code decides. The evaluated runs (development bank and the
three held-out banks) used the offline column only, with these local model builds (Ollama digests;
pulled 27 Sep 2026, unchanged through the runs): `qwen3:8b` `500a1f067a9f`, `bge-m3`
`790764642607`. An Ollama tag can change upstream while the cache key stays the same, so the digest
is the record of which weights produced the numbers.

| Stage | Model, offline (evaluated runs) | Model, hosted demo | What code decides |
|---|---|---|---|
| Parse regulation and policy | none (Docling layout for PDFs) | none; versions parsed live in the change agent | the whole clause tree and every character span |
| Obligation extraction (`extract_obligations`) | qwen3:8b | gpt-oss-120b, changed clauses only (change agent) | the citation gate cuts the sentence and rejects what it cannot find |
| Definitions (`extract_definitions`) | qwen3:8b | not used | citation gate |
| Obligation level (`classify_level`) | qwen3:8b | gpt-oss-120b, re-extracted obligations only | a quantified duty is always policy-level |
| Control extraction (`extract_controls`) | qwen3:8b | not used (stored results) | citation gate |
| Hidden-instruction scan | none | stored results | the code-level scan flags instruction-like text |
| Applicability (`classify_condition`) | off in every evaluated run (optional fallback) | not used | rules match conditions against the bank profile |
| Candidate search | bge-m3 embeddings + pgvector | no embeddings: ranked by shared wording (no GPU) | deduplication, top 5 |
| Judge (`judge`) | qwen3:8b | gpt-oss-120b, in-scope obligations only (change agent) | fixed rules turn the verdict and issue into a gap type |
| Wording comparison and tiers (`compare_numbers`) | qwen3:8b, only when the wording around a changed number does not decide the direction | stored results | numbers, "shall" against "may", inserted limits, the tier |
| Control tests, risk ranking | none | stored results | everything |
| Remediation (`draft_remediation`) | qwen3:8b | stored drafts | owner, due date, the fidelity check |
| Change agent: diff, classify, scope, plan, compare, commit | none | diff to compare run live; commit never runs (dry run); one recorded commit on d2 shown read-only | everything |
| Evidence trigger (`run_evidence.py`) | none | the October batch tested in memory (`preview_batch`, nothing written) | everything |

**What runs where.** Live in the hosted app (Streamlit Community Cloud, no GPU): reading stored
results on every tab, the change agent's dry run (code, plus gpt-oss-120b on the Groq free tier for
re-extraction, level and judging of the changed clauses only), the applicability what-if (code, in
memory), the evidence-batch test (code, in memory) and the reviewer form (a simulation without the
reviewer code). Offline only, on one
laptop GPU (local qwen3:8b and bge-m3): the full pipeline for a new regulation or policy, every
evaluated run, the evidence trigger and the change agent's commit step (tested offline,
`tests/test_change_agent.py`).

Models are chosen per stage by configuration. Every call is cached by an exact hash of stage,
model, prompt, schema and options; there is no semantic cache, because two clauses that differ
only in "10 days" and "30 days" must not share an answer. Prompts name no clause, threshold or
theme from any answer key.

A 120B hosted model was compared with the local judge on 56 development units with identical
prompts: the same number of gaps, 37 in common, better gap types, one more decoy flagged. It was
not adopted as the evaluated judge ([data](../eval/reports/judge_compare.json)).

## 6. Evaluation

### Design

- **Planted gaps.** Known errors are written into public bank policies as exact find/replace edits:
  a deleted duty, a weakened or stale number, a narrowed scope, a contradiction, a duty made
  optional, a removed owner. Decoys (rewording, reordering, a stricter number) must not be
  flagged. One injected instruction per policy must be flagged and must change nothing.
  Details: [`mutation_taxonomy.md`](mutation_taxonomy.md).
- **Keys before runs.** Each answer key is committed before any model reads that policy; the
  commit time is the evidence.
- **Splits.** Nainital Bank is the development set. Central Bank of India and Dhanlaxmi Bank are
  held out and run once, at the freeze. For the third bank the passages were chosen by a seeded
  draw committed in advance, because its key was written after development results were known.
- **Strict matching.** A planted gap counts as found only if the report is at the right
  obligation and cites the altered passage. The count at the right obligation with any passage is
  reported beside it.
- **Counts, not percentages.** The sets are small.
- **Change detection** is scored against RBI's own amendment markers.

### Development results

| Measure | Result |
|---|---|
| Planted gaps, exact passage | 5 of 7 (3 high-confidence, 2 review) |
| Planted gaps, right obligation | 6 of 7 |
| Decoys flagged | 0 of 3 high-confidence, 1 of 3 review |
| Other reports | 17 high-confidence, 38 review |
| Injection caught / real findings / evidence tests | 1 of 1 / 2 of 2 / 2 of 2 |
| Change detection | 2 of 2 KYC amendments; 262 of 266 clauses in nine other Directions |
| Applicability | 458 of 458 obligations apply to the development bank; none excluded, none to confirm |

Still missed on development: the removed owner, and the contradiction is flagged at the right
obligation with the wrong passage.

**Second development key.** A second set of planted gaps on the same bank (4 gaps, 3 decoys, 1 injection; passages from a seeded draw committed first; key frozen at `4631983` before its run) was written after the wording comparison, to see whether the rules hold on gaps they were not written against.

| Measure | First key | Second key, as first run | Second key, after two fixes |
|---|---|---|---|
| Planted gaps, exact passage | 5 of 7 | 3 of 4 | 3 of 4 |
| Of those, in the high-confidence tier | 3 | 0 | 1 |
| Decoys flagged: high-confidence / review | 0 / 1 of 3 | 0 / 1 of 3 | 0 / 1 of 3 |
| Injected instruction flagged | 1 of 1 | 0 of 1 | 1 of 1 |
| Other reports: high-confidence + review | 17 + 38 | 17 + 38 | 17 + 38 |

What the second key showed: (1) a weakened "one year" to "two years" was judged correctly by the model, then moved to review because the number comparison ignores the number one and so saw two matching sentences; (2) a duty made optional in a sentence whose regulation text has no "shall" was found with the wrong type; (3) a deleted duty was found, in review, because the obligation was classed as procedure-level; (4) the contradiction was missed, as on the first key; (5) the injected instruction, worded differently from the first, was not flagged; the verdicts show no sign that it was followed. The comparison rules therefore fit the first key better than they generalise.

**Two fixes made after the second key's first run (3 Oct), before the freeze.** Both were written from the general principle, without looking at the held-out keys, and both are disclosed here because the last column above is not a test: the fixes were made knowing what this key had missed.

1. *The number one.* The number comparison used to ignore the number one, because "any one of" and "(1)" are not thresholds. It now counts one when a unit follows ("one year", "1 per cent"), and treats "one year" and "12 months" as the same period. Effect on the first key: no verdict, gap, tier or score line changed (the result lock compares equal). Effect on the second key: the weakened "one year" to "two years" moved from the review queue to the high-confidence tier.
2. *A code-level scan for instructions.* Every sentence of the bank's document is checked in code for text that tells an automated reader to drop its instructions, addresses a program reading the document, says what verdict to give, or tells it not to report findings ([`guard.py`](../src/regcomp/pipeline/guard.py)). It does not depend on a model. On the unaltered development policy it flags 0 sentences, and 0 in the regulation; in each planted copy it flags exactly the planted sentence. The held-out banks carry differently worded instructions and are the real test.

Not fixed: the contradiction, the duty made optional where the regulation sentence has no "shall", and the deleted duty classed as procedure-level.

### Held-out results

> **Code of record.** Every evaluated number comes from the tag `eval-freeze-2026-10-03`. `main`
> carries fixes made after the freeze (7 Oct 2026): model replies are validated against their
> schema with one repair retry (B2); the judge fails closed, so an unusable or missing answer goes
> to the review queue as an unspecified gap instead of silently counting as "no gap" (B1); plus
> hardening outside the pipeline (database guard, review row lock, no second commit of an
> amendment, simulated review decisions rolled back as a whole). Audit of the model-call caches
> on 7 Oct: 0 of 6,829 cached replies miss their schema, and with the evaluated prompts the judge
> left no obligation out and gave no unknown verdict in 2,112 calls (the only 38 omissions are
> from one 27 Sep call with an older prompt). So re-running `main` on the cached data reproduces
> the evaluated results; the result lock is unchanged.

> **Since 3 Oct 2026:** Central Bank and Dhanlaxmi have been studied (the D2 error analysis on
> the `d2` branch), so the figures below are the v1 result of record and are no longer evidence
> of anything unseen. A third bank, South Indian Bank (key frozen at `c556c42`), was run once by
> the same frozen v1 code on 3 Oct ([pre-run note](../eval/third_bank_v1_prerun.md)), after the
> D2 attempt had stopped and without the D2 detector.

Run once each, from a clean checkout (git worktree) of the tag `eval-freeze-2026-10-03` (commit
`5cb728b`); answer keys frozen at `350b8e0` (Central Bank), `da58e66` (Dhanlaxmi) and `c556c42`
(South Indian Bank). Nothing was tuned afterwards. Reports: [`heldout_centralbank_report.md`](../eval/reports/heldout_centralbank_report.md),
[`heldout_dhanlaxmi_report.md`](../eval/reports/heldout_dhanlaxmi_report.md),
[`heldout_southindianbank_report.md`](../eval/reports/heldout_southindianbank_report.md); scorecards and
confidence checks in `eval/reports/` carry the evaluated tag.

| Measure | Central Bank | Dhanlaxmi | South Indian Bank |
|---|---|---|---|
| Planted gaps, exact passage | 3 of 7 (all high-confidence) | 2 of 6 (all high-confidence) | 4 of 7 (2 high-confidence, 2 review) |
| Planted gaps, right obligation | 4 of 7 | 3 of 6 | 4 of 7 |
| Decoys flagged | 1 of 3, high-confidence | 0 of 3 | 1 of 3, review (first scoring 2 of 3, see its report) |
| Hidden instruction flagged | 1 of 1, by the code-level scan only | 1 of 1, by the code-level scan only | 1 of 1, by the code-level scan only |
| Other reports: high-confidence + review | 15 + 36 | 42 + 43 | 12 + 29 |
| Obligations excluded by applicability | 0 | 0 (3 to confirm) | 0 |

By type of planted gap (three banks):

| Planted change | Found at the exact passage | At the right obligation |
|---|---|---|
| Weakened number | 4 of 4 (all high-confidence) | 4 of 4 |
| Stale threshold (an older value) | 3 of 3 (high-confidence, typed as weakened) | 3 of 3 |
| Deleted duty | 0 of 4 | 0 of 4 |
| Narrowed scope | 1 of 4 (review) | 1 of 4 |
| Contradiction | 0 of 2 | 1 of 2 (review) |
| Duty made optional | 1 of 2 (review) | 2 of 2 (review) |
| Removed owner | 0 of 1 | 0 of 1 |
| **All planted gaps** | **9 of 20** | **11 of 20** |


**Precision of the high-confidence tier on the held-out banks** (measured after the freeze; nothing
tuned on it; plan and seed committed first, `a050a1d`). The frozen findings were reconstructed from
the model-call cache with the tag's code, and the sampler refused to continue unless each bank
scored exactly as its frozen scorecard. Per bank: 10 high-confidence findings matching no key row
(of 14 and 41 distinct), mixed with 10 pairs judged covered, shuffled, no verdict shown. The author
labelled them, with Gemini helping to write the reasons; Claude ran the full-policy text check on every row labelled gap
([`report.md`](../eval/reports/heldout_precision/report.md), `summary.json` and the sheets
alongside). A "gap" label is set aside only when another passage carries the whole duty: same subject and scope, mandatory, same or stricter (the three-part test, applied to all three banks).

| | Central Bank | Dhanlaxmi | South Indian Bank |
|---|---|---|---|
| Findings labelled gap, of those decided | 8 of 9 | 9 of 9 | 7 of 10 |
| After the full-policy check | 8 of 9 | 9 of 9 | 4 of 10 |
| Duties only (reliefs or permissions not adopted left out) | 6 of 7 | 8 of 8 | 4 of 10 |
| Unsure | 1 | 1 | 0 |
| Covered pairs really covered (after the check) | 8 of 10 (one miss is planted gap C05) | 9 of 10 | 9 of 10 (the miss is planted gap S01) |
| Control-extraction coverage of the policy text | about 62% | about 8% | extraction units: 134,634 of 165,629 characters |

South Indian Bank: every high-confidence finding outside the key (12 findings, 10 distinct
regulation-passage pairs, all 10 on the sheet; plan and seed committed before the run). The check
set aside 3 of the 7 "gap" labels on findings: in two the policy, approved March 2026, states
the duty in another passage; one (RBI 65(5)) does not apply to a scheduled commercial bank and
counts as a false positive. Two first-pass set-asides (rows 5 and 15) failed the three-part test
and were reversed: row 5's passage adds a precondition before an STR is considered, row 15's
excludes Aadhaar OTP e-KYC accounts. On the third bank most high-confidence findings were duties the policy states in a different passage from the one the system compared, so its high-confidence tier was weak there. Over three banks: 21 of 28.

On Central Bank and Dhanlaxmi the check set aside no "gap" label on a finding. It set aside three
on covered pairs; re-tested on 4 Oct, two failed the three-part test and were reversed (Central
Bank row 9, planted gap C05; Dhanlaxmi row 7), and one stands. Most real gaps are provisions the 2024 policies predate. Several are procedure or
system details (photograph capture, application messages) rather than policy statements. The
development bank's newer policy gave a much weaker result for the same tier (3 real, 7 false
alarms, 4 unclear of 14), so precision depends on how far the policy lags the regulation.

What it shows:
- **Numbers are found; omissions and contradictions are not.** The high-confidence hits are
  changed or stale thresholds (7 of 7 across the three banks). Deleted duties were missed on all
  three banks (0 of 4), and contradictions and the removed owner on the first two.
- **The high-confidence tier is precise about what it finds, not complete.** Every exact hit was
  high-confidence, but that tier also holds 15 and 42 other reports, most of them unchecked.
- **The code-level scan mattered.** The extraction model flagged neither hidden instruction;
  the scan, written before the held-out keys were opened, flagged both.
- **The judge's own confidence number misleads** (confidence checks in `eval/reports/`): at
  1.00 it called five Central Bank and two Dhanlaxmi planted-gap mappings covered.
- **"Judge and text comparison agree" is the most reliable signal**: 4 of its 5 findings on the
  two banks were planted gaps, the fifth a stricter-number decoy.
- **A parser limit found after the freeze.** On Dhanlaxmi, control extraction covered about 8%
  of the policy text: the unit builder turns few of its 4.1.2-numbered clauses into units. The
  judge still compared every passage (passages are candidates), but extraction-based checks saw
  little of the policy. Not fixed: fixing it after seeing the result would be tuning on the
  test.

### Confidence

The judge returns a number from 0 to 1 with each verdict. It is stored and not shown. Measured on
the development bank against the answer key and the 50 adjudicated pairs
([table](../eval/reports/confidence_table.json)):

| Judge's number | Verdicts | With a known answer | Right |
|---|---|---|---|
| 1.00 | 269 | 27 | 25 |
| 0.95 to 0.99 | 118 | 15 | 13 |
| 0.80 to 0.94 | 54 | 7 | 4 |
| below 0.80 | 17 | 3 | 1 |

The number mostly restates the verdict: every checked verdict at 1.00 was "covered", nearly every
one below 0.95 was a gap, and two planted gaps were passed as covered at 1.00. The prompt asks for
"confidence between 0 and 1" without saying confidence in what. It is left as it is, because
rewording it means judging every obligation again.

Each finding instead carries a note built from checks that code can verify
([`confidence.py`](../src/regcomp/confidence.py)): an evidence test failed; the judge and the text
comparison agree; the text comparison found a difference the judge had passed; the judge alone;
the judge contradicted by near-verbatim policy text; and whether the policy citation was verified.
Each combination shows its record on the development bank as counts. Two cautions: most findings
of each kind are not adjudicated, and many adjudicated ones are gaps we planted, which are real by
construction. The records are therefore not hit rates. The "judge alone" findings of the
high-confidence tier are the best measured: of 21, 7 are real (3 planted), 8 are false alarms
and 6 are not adjudicated. The table is fitted on the development bank only and frozen before the
held-out runs, which are then reported against it.

### Integrity disclosures

- **Same toolchain.** The answer keys were authored with the same AI coding assistant that helped
  build the system. Mitigations: edits are hand-written and applied by a script; every item was
  reviewed by the author; a redundancy check (lexical and semantic) confirmed that no other
  passage still satisfies each altered obligation; keys were committed before any run; prompts
  are generic.
- **Rules written after development misses.** The wording comparison was designed on 2 Oct after
  studying which planted gaps the development run missed. Development numbers therefore flatter
  it; the held-out banks are the test.
- **Labels.** A blind sheet of 50 obligation and passage pairs was labelled by two AI models
  independently (36 of 50 agree on whether the passage satisfies the requirement) and the author
  decided the disputed rows. Checking each "gap" against the full policy text showed 12 of 15
  were covered elsewhere: the judge had not been shown the right text. That finding led to
  offering every policy passage as a candidate.
- **Obligation level is a convention.** The two labellers agree on 30 of 50 rows about what is
  policy-level. Level therefore routes items to review and is not reported as an accuracy figure.
- **Correlated error.** The redundancy check and the pipeline both use bge-m3; a passage both
  miss would make a planted gap look valid. Lexical search and manual reading reduce this.
- **Bank profiles.** The profiles of all three banks are built by a script from the published policies and were committed (`c286fd7`) before any held-out run; no model read the held-out policies. The vocabulary behind them was written from the regulation's own conditions. A profile lists what a policy mentions, which is weaker than what the bank offers: a policy that restates the regulation mentions almost everything, so the stage excluded nothing on the banks tested (no profile states an absence) and no precision gain is claimed from it. The step has no accuracy number of its own: a blind label sheet of 50 conditions was prepared and, by the author's decision, not labelled, because no label could change any result. The what-if in the app is hypothetical.
- **Held-out precision sheets (3 Oct).** Labelled by the author after the freeze, blind to the system's verdict (half the rows were covered pairs); the written reason for each row was drafted with help from an AI model (Gemini). Every "gap" label was checked against the whole policy by Claude, who also chose which labels the check overturned. Measurement only: no code or threshold changed.
- **High-confidence check sheet (3 Oct).** The 14 high-confidence findings that neither the
  answer key nor the 50-pair sheet had settled were mixed with 7 covered pairs and labelled
  by the author from the two texts shown, with an AI model (Gemini) helping to write the
  reason for each row. The sheet was not blind to the system's call: two thirds of its rows
  were findings. Every row labelled "gap" was then checked against the
  whole policy (`scripts/full_policy_check.py`): 3 of 8 held, 5 were covered elsewhere.
  Result for the 14 findings: 3 real, 7 false alarms, 4 unclear. One covered pair was
  labelled "gap" (a policy that says "should have" where RBI says "shall have"); it is
  borderline and left as covered.
- **Real findings** in the published policies are labelled separately and scored by their own
  rules, never as false alarms. A real gap that shares an obligation with a planted one counts
  neither way.

## 7. Safeguards

| Risk | Safeguard | Status |
|---|---|---|
| Invented citations | Quotes are cut from the source by position | Built |
| Changed numbers or lost duties | Wording comparison; fidelity check on remediation drafts | Built |
| Instructions hidden in a document | Documents are passed as data and never followed; flagged by the extraction model and by a code-level scan that needs no model | Built. The model alone flagged 1 of 2 on the development keys; the scan, written after that, flags both and nothing in the unaltered policy |
| Over-confident output | Two tiers and a review queue | Built |
| An agent that writes too much | Dry run cannot reach the write step; pause above 20% of mappings; versioned writes, nothing deleted | Built |
| Machine closes a gap | Only a reviewer confirms, dismisses, resolves or accepts; name and reason recorded | Built |
| Evidence leaking to a model | Tests run in code; the model sees no rows | Built |
| Private data reaching a model | Only public or synthetic data is used | A working rule, not enforced by code |
| Runaway cost | Exact-match cache; time budget per run | No per-event spending cap |
| Bias | See below | Measured; mitigated by review |

**Bias.** No personal data is processed: the inputs are public regulations, public bank policies
and synthetic evidence logs that carry identifiers only, so there are no customers or groups to
treat unequally. The bias we measured is the model's: it leans towards "covered". Most misses on
the unseen banks are false "covered" verdicts: all four deleted duties, the narrowed scope C05
("savings accounts" read as "accounts") and the limit in a list lead-in (L03). The system is built
to fail safe against that lean: doubtful findings go to a review queue, the system never closes a
gap itself, and a person confirms, dismisses or accepts every finding with a name and a reason.

## 8. Deployment

- **Pipeline:** local (Ollama, Postgres 18 + pgvector on Neon). Long runs stop at a time budget
  and resume from the cache. `docker-compose.yml` starts a local database with the schema.
- **Demo:** Streamlit Community Cloud, reading the same database. It has no GPU: model steps use
  the hosted model, and candidate search falls back from embeddings to shared wording. A visitor
  cannot change data; a reviewer decision is saved only with a reviewer code.
- **The demo never writes.** The change agent runs dry in the hosted app; the commit step (a new
  version stored beside the old, old rows closed in time) is tested offline, and one commit of the change agent and two reviewer decisions, recorded on a copy of the database (d2, development data), are shown read-only.
  The evidence batch is tested in memory; new analyses run offline. Evidence is synthetic and
  covers two controls of the development bank.
- **Inputs.** One regulation end to end (the RBI KYC Directions, HTML and PDF) and published bank
  KYC/AML policies (PDF). No control libraries, SOPs, RCSA registers or test records, and no
  upload in the hosted app: a new policy runs offline (about 1,190 model calls and about 55
  minutes on one laptop GPU, measured on the third bank).
- **In a bank:** the same components inside the bank's network: Postgres, an internal model
  server, the policy and evidence never leaving it.

## 9. Limits and what comes next

- Detection is measured on 7 planted gaps per bank. Most high-confidence extras on the
  development bank are false alarms (of 14 checked by hand: 3 real, 7 false, 4 unclear), mostly
  duties the policy states elsewhere or in a different sentence structure.
- A removed owner is not detected on plain policy passages.
- Applicability missed an obligation that does not apply: RBI 65(5) binds lenders other than
  scheduled commercial banks, yet it was raised as a high-confidence gap on the third bank.
- One regulation end to end; nine others only for change detection. Text input only.
- No cross-regulation analysis and no detection of contradictions between regulations.
- No document routing: a person chooses which policy is checked against which Direction.
- Conflicts inside one policy: a code-only check for two passages restating one RBI sentence with
  different numbers or periods found the 3 planted numeric contradictions on the development keys
  and flagged nothing else, a best case since its rules were written on those keys
  ([report](../eval/reports/policy_conflicts_dev.md)). Next: conflicts in wording (planted S04),
  then between regulations.
- Next: a bank profile built from independent facts (licences, product lists) instead of the policy's own text, so that applicability can exclude; a design check for owners the regulation itself names; a wider comparison for reworded
  sentences; more than one development bank.

## 10. Claim

**F3 / D1**, against the brief's definitions.

**F3 needs at least 8 of 14 features. We show 11 of 14: 9 on real policies, plus 6 and 7 on development data with synthetic logs**, all in the live demo: 1, 2, 3, 5,
8, 9, 10, 11, 12, then 6 and 7 (see the feature → stage map in §2).
Partial: 4 (policy text, not a control library). Not claimed: 13, 14.

**D1 (acceptable outputs in a majority of situations)**, three unseen banks, frozen v1, per output
type:

- reported outputs acceptable: high-confidence findings real in blind samples after the
  full-policy check 8 of 9, 9 of 9, 4 of 10 (21 of 28 overall);
  hidden instructions caught 3 of 3;
  decoys left alone 7 of 9 (first scoring 6 of 9, see the third bank's report); real findings
  handled 4 of 4;
- a majority of planted gaps raised at the right obligation, 11 of 20 (9 of 20 at the exact
  passage); every changed number found, 7 of 7;
- blind spot, disclosed: deleted duties 0 of 4.

**Not D2.** D2 needs a high degree of demonstrable reliability; omitted duties are not found, and a
pre-registered attempt at D2 stopped at its own gate on development data (closing note on the
unmerged `d2` branch).
