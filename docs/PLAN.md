# Project plan: submit Sat 10 Oct 2026

Hard deadline is 11 Oct 23:59 IST. Target is **Sat 10 Oct, 15:00**; Sunday is the emergency
buffer only.

Revision 2 (26 Sep, 20:14): adds the Fri 2 Oct holiday, reflects what the corpus work found,
and folds in the patterns adopted from the reference material (section 3).
Revision 3 (26 Sep, 20:40): aligned with the Unstop rules (section 7) and adds the guardrails
layer (section 3a).
Revision 5 (29 Sep, 00:42): rows re-dated after Sun 27 / Mon 28. Mon 28 was spent on judge quality
(three judge experiments), the extended change-detection set and parser fixes, and a third bank
(held-out test2); tiering and remediation move to Tue 29.

Revision 4 (27 Sep, 15:00; rows re-dated 15:47): the plan is a guide, not a contract (user). Work is pulled forward
as soon as the previous task is done and the dates below are re-set continuously; the only hard
line is submission before 10 Oct. Sunday's work finished early, so the end-to-end run moves from
Wed 30 to Sun 27 / Mon 28. The chain links applicability, evidence and testing are promoted from
stretch to core in a minimal form (see 5a).

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

## 3. Stack (open-source first, user directive 26 Sep)

Principle: every component is open source (OSI licence) unless no practical open option
exists; the few exceptions are free hosting services, listed explicitly. Total cash cost
target: **INR 0**.

| Piece | Choice | Licence | Reason |
|---|---|---|---|
| DB | PostgreSQL 18 + pgvector (Neon for dev and demo; same version in CI and compose) | PostgreSQL / PostgreSQL | CLAUDE.md |
| Containers | Podman Desktop (fully open source), running our `docker-compose.yml`; Docker Desktop is the fallback (free for personal use, proprietary app). Both need CPU virtualisation enabled in BIOS | Apache-2.0 | open-source first |
| Regulation parsing | HTML via BeautifulSoup for v2/v3; Docling for PDF v1 | MIT / MIT | HTML is clean; Docling fixes PDF word-split noise (P-012) |
| Policy parsing | Docling (layout + tables, no OCR) | MIT | reference session 2 |
| **LLM (local)** | Ollama on the RTX 4060 (8 GB). Candidates for the Mon 28 bake-off: `qwen3:8b` (5.2 GB, fits in VRAM) and `qwen3:14b` (9.3 GB, partial CPU offload). Used for extraction passes, the cheap judge and the injection classifier | MIT (Ollama); Apache-2.0 (Qwen3) | free, private, on-prem story |
| **LLM (strong)** | A larger open-weights model (70B-120B class) via a free hosted tier, used only for escalations | open-weights model; host is a free service | laptop cannot run 70B well; model stays open |
| LLM routing | LiteLLM in-process; stage -> model mapping in config; a paid API model is possible only as an explicit, logged opt-in | MIT | swap without code changes |
| Embeddings | bge-m3 served by Ollama (1024-dim, 8K context; no PyTorch in the core install) | MIT | CLAUDE.md; one local model server for LLM and embeddings |
| Reranker | FlashRank (local, CPU); fall back to embedding order on failure | Apache-2.0 | reference session 1 |
| Agent | LangGraph + Postgres checkpointer | MIT | reference repo has checkpointer code |
| Tracing + eval tracking | **MLflow** (local server): OpenTelemetry-compatible LLM traces plus experiment runs for every eval | Apache-2.0 | replaces Logfire, whose backend is SaaS; one tool for traces and metrics |
| Retries | tenacity | Apache-2.0 | reference repo pattern |
| Cache | exact-match table in Postgres | - | CLAUDE.md (never semantic cache) |
| UI | Streamlit; replay mode deployed on Streamlit Community Cloud (free hosting service) | Apache-2.0 | public demo link is mandatory |
| Quality | ruff (lint + format), pytest, pre-commit, GitHub Actions CI | MIT / MIT / MIT / free for public repos | industry standard |
| **Not used** | Qdrant Cloud, Portkey, NeMo guardrails, AWS ECS, Batch API, Jev, Logfire; RAGAS only as an optional extra metric | - | conflict with settled design, SaaS, or budget |

Business angle for the deck: open-weights models plus self-hosted components mean a bank can
run the whole system inside its own perimeter, with no customer or policy data leaving it.

### Engineering standards

- `uv` lockfile; `ruff` lint and format; `pytest` unit tests; GitHub Actions CI on every push.
- `.env.example` (no secrets in git); config in `pydantic-settings`; structured logging.
- Architecture Decision Records in `docs/adr/` (one short file per settled decision; they feed
  the architecture document).
- Open-source licence file in the repo (Apache-2.0 proposed; the user decides).

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
| Tonight / Sun AM | Enable CPU virtualisation (Intel VT-x) in BIOS, then install Podman Desktop (or Docker Desktop) and Ollama | 1 h |
| Sun | Create a free account on one hosted open-weights provider (no card) for the strong model | 10 min |
| ~~Sat 26~~ | ~~Choose 2 policies~~: Nainital Bank + Central Bank of India (done 26 Sep 22:45) | - |
| By Mon | Personal check: outside-activity approval, IP ownership, public-statement rules | 30 min |
| By Mon | Post the AI-tools question in the Unstop Discussions tab (draft in PROJECT_LOG 20:44); open the logged-in Phase 2 "Submit" form and note every field; read the ET microsite (Claude cannot open it) | 30 min |
| Sun 27 | Review planted mutations for realism | 1 h |
| Mon 28 – Tue 29 | **Blind-label ~30 obligation-to-control mappings** (15 per day) | 2 x 1 h |
| After first E2E (Wed 30 - Thu 1) and each eval run | **Blind adjudication** of system-reported gaps not in the answer key (pairs shown without the system's verdict, mixed with covered pairs); precision is reported after adjudication | 30-45 min each |
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

## 5a. Chain coverage (rev 4)

Problem 1's chain, and where each link is shown:

| Link | Minimal version that must exist | Built on |
|---|---|---|
| Regulations | 3 versions, clause tree, diff | done |
| Obligations | extracted with modality must / must_not / may, verbatim quote | Sun 27 - Mon 28 |
| Applicability | bank profile + filter with a reason per obligation (e.g. "applies only if V-CIP introduced") | Wed 30 |
| Policies / controls | extracted controls with owner / frequency / evidence fields | Sun 27 - Mon 28 |
| Evidence | 2 synthetic CSVs (re-KYC completion dates, CKYCR upload lag) | Wed 30 |
| Testing | design test (control attributes) + operating test (exception rate vs tolerance), "cannot assess" without evidence | Wed 30 |
| Gaps | deterministic gap rules, scored against the frozen key | Mon 28 - Tue 29 |
| Remediation | drafts for top gaps with owner line, due date, success criterion | Thu 1 |
| Ongoing monitoring | change agent triggered by a new circular **or** a new evidence batch | Fri 2 - Sat 3 |

## 6. Schedule (rev 4: rolling; re-dated as work moves)

| When | Work | Exit criterion | Status |
|---|---|---|---|
| Sat 26 | Schemas, DDL, taxonomy, plan; RBI corpus (3 versions); theme verification | - | done |
| Sun 27 AM | Parsers (RBI HTML + Docling PDFs, policies); both real amendments diff to 1 change; Neon + schema; Ollama models; CI | - | done |
| Sun 27 PM | Answer keys reviewed, coverage-checked, **approved and frozen** (`350b8e0`) | - | done |
| **Sun 27 PM** | **Crude end-to-end on Nainital (dev)**: extraction, pgvector retrieval, judge, gaps; **eval harness v1**; evidence + control tests; applicability module | First scores (counts) | done: runs e2e1-e2e5, error analysis, dedupe, obligation level; third bank drafted |
| **Mon 28** | Wire applicability + evidence into the pipeline; score the evidence key; FlashRank rerank; change-detection report vs RBI amendment markers; first fixes from the scores. You: label 15 | Chain links scored end to end | done: evidence 2/2, rerank, change detection on 9 more Directions (262/266), parser fixes; judge rubric e2e6 reverted; thinking-judge e2e7 run (to score) |
| Tue 29 | Score e2e7 (thinking judge) vs e2e5; freeze the Dhanlaxmi key (after user review); score the 50-label gold set. Then **tiering** (fast judge for all; thinking / strong judge only on uncertain units -> high-confidence gaps vs review queue), loop caps + fallback, risk rubric, **remediation drafts**. You: Dhanlaxmi review + blind review | Triage report: high-confidence precision, review-queue rate, recall | |
| Wed 30 | Label-based accuracy + calibration; tuning on the dev set only | Metrics vs user labels | |
| Thu 1 | **Change agent groundwork** (LangGraph skeleton, Postgres checkpointer, diff tool wrapped) | Agent runs a dry pass | |
| **Fri 2 (holiday)** | **Change agent part 1:** LangGraph, diff -> classify (incl. permissive "may" -> advisory) -> scope, Postgres checkpointer | Both real amendments classified; FPI -> "policy update recommended" | |
| **Sat 3** | **Change agent part 2:** re-extract, re-map affected edges only, recovery, open gaps + remediation; evidence-batch trigger (ongoing monitoring) | Sep 2026 amendment end to end, one recovered failure | |
| **Sun 4** | What-if dry-run; reviewer override loop; injection flagging report; eval re-run | All claimed features exist. **CHECKPOINT** | |
| Mon 5 - Tue 6 | Streamlit (profile, gaps, why-panel, review queue, timeline, metrics, guardrails); replay mode; **Streamlit Cloud deploy** | Public demo URL works without keys | |
| **Wed 7** | **FEATURE FREEZE.** Final eval: dev + first-ever test-set run (Central Bank), counts per split; evidence matrix; decide claim | Numbers and claim frozen | |
| Thu 8 | Architecture doc + pitch deck (8-12 slides); **submit v0** | v0 submitted | |
| Fri 9 | Rehearse; record 2-4 min video (mp4 < 50 MB + unlisted YouTube) | Video link works | |
| **Sat 10** | Fixes; final submit by 15:00 | Submitted | |
| Sun 11 | Buffer only | - | |

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

From the logged-in Phase 2 submit form (screenshot, 27 Sep) plus the Unstop rules and FAQs:
- Four required fields: pitch deck (PDF), demo video (mp4/mp3 upload), public GitHub URL (max
  500 chars), problem statement radio (**Banking/financial regulations**).
- Uploads max 50 MB (FAQ). One solution per team. Editable until the deadline; no late
  submissions. Top 10 go to the virtual finale on 2 Nov 2026.
- A **"Download Brief/Case"** button on the form: not read yet (user to download and share).

1. **Public GitHub repo.** The form asks for "complete source code, README.md, installation
   steps, dependencies, architecture overview, API documentation (if applicable), and
   environment setup instructions", enough for judges "to understand and run the project
   without additional assistance". So the README must also contain:
   - A one-command run and the public demo URL.
   - The answer-key commit hash.
   - The data provenance statement.
   - The **AI-assistance disclosure** and **attribution** for the reference repos. The rules
     make plagiarism a disqualifier, so we reuse ideas with credit and never copy code verbatim.
   - A zero-setup path: replay mode runs with no models, no API keys and no database.
2. **Pitch deck (PDF, 8-12 slides)**, one slide per form item:
   1. Team Introduction.
   2. Problem Statement.
   3. Proposed Solution.
   4. Architecture: process flow, agent graph, model per stage (the problem statement's
      "detailed structural architecture"; full version in `docs/ARCHITECTURE.md`).
   5. AI Models & Technologies Used (open-source stack + licences).
   6. Product Demo (screens + demo URL).
   7. Business Impact.
   8. Scalability (plus Responsible AI and guardrails).
   9. Future Roadmap.
   10. Grid claim F3/D2 with the evidence matrix and metrics. The form has no separate field
       for it, so it must be in the deck.
3. **Demo video, 2-4 minutes** (hard limit). Uploaded as **mp4 under 50 MB** (export 720p) and
   also on YouTube (unlisted) with a public link. The form's required sections map to our
   script, target 3:30:
   - Introduction and problem overview (25 s).
   - Live demo: bank profile -> gaps with citations and one "why" panel (40 s).
   - AI capabilities: amendment arrives -> agent plans, re-maps, recovers from one failure,
     opens remediation (70 s).
   - Key features: what-if and reviewer override (35 s).
   - Business impact: metrics and guardrail report (30 s).
   - Closing summary with the evidence matrix (10 s).
4. **Accessible demo link:** replay mode on Streamlit Community Cloud. It needs no API keys and
   no database.
5. **Grid claim F3/D2**, justified by the matrix. Never D3 (no multimodal input).

## 8. Open decisions

- Strong-model host for escalations (free open-weights tier); the local model is picked on Mon 28 by a small bake-off on the hand-labelled sample.
- Docker Desktop (recommended) vs Neon.
- Organisers' answer on commercial LLM APIs. Until then, keep every stage runnable on an
  open-weights model via LiteLLM (config change only).
- Whether the public repo should keep `CLAUDE.md`, which says you work at a bank. Recommend
  keeping it but removing that phrase.
