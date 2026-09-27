# CLAUDE.md — ET x Accenture AI Hackathon (Agentic Edition), Problem 1

Handoff from a planning conversation on claude.ai. Read fully before any work.
All decisions below are settled unless the user reopens them.

## Context
- Hackathon: ET AI Hackathon: Agentic Edition (Economic Times x Accenture), hosted on Unstop.
- Phase 2 build sprint: 23 Sep 2026 11:00 IST -> 11 Oct 2026 23:59 IST. Target submission: Sat 10 Oct 15:00 IST (11 Oct is buffer only).
- Team: user (solo, part-time alongside a full-time job) + Claude. Budget ~90 hours (≈3 h weekdays, ≈9 h weekend days).
- Goal: top 3. Optimize for the 8 evaluation criteria and a defensible grid claim.
- Required deliverables (problem statement): (1) working demo covering every claimed area, (2) detailed structural architecture (process flow, actions, decisions, model usage, features). Self-declared 3x3 grid position with justification; over- AND under-claiming are penalized.
- Unstop submission (checked 26 Sep): public GitHub repo URL, pitch deck (PDF/PPT), 2-4 minute demo video (hard limit), accessible demo link; uploads .pdf max 50 MB; one solution; editable until deadline. Plagiarism disqualifies: credit reference repos, never copy code verbatim. ET microsite rules (read 26 Sep from the user's PDF): "Open-source AI tools, libraries, datasets, and models are permitted." "All AI solutions, code, and assets must be original and developed during the hackathon." "Misconduct, cheating, or misuse of AI will result in disqualification." There is no explicit ban on commercial LLMs or AI coding assistants, but only open-source is explicitly permitted, so prefer open-weights models inside the product and disclose AI-assisted development in the README. Keep every stage runnable on an open-weights model via LiteLLM. Top 10 go to a virtual finale.

## Problem chosen: Problem 1 — Banking regulatory compliance agent
Chain to implement and keep traceable over time:
Regulations -> obligations -> applicability -> internal policies/controls -> evidence -> testing -> gaps -> remediation -> ongoing monitoring.

Target grid position: F3 / D2. Final claim decided on 8 Oct from the evidence matrix. Do NOT claim D3.
- D2 = mostly structured/textual input, high demonstrable reliability.
- F3 = at least 8 of the 14 listed features.

Feature candidates (claim ≥8 only if proven): 1 ingestion, 2 change intelligence, 3 obligation extraction,
4 control-framework understanding, 5 regulation-to-control mapping, 6 control effectiveness (design vs operating),
7 evidence-based assessment, 8 gap identification, 9 risk-based prioritization, 10 remediation recommendations,
11 autonomous impact analysis, 12 what-if simulation.
Declared not covered unless time remains after freeze: 13 cross-regulation, 14 regulatory contradiction detection.

## Hard rules
- ZERO internal material from any employer. No policies, control libraries, templates, or data, not even anonymized. Public sources or synthetic only.
- Hackathon rules and submission format are recorded above; open questions are tracked in docs/PLAN.md section 8.
- Commit daily so git history shows real progress.
- Only public data goes to any LLM provider.

## Data and ground truth
- **Base corpus (confirmed by user 27 Sep): RBI (Commercial Banks – Know Your Customer) Directions, 2025 (RBI/DOR/2025-26/169, 28 Nov 2025), plus the 18 Sep 2026 amendment (current version v3).** Demo "new circular arrives" event = the 18 Sep 2026 FPI amendment (permissive, so expected output is "policy update recommended", not a breach). It replaced the 2016 KYC Master Direction, which is repealed; do not build on the 2016 MD. Three versions are on disk (original, after 29 Dec 2025 amendment, after 18 Sep 2026 amendment); provenance and sha256 in data/sources.yaml. STR/CTR numeric rules live in the PML Rules, not in the Directions.
- Controls: publicly published KYC/AML policies of two commercial banks, Nainital Bank and Central Bank of India (data/sources.yaml).
- Gap planting: a script mutates the public policies and writes an answer key. The answer key is committed to git BEFORE any system run (timestamped proof against "self-grading").
- Mutation operators: delete control; weaken threshold/frequency; narrow scope; introduce contradiction; make stale (pre-amendment rule); strip owner/evidence (design deficiency).
- Mutation themes (from public RBI penalty patterns; user to validate): periodic re-KYC, risk categorization, beneficial-owner identification, CKYCR upload timelines, STR/CTR reporting to FIU-IND, transaction-monitoring alert review.
- Answer key scoring rules (acceptable sets, split findings, decoys, real findings, blind adjudication of unkeyed reports before precision is reported): docs/mutation_taxonomy.md "Scoring". Obligation modality is must / must_not / may.
- Hand-labeled real sample: ~30 obligation->control mappings labeled blind by the user.
- Evidence: synthetic CSV logs (e.g., re-KYC completion), some deliberately failing operating tests.

## Architecture
Storage: Postgres + pgvector (local Docker). Graph as node/edge tables. Every node and edge is versioned (effective_from, effective_to, source_version) — bitemporal traceability.

Core schemas (fields, to be finalized on 24 Sep):
- Obligation: id, source_clause_ref, source_span, actor, modality (must / must_not), action, object, condition, threshold_or_deadline, applicability, effective_from, effective_to, source_version.
- Control: id, objective, type (preventive/detective/corrective), nature (manual/automated), frequency, owner, expected_evidence, source_span.
- Mapping: obligation_id, control_id, verdict (covered/partial/missing), rationale, citations (both sides), judge outputs, confidence, status (auto/escalated/reviewed).
- Gap: id, type, inherent_risk, residual_risk, status, linked obligation/control.
- Remediation: gap_id, action, owner line (1st/2nd/3rd line of defense), due date.
- Bank profile: bank type, products, geography (drives applicability filter).

Ingestion pipeline (deterministic workflow — deliberately NOT an agent):
1. Structural parse by RBI paragraph numbering (no LLM; never fixed-size chunking). HTML sources via BeautifulSoup; PDFs (regulation v1, bank policies) via Docling (layout + tables, no OCR). Normalize text before any diff.
2. Obligation extraction: cheap model, strict JSON, two passes; disagreement is flagged.
3. Control extraction: same pattern.
4. Candidate retrieval: bge-m3 embeddings (top 20) -> FlashRank local reranker -> top 5 controls per obligation. If the reranker fails, fall back to embedding order (tenacity retry first).
5. Mapping judge: cheap LLM judge (+ optional Jev as independent second judge). Agree + high confidence -> accept; else -> strong model -> human review queue.
6. Citation verifier: every cited span must exist verbatim in source, else reject. Deterministic.
7. Gap scoring: deterministic rules over control attributes + risk rubric; LLM writes rationale only.
8. Remediation drafting: strong model, top-N gaps only.

Change agent (the agentic centerpiece, LangGraph):
- Trigger: feed event (simulated RBI feed replaying real amendments).
- Plan: classify change (cosmetic / modified / new / repealed obligation), decide scope of re-analysis.
- Tools: diff, re-extract, graph query, mapping judge, evidence lookup, remediation writer.
- Recovery: repair-and-retry on invalid output; escalate on judge disagreement; explicit "cannot assess" when evidence missing.
- Actions: update versioned graph, open remediation items.
- What-if mode (feature 12): same agent on a draft circular, dry-run, outputs projected gap delta without committing.

Cross-cutting:
- Models: open-weights only by default (user directive 26 Sep). Local Ollama on the RTX 4060 for extraction and cheap judging; a larger open-weights model on a free hosted tier for escalations. A paid API model is only an explicit, logged opt-in.
- Routing: LiteLLM in-process. Eval mode = pinned model per stage, fallback OFF. Demo mode = fallback ON, served model logged per trace.
- Cache: exact-match on (prompt hash, model, input hash). NEVER semantic cache (near-identical clauses differ in thresholds).
- Batch API for offline extraction. Hard spend cap in provider console.
- Tracing and eval tracking: MLflow (Apache-2.0, local), replacing Logfire on 26 Sep per the user's open-source-first directive. Lazy-load heavy models (embedder, reranker).
- Checkpointing: LangGraph Postgres checkpointer (resume after crash).
- Security: uploaded docs treated as untrusted data; delimited in prompts; instruction-like content flagged.
- Trainability: reviewer overrides stored and fed back as few-shot corrections + threshold recalibration.
- Replay mode: deterministic demo from cache.
- UI: Streamlit — graph view, gap dashboard, per-verdict "why" panel, review queue, metrics page, change timeline.

Rejected tools (do not reintroduce without the user's say-so): OmniRoute (fallback mixes models into eval numbers; compression can drop "shall not"/thresholds; ToS risk), semantic caching, NeMo guardrails, AWS ECS deployment, multimodal parsing (ColPali/OCR), Neo4j, Qdrant Cloud (vectors stay in pgvector next to the versioned graph), Portkey (external proxy; LiteLLM is in-process).
Reference material: two Krish Naik 8-hour RAG marathons (repos d-hackmt/8hr-MARATHON, sourangshupal/8hr-MARATHON). Adopted from them: Docling, FlashRank, Logfire gotchas, tenacity retry + fallback, Postgres checkpointer setup, guardrail test cases in the golden set, optional Streamlit Cloud deploy of replay mode.
Jev (TypeSafe AI, typed calibrated decisions): optional second judge only, added after eval harness exists, only if metrics improve. Pipeline must run without it. Verify its calibration with a reliability plot before thresholding on it.

## Metrics (the D2 proof)
- Obligation extraction precision/recall (hand-labeled sample).
- Gap detection precision/recall per mutation type (answer key).
- Citation validity rate (and rejection count).
- Auto-accept rate vs accuracy of auto-accepted items.
- Calibration plot of judge confidence vs actual accuracy.
- Cost and latency per circular. Before/after effect of one reviewer correction.
- Business impact: circular-to-impact-assessment time, agent vs manual baseline (user's estimate, labeled as such).

## Schedule
Superseded on 26 Sep (3-day slip). The live schedule, checkpoints, cut order, stack simplifications and feature tiers are in docs/PLAN.md.

## Evidence matrix (build as you go)
Columns: feature | demo timestamp | architecture section | metric. One row per claimed feature.

## Demo script (2-4 min hard limit; target 3:30; mp4 < 50 MB + unlisted YouTube link)
Bank profile -> gaps with citations + one "why" panel (45 s) -> amendment arrives, agent plans, re-maps only affected edges, recovers from one injected failure, opens remediation (75 s) -> what-if on a draft circular (20 s) -> reviewer override changes a re-run (20 s) -> metrics + guardrail report (30 s) -> evidence matrix (10 s).

## Guardrails
See docs/PLAN.md section 3a. Input (injection scanner, egress allowlist), output (schema, citation gate, number/negation fidelity, review queue), action (read-only what-if, blast-radius pause, humans close gaps, budget), data (LLM never sees raw evidence rows). No chat-topic rails; NeMo stays rejected.

## After submission
Prepare a 5-minute pitch and a live-demo path for the finale: virtual grand finale on 2 Nov 2026 (top 10 teams).

## Project metadata (outside the repo, not submitted)
Folder: C:\Users\singh\OneDrive\Documents\AI Engineer\regcompliance-meta\
- PROJECT_LOG.md: append a timestamped (IST) entry for every meaningful action: what was done, files/commits, decisions.
- PROBLEMS_LOG.md: every problem hit, each attempted fix with timestamp, whether it worked and why, final solution. Update status as it changes.
- project_chart.html: architecture, Gantt, feature status, blockers. Update stats, Gantt done/active tags, feature status and blockers at the end of each work session.
- Flow maps: whenever a new process/data flow is built or designed, add it to project_chart.html as a Mermaid diagram (verify it renders) and keep existing flow maps current (user rule, 27 Sep).
- PROJECT_LOG.md has a "Current status" block at the top: update it at the end of every work step.
Get the time with `date "+%Y-%m-%d %H:%M"`; never guess timestamps.

## Open-source-first directive (user, 26 Sep)
Keep the project to industry standards and use open-source tools wherever practical. Stack and licences: docs/PLAN.md section 3. Any non-open component must be named as an exception with a reason.

## Evaluation integrity (user rules, 27 Sep)
- Nainital = dev set (prompts, thresholds and routing may be tuned on it). Central Bank = held-out test set: run only for final numbers (freeze, Wed 7 Oct), never inspected while tuning. Report metrics separately per split.
- Extraction and mapping prompts must NOT reference specific clauses, thresholds or themes from either answer key (e.g. no "re-KYC", "10 days", "25%", "trust beneficial owner" hints). Schema-generic instructions only; few-shot examples, if any, must come from non-KYC text or from reviewer overrides on the dev set.
- Every delete / narrow / weaken mutation must pass scripts/coverage_check.py (lexical + bge-m3 semantic search of the altered policy) with each remaining hit judged; a planted gap is only valid if no other passage still satisfies the obligation.
- Report evaluation results as counts per row type ("6/7 gaps, 0/3 decoys, 1/1 injection"), never bare percentages.
- Answer keys, mutated policies and mutation specs are FROZEN since the approval commit: no edits without an explicit logged reason (commit message + PROBLEMS_LOG), and metrics must cite the key commit.
- The architecture document must disclose that the answer keys were authored in the same toolchain (Claude Code), with the mitigations: hand-written find/replace edits, user review, coverage check, commit timestamp before any LLM run, held-out test split.

## Git hygiene
- Stage explicit paths (`git add <files>`); never `git add -A` / `git add .`. Twice on 26-27 Sep a blanket add published files that must stay local (the organiser brief; a pre-review answer key).
- Never print, log or echo values from `.env` or any secret; validate structure only (redact unknown lines too). A Neon password leaked into session output on 27 Sep this way.
- Check `git status --short` before every commit. The answer key is committed only in the user-approved approval commit.

## Working agreement with the user
- The plan (docs/PLAN.md) is a guide, not a contract: when a task is done, pull the next one forward without waiting; re-date the schedule and the metadata chart as work moves. Only hard line: submit before 10 Oct 2026.
- Direct, precise, no fluff or praise, no emojis. Explain intuition and first principles.
- Challenge weak assumptions. Name analysis paralysis when scope refinement replaces building.
- Do not remove or alter provided code unnecessarily. Refer to exact code segments, not line numbers.
- Say explicitly when something is uncertain or speculative.

## Next action
Answer keys approved and frozen (see the "ANSWER KEYS APPROVED" commit). Next session goal (behind schedule): a crude end-to-end run on the Nainital DEV set only: regulation parse -> obligation extraction (qwen3:8b via Ollama) -> control extraction -> mapping (bge-m3 retrieval, judge) -> gap list, with results loaded into Neon. Quality does not matter yet; a complete run does. Never run on the Central Bank test set before freeze.
