# Project plan: submit Sat 10 Oct 2026

Hard deadline is 11 Oct 23:59 IST. Target is **Sat 10 Oct, 15:00**; Sunday is the emergency
buffer only.

Revision 2 (26 Sep, 20:14): adds the Fri 2 Oct holiday, reflects what the corpus work found,
and folds in the patterns adopted from the reference material (section 3).
Revision 3 (26 Sep, 20:40): aligned with the Unstop rules (section 7) and adds the guardrails
layer (section 3a).

## 1. Status and budget

- **Against the original CLAUDE.md schedule:** 3 days behind. The corpus was due 23 Sep,
  schemas 24 Sep, answer key 25 Sep.
- **Against this plan:** schemas, DDL, taxonomy, the corpus (3 real regulation versions) and
  theme verification are done. The answer key is due Sun 27 Sep.
- **Blocked on the user:** Docker/WSL2, API key, choosing the 2 bank policies.

| Block | Days | Hours |
|---|---|---|
| Weekend 27 Sep | Sun | 9 |
| Weekdays 28 Sep – 1 Oct | Mon–Thu | 4 x 3 = 12 |
| **Holiday 2 Oct (Gandhi Jayanti)** | Fri | **9** |
| Weekend 3–4 Oct | Sat–Sun | 18 |
| Weekdays 5–9 Oct | Mon–Fri | 5 x 3 = 15 |
| Submission day | Sat 10 Oct | 6 |
| **Total** | | **~69 h** |

The holiday buys one full build day before the weekend. It goes to the change agent, the
riskiest component, so it starts on Friday instead of Saturday.

## 2. What we are building, in plain terms

Two documents go in: the regulation (RBI Commercial Banks KYC Directions, 2025) and a bank's
KYC policy. The questions to answer: *which rules does the bank's policy fail to cover, how
badly, and what changes when RBI amends a rule?*

```
 RBI Directions (HTML/PDF) ──parse──> paragraphs ──LLM extract──> obligations ─┐
                                                                               ├─ bge-m3 top-20 -> FlashRank top-5 -> LLM judge
 Bank KYC policy (PDF) ──Docling──> sections ──LLM extract──> controls ─────────┘        (covered / partial / missing)
                                                                                                 │
 synthetic evidence CSVs ─────────> operating test ────────────┐                                 │ citation gate
                                                               v                                 v
                                                gaps (deterministic rules) -> risk score -> remediation (LLM)

 RBI amendment arrives ──> CHANGE AGENT (LangGraph): normalize -> diff -> classify -> re-extract changed paragraphs
                           -> re-map only affected edges -> new / closed gaps -> remediation
                           (same agent with dry_run=True on a draft circular = what-if)
```

The LLM reads and judges. Deterministic code parses, checks every citation verbatim, and
computes risk. That split is the "high demonstrable reliability" argument for D2.

Two real amendments drive the demo: 29 Dec 2025 (CKYCR reliance) and 18 Sep 2026 (FPIs added
to the certified-copy route). See `data/sources.yaml`.

## 3. Stack

| Piece | Choice | Source / reason |
|---|---|---|
| DB | Postgres 16 + pgvector in Docker (fallback: Neon free tier) | CLAUDE.md |
| Regulation parsing | HTML (BeautifulSoup) for v2/v3; Docling for PDF v1 | HTML is clean; Docling fixes PDF word-splitting noise (P-012) |
| Policy parsing | **Docling** (layout + tables, no OCR) | reference session 2; policies contain tables |
| LLM routing | LiteLLM in-process; cheap = Claude Haiku 4.5, strong = Claude Sonnet 5 | provider to confirm |
| Embeddings | bge-m3 local (sentence-transformers) | CLAUDE.md |
| Reranker | **FlashRank** (local, CPU) with fall-back to embedding order on failure | reference session 1 |
| Agent | LangGraph + Postgres checkpointer | reference repo has working checkpointer code |
| Tracing | Logfire free tier; configure before imports, lazy-load models | reference repo gotchas |
| Retries | tenacity (exponential backoff), then escalate | reference repo pattern |
| Cache | exact-match table in Postgres | CLAUDE.md (never semantic cache) |
| UI | Streamlit; replay mode can deploy to Streamlit Community Cloud if a live URL is required | reference repo `st_cloud_ui.py` |
| **Not used** | Qdrant Cloud, Portkey, NeMo guardrails, AWS ECS, Batch API, Jev; RAGAS only as an optional extra metric on rationales | conflict with settled design or budget |

## 3a. Guardrails (how they apply to a compliance agent)

Chatbot-style topic rails (NeMo) do not fit: there is no open chat surface. The real risks are
poisoned inputs, fabricated outputs and unsafe agent actions, so the guardrails sit there.
Each one produces a number for the metrics page.

| Layer | Guardrail | How | Metric | Built |
|---|---|---|---|---|
| Input | Indirect prompt injection in ingested docs (policies, draft circulars, feed items) | Documents always passed as delimited data. A deterministic scanner flags instruction-like text ("ignore previous", role/system phrases, "mark as covered") and quarantines the clause with a reviewer flag | Detection of planted injections; false flags on clean docs | Sun 27 (plant), Mon 28 (scanner) |
| Input | Data egress | Only documents listed in `data/sources.yaml` or synthetic data may be sent to an LLM (allowlist check before each call) | Blocked-call count | Mon 28 |
| Output | Schema | Strict Pydantic JSON; one repair-retry, then escalate | Repair rate | Mon 28 |
| Output | Hallucinated citations | Citation gate: quote must equal `doc.text[start:end]` | Citation validity, rejection count | Wed 30 |
| Output | Number and negation fidelity | Extracted threshold values must appear in the cited span; `must_not` requires a negation in the span | Mismatch rejections | Wed 30 |
| Output | Low-confidence verdicts | Judges disagree or low confidence -> strong model -> human review queue | Auto-accept rate vs accuracy | Fri 2 |
| Action | Least privilege | What-if mode gets read-only tools; only commit mode can write to the graph | Test: dry-run cannot write | Sat 3 |
| Action | Blast radius | If a change event touches more than N% of mappings, the agent pauses for human approval | Pause count | Sat 3 |
| Action | Humans in the lead | Agent may open gaps and draft remediation; closing a gap or accepting risk needs a reviewer | Reviewer actions logged | Sun 4 |
| Action | Budget | Max tool calls / tokens / USD per change event -> escalate | Cost per circular | Sat 3 |
| Data | PII in evidence | The LLM never sees raw evidence rows; the operating test is computed deterministically and only aggregates reach the LLM | Zero raw rows in prompts (trace check) | Sat 3 |

The hackathon's own framing ("humans in the lead") and evaluation criterion 8 (hallucination,
security, privacy, reliability, human oversight) map directly onto this table. It gets its own
page in the deck.

## 4. Who does what

Claude writes the code, tests and docs, explains each component as it is built, runs the
pipeline, and keeps the metadata logs updated. **Only you can do these:**

| When | Task | Time |
|---|---|---|
| Tonight / Sun AM | Install WSL2 + Docker Desktop; create an API key with a spend cap | 1 h |
| Tonight / Sun AM | Choose 2 of the 3 policy candidates (exclude your employer) | 5 min |
| By Mon | Employer code of conduct (outside activities, IP clause) | 30 min |
| By Mon | Post the AI-tools question in the Unstop Discussions tab (draft in PROJECT_LOG 20:44); open the logged-in Phase 2 "Submit" form and note every field; read the ET microsite (Claude cannot open it) | 30 min |
| Sun 27 | Review planted mutations for realism | 1 h |
| Mon 28 – Tue 29 | **Blind-label ~30 obligation-to-control mappings** (15 per day) | 2 x 1 h |
| Wed 7 | Manual baseline estimate: analyst hours per circular | 15 min |
| Fri 9 – Sat 10 | Record the video, submit | 3 h |

## 5. Feature claim strategy

| Tier | Features | Built on |
|---|---|---|
| **Floor (the 8 that make F3)** | 1 ingestion, 3 obligation extraction, 4 control understanding, 5 mapping, 8 gap identification, 9 risk prioritization, 2 change intelligence, 11 autonomous impact analysis | core pipeline + change agent |
| Stretch (cheap, shared machinery) | 10 remediation, 7 evidence-based assessment, 6 design vs operating effectiveness, 12 what-if | one LLM call; CSV + rules; dry-run flag |
| Declared not covered | 13 cross-regulation (the PML Rules are referenced but not ingested), 14 contradiction detection | none |

Internal contradictions *within* a bank policy are a planted mutation. That is not feature 14.
The final claim is decided on **Wed 7 Oct** from the evidence matrix.

## 6. Schedule

| Day | Hrs | Work | Exit criterion |
|---|---|---|---|
| ~~Sat 26 Sep~~ | 3 | ~~Schemas, DDL, taxonomy, plan~~, ~~RBI corpus (3 versions), theme verification, docker-compose~~ | Done |
| **Sun 27 Sep** | 9 | Regulation parser (HTML v2/v3 + Docling v1) with clause-level normalization; policy parser (Docling); loader into Postgres; `spec.yaml` (~25 mutations + 8 decoys + 1 injection plant), `mutate.py`; **answer key committed and pushed** | Answer key on GitHub before any LLM run; v1->v2 clause diff shows 1 real change, not 500 |
| Mon 28 Sep | 3 | LiteLLM + exact cache + Logfire wiring; obligation extraction (single pass, strict JSON) on the 6 theme chapters. You: label 15 | Obligations in DB, all spans verified |
| Tue 29 Sep | 3 | Control extraction; bge-m3 embeddings; FlashRank rerank to top 5. You: label 15 | Candidates per obligation |
| **Wed 30 Sep** | 3 | Mapping judge, citation gate, gap rules, **first end-to-end run** | Gap list for one policy. **CHECKPOINT 1** |
| Thu 1 Oct | 3 | Eval harness v1: gap P/R per operator, decoy FP rate, citation validity, extraction P/R vs your labels | First metrics table |
| **Fri 2 Oct (holiday)** | 9 | AM: tiering (agree + high confidence -> auto, else strong model -> review queue), second extraction pass, risk rubric. PM: **change agent part 1** (LangGraph skeleton, normalize/diff/classify, Postgres checkpointer) | Agent classifies both real amendments correctly and ignores cosmetic noise |
| **Sat 3 Oct** | 9 | **Change agent part 2**: re-extract, re-map affected edges only, recovery (repair-retry, escalate, cannot-assess), open gaps + remediation; injected-failure test. Evidence CSVs + design/operating tests | Agent handles the Sep 2026 amendment end to end, including one recovered failure |
| **Sun 4 Oct** | 9 | What-if dry-run on a synthetic draft circular; reviewer override -> few-shot feedback; injection flagging; remediation polish; eval re-run | All claimed features exist. **CHECKPOINT 2** |
| Mon 5 Oct | 3 | Streamlit: bank profile, gap dashboard, "why" panel, review queue | Core demo path clickable |
| Tue 6 Oct | 3 | Streamlit: change timeline, metrics page (including the guardrail report), graph view; replay mode; **deploy replay to Streamlit Community Cloud** (the rules make an accessible demo link mandatory) | Public demo URL works without API keys |
| **Wed 7 Oct** | 3 | **FEATURE FREEZE.** Final eval, calibration plot, cost/latency; evidence matrix; decide claim | Numbers and claim frozen |
| Thu 8 Oct | 3 | Architecture document (`docs/ARCHITECTURE.md`) + **pitch deck** (PDF, 10-12 slides). **Submit v0 on Unstop tonight** (it can be replaced until the deadline) | Deck PDF; v0 submitted |
| Fri 9 Oct | 3 | Rehearse; record the **2-4 minute** video (hard limit); upload unlisted and check the link while logged out; README / run instructions + AI-assistance disclosure | Video link works publicly |
| **Sat 10 Oct** | 6 | Fix what the rehearsal exposed; check all links logged out; **final submit by 15:00** (edits allowed until 11 Oct 23:59) | Submitted |
| Sun 11 Oct | - | Emergency buffer only | - |

### Checkpoints and cuts

- **Wed 30 Sep, no end-to-end run:** single-pass extraction only, one judge, drop the second
  pass on Fri 2 Oct, and use the whole holiday on the change agent.
- **Sun 4 Oct, agent unstable:** reduce it to diff -> graph query -> re-map with recovery;
  cut what-if (feature 12).
- **Docker still unavailable on Sun 27 midday:** switch to Neon (about 15 min). Parsers do not
  need a DB, so Sunday morning is unaffected.
- **Cut order when slipping:** UI polish -> graph view -> reviewer feedback loop -> what-if ->
  remediation depth -> evidence/effectiveness (6/7). The public demo link is no longer
  optional.
- **Never cut:** answer key before first run, citation gate, eval harness, change agent,
  evidence matrix.

## 7. Submission package

Unstop rules, read 2026-09-26:
- Deliverables: a working prototype (public GitHub URL), a **pitch deck (PDF or PPT)** and a
  **2-4 minute demo video**.
- Uploads in .pdf, max 50 MB. One solution per team.
- All links public. Editable until the deadline; no late submissions.
- Top 10 go to a virtual National Finale.

1. **Public GitHub repo:**
   - README with a one-command run and the public demo URL.
   - The answer-key commit hash.
   - A statement that all data is public or synthetic.
   - An **AI-assistance disclosure** (Claude Code as coding assistant; LLM APIs used inside the
     system).
   - **Attribution** for patterns taken from the reference repos. The rules make plagiarism a
     disqualifier, so we reuse ideas with credit and never copy code verbatim.
2. **Pitch deck (PDF, 10-12 slides):**
   - Problem and business impact.
   - Architecture (process flow, agent graph, model per stage).
   - Reliability and guardrails.
   - Metrics.
   - Evidence matrix.
   - Grid claim F3/D2 with justification. The problem statement's "detailed structural
     architecture" deliverable lives here plus `docs/ARCHITECTURE.md`.
3. **Demo video, 2-4 minutes** (hard limit). The CLAUDE.md script is cut to fit:
   - Bank profile -> gaps with citations and one "why" panel (45 s).
   - Amendment arrives -> agent plans, re-maps, recovers from one failure, opens remediation
     (75 s).
   - What-if (20 s).
   - Reviewer override (20 s).
   - Metrics and guardrail report (30 s).
   - Evidence matrix (10 s).
4. **Accessible demo link:** replay mode on Streamlit Community Cloud. It needs no API keys and
   no database.
5. **Grid claim F3/D2**, justified by the matrix. Never D3 (no multimodal input).

## 8. Open decisions

- LLM provider/key. Plan assumes Anthropic; LiteLLM makes it swappable.
- Docker Desktop (recommended) vs Neon.
- Which 2 of Nainital / Central Bank of India / Dhanlaxmi (exclude employer).
- Organisers' answer on commercial LLM APIs. Until then, keep every stage runnable on an
  open-weights model via LiteLLM (config change only).
- Whether the public repo should keep `CLAUDE.md`, which says you work at a bank. Recommend
  keeping it but removing that phrase.
