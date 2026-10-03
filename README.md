# RegCompliance Agent

Keeps a bank's KYC policy traceable to the regulation it implements: it reads an RBI Direction and
a bank's policy, finds where the policy falls short, shows the evidence for each finding, and when
the regulator amends a rule it re-checks only what the amendment touches.

Built for the **ET AI Hackathon 2026: Agentic Edition (presented by Accenture), Problem 1:
Banking / financial regulations**.

**Live demo:** <https://regcompliance-agent-gg39o3vts7mzhbtds2u6l7.streamlit.app/>
(add `?scenario=2` to open the change agent on the what-if draft circular)

## The problem

Regulations → obligations → applicability → internal policies and controls → evidence → testing →
gaps → remediation → ongoing monitoring. A compliance team has to keep that chain intact while
both ends keep changing. Today it is spreadsheet work, redone after every amendment.

## What it does

| Step | How | Who decides |
|---|---|---|
| Read the regulation | A parser splits the RBI Direction into numbered clauses with exact character positions | Code |
| Read the bank policy | Docling layout parsing, then the same clause tree | Code |
| Extract obligations and controls | An open-weights model returns structured items; every quote is sliced from the source by position, so it cannot be invented | Model proposes, code verifies |
| Decide applicability | Each obligation's limiting condition is matched against a bank profile built from the bank's own policy; an obligation is excluded only when the profile states the bank does not offer what the condition names | Code |
| Find policy text for each obligation | Embedding search over extracted controls **and** every raw policy passage | Code |
| Judge coverage | A model gives a verdict and an issue; fixed rules turn that into a gap type | Model judges, code decides |
| Compare the wording | Near-identical sentences are compared directly: numbers, "shall" against "may", inserted conditions | Code |
| Sort into two tiers | High-confidence gaps and a review queue | Code |
| Test controls against evidence | Exception rates from logs against a tolerance | Code |
| Rank by risk | A rubric file: the subject sets the level, the gap type scales it | Code |
| Draft remediation | A model drafts; code sets owner and due date and rejects wording that drops a number or a duty; one remedy per regulation paragraph | Model drafts, code checks |
| Cite the source | Every finding carries the document, paragraph, RBI reference number, issue date, version date, amendment date and link, read from the stored source record | Code |
| Say how sure | A note built from checks code can verify (text comparison, citation, evidence test), with the record of that kind of finding as counts; the model's own confidence number is not shown | Code |
| React to an amendment | A LangGraph agent: diff → classify → scope → re-extract → re-map → compare → commit, with checkpoints and retries; a dry run is the what-if mode | Agent, within fixed rules |
| Monitor | A new evidence batch is tested against the last result; a reviewer confirms, dismisses, resolves or accepts | Code and a person |

The system opens gaps. Only a person closes one or accepts a risk.

## Results (counts)

Known gaps were planted in public bank policies before any model run, together with decoys that
must not be flagged and one hidden instruction each. The development bank was used to build the
system. The two other banks were run once, from a clean checkout of the tag
`eval-freeze-2026-10-03`, and nothing was tuned afterwards
([Central Bank](eval/reports/heldout_centralbank_report.md),
[Dhanlaxmi](eval/reports/heldout_dhanlaxmi_report.md)).

**Proven on two banks the system had never seen** (each run once, counts):

- every weakened number and stale threshold was found: **5 of 5**, all in the high-confidence
  tier (3 of 5 with the right gap type);
- hidden instructions in the policy: **2 of 2** caught, both by the code-level scan;
- real findings in the published policies: **3 of 3** handled correctly;
- decoys (rewordings and stricter numbers) left alone: **5 of 6**;
- change detection against RBI's own amendment markers: **2 of 2** on the KYC Direction and
  **262 of 266** amended clauses on nine other Directions.

**Not yet, the next milestone:** deleted duties 0 of 2, narrowed scope 0 of 2, contradictions
0 of 2 (one found at the right obligation), a removed owner 0 of 1, a duty made optional 0 of 1
(found at the right obligation). Overall: 5 of 13 planted gaps at the exact passage, 7 of 13 at
the right obligation. Claim: **F3 / D1** (see the architecture document for why not D2).

| Measure | Development bank | Central Bank (unseen) | Dhanlaxmi (unseen) |
|---|---|---|---|
| Planted gaps found at the exact passage | 5 of 7 | 3 of 7 | 2 of 6 |
| ...of which in the high-confidence tier | 3 | 3 | 2 |
| Planted gaps found at the right obligation | 6 of 7 | 4 of 7 | 3 of 6 |
| Decoys flagged: high-confidence / review | 0 / 1 of 3 | 1 / 0 of 3 | 0 / 0 of 3 |
| Hidden instruction flagged | 1 of 1 | 1 of 1 | 1 of 1 |
| Other reports: high-confidence + review | 17 + 38 | 15 + 36 | 42 + 43 |
| Applicability: obligations excluded | 0 of 458 | 0 of 458 | 0 of 458 |

The other reports (15 and 42 high-confidence on the unseen banks) are not yet adjudicated; a
blind precision check on a sample of them is in progress. On Dhanlaxmi, control extraction
covered only about 8% of the policy text (its clauses are numbered 4.1.2-style): the judge still
compared every passage, but extraction-based checks saw little of it. That was found after the
freeze and is not fixed. Evidence tests: 2 of 2 on the development bank.

**A second answer key on the same bank** (4 planted gaps, 3 decoys, 1 injection, on passages picked by a seeded draw and written after the comparison rules) checks whether those rules hold on gaps they were not written for. Result: 3 of 4 planted gaps found, all three in the review queue and none in the high-confidence tier; the contradiction was missed; the stricter-number decoy was flagged in the review queue; the injected instruction was not flagged (0 of 1). Two causes were fixed afterwards, from the general principle and before the freeze: the number comparison ignored the number one ("one year" against "two years"), and instruction detection depended on the extraction model noticing the text; a code-level scan now checks every sentence. With both fixes the first key's results are unchanged, and the second key reads 3 of 4 found (1 high-confidence) and the injection flagged. That second reading is not a test, because the fixes were made knowing its misses.

Read these with two cautions. The wording-comparison rules were written after studying this bank's
misses, so they fit it well. And the high-confidence extras are mostly false alarms: of 14
high-confidence findings that nothing else had settled, the author's check (helped by an AI model,
with every "gap" label verified against the full policy) found 3 real gaps, 7 false alarms and 4 unclear
([error analysis](eval/reports/error_analysis_e2e11.md)). Two banks the system
has never seen are scored once, at the freeze; their answer keys were committed before any model
read those policies. Those results will be added here.

## Business impact (measured time, estimated baseline)

Change agent, dry run, per circular ([timing](eval/reports/change_agent_timing.json)):
on one laptop GPU (RTX 4060, local qwen3:8b) 1.7 s for a permissive amendment (no model call),
27 s for the Dec 2025 amendment and 17 s for the draft circular, about 81 s on a first, uncached
run; with the hosted open-weights model 1 to 22 s. Baseline: 5 to 10 analyst hours per circular,
the author's own estimate, not a measurement. The agent produces a scoped draft assessment; a
person still reviews it.

## Data (all public or synthetic)

- **Regulation:** RBI (Commercial Banks – Know Your Customer) Directions, 2025, in three real
  versions (28 Nov 2025, and after the amendments of 29 Dec 2025 and 18 Sep 2026), plus nine other
  RBI Directions used only to test change detection.
- **Bank policies:** the published KYC/AML policies of Nainital Bank (development), Central Bank
  of India and Dhanlaxmi Bank (both held out).
- **Evidence:** synthetic logs with identifiers only.
- **A synthetic draft circular** for the what-if demo: one invented sentence added to the current
  Direction, clearly marked.
- Provenance, source URLs and sha256 for every file: [`data/sources.yaml`](data/sources.yaml).
  Raw files are stored byte-identical so citation positions stay valid.

## Run it

```bash
uv sync                         # core
uv sync --extra pdf             # adds Docling for PDF parsing (large)
uv run pytest                   # 126 tests
```

The pipeline, on the development bank (needs Postgres with pgvector, and Ollama with `qwen3:8b`
and `bge-m3`; copy `.env.example` to `.env`):

```bash
uv run python scripts/run_extract.py --run demo            # obligations and controls
uv run python scripts/run_level.py --run demo              # obligation level
uv run python scripts/run_map.py --run demo --passages --dense-only --stop-after-min 25
uv run python scripts/load_metadata.py                     # source metadata for citations
uv run python scripts/run_tests.py                         # design and operating tests
uv run python scripts/run_verify.py                        # wording comparison and tiers
uv run python scripts/run_applicability.py --apply         # applicability by bank profile
uv run python scripts/run_risk.py                          # risk ranking
uv run python scripts/run_remediation.py --top 10          # remediation drafts
uv run python scripts/clean_remediation.py --apply         # one remedy per paragraph
uv run python scripts/score.py --run demo                  # against the answer key
```

Every model call is cached, so a stopped run resumes where it left off and a repeated run is
free. The change agent and the app:

```bash
uv run python scripts/run_change.py --old data/raw/rbi/kycdir_v2_20251229.html \
    --new data/raw/rbi/kycdir_v3_20260918.html --dry-run
uv run python scripts/run_evidence.py                      # a new evidence batch arrives
uv run python scripts/review.py                            # the review queue
uv run streamlit run app/streamlit_app.py
```

Any stage can be moved to a hosted open-weights model with one setting, for example
`REGCOMP_MODEL=groq:openai/gpt-oss-120b`. The deployed app runs that way, because it has no GPU.

## Layout

```
src/regcomp/ingest/     parsing: RBI HTML, Docling PDFs, clause tree
src/regcomp/pipeline/   extraction, citation gate, judge and gap rules, passages, wording comparison
src/regcomp/change/     clause diff, change classification, scope, the agent, versioned writes
src/regcomp/            evidence tests, monitoring, risk rubric, remediation, reviewer decisions, LLM access
scripts/                one script per pipeline stage, the evaluation tools
app/                    the Streamlit demo
db/                     Postgres + pgvector schema and migrations (versioned rows, nothing deleted)
data/                   public sources, planted-gap specifications, rubric and triage settings
eval/                   answer keys and published reports
docs/                   architecture, plan, how the test sets were built, decision records
```

## Safeguards

- **Citations cannot be invented.** The model names where a sentence starts; code cuts the quote
  from the source.
- **Numbers and duties must survive.** Wording comparison and remediation drafts check that every
  number and every "shall / shall not" is kept.
- **Instruction-like text in a document is treated as data, never followed.** It is flagged by the
  extraction model (1 of 2 on the development keys) and by a code-level scan that needs no model
  (0 false flags on the unaltered development policy).
- **Dates and references come from the source record.** A citation's fields are read from the
  stored document data and RBI's own amendment markers, never from a model.
- **Two tiers.** Anything the comparison contradicts, anything procedure-level and anything
  technical goes to a review queue instead of being asserted or silently dropped.
- **Read-only what-if.** A dry run has no path to the step that writes; a large change pauses for
  a person.
- **Evidence stays in code.** The model never sees evidence rows, only counts.

Not enforced by code: the rule that only public or synthetic data reaches a model is a working
rule of this project, and there is no per-event spending cap.

## Limits

- Gap detection is measured on small sets (7 planted gaps per bank); results are counts, not
  statistics.
- The comparison rules were written after studying development misses.
- "Policy-level or procedure-level" is a convention: two independent labellers agreed on 30 of 50
  rows. The system routes such items to review rather than deciding.
- One regulation end to end; text input only. A person chooses which policy is checked against which Direction.
- A bank profile lists what the bank's policy mentions. A policy that restates the regulation mentions almost everything, so the applicability step excluded nothing on the banks tested, and no precision gain is claimed from it. The what-if in the app is hypothetical: it shows what would drop out if a bank stated it did not offer something. A profile built from independent facts is on the roadmap.
- The hosted demo depends on free tiers (a daily token cap for the hosted model).

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/mutation_taxonomy.md`](docs/mutation_taxonomy.md), [`docs/adr/`](docs/adr/).

## AI assistance disclosure

Most of the code was written with **Claude Code** (Anthropic) as a coding assistant, under the
author's direction; the author made the scope, data and evaluation decisions and reviewed the
planted-gap answer keys. The 50-pair check sheet was labelled blind by two AI models (Claude and
Gemini) and the author decided the disputed rows. The system itself runs on open-weights models.

## Acknowledgements

Some patterns (Docling parsing, retry with fallback, LangGraph Postgres checkpointing) were
informed by the public "8-hour marathon" RAG sessions and their repositories
([d-hackmt/8hr-MARATHON](https://github.com/d-hackmt/8hr-MARATHON),
[sourangshupal/8hr-MARATHON](https://github.com/sourangshupal/8hr-MARATHON)). No code was copied.

## Licence

[Apache-2.0](LICENSE)
