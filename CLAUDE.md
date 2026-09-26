# CLAUDE.md — ET x Accenture AI Hackathon (Agentic Edition), Problem 1

Handoff from a planning conversation on claude.ai. Read fully before any work.
All decisions below are settled unless the user reopens them.

## Context
- Hackathon: ET AI Hackathon: Agentic Edition (Economic Times x Accenture), hosted on Unstop.
- Phase 2 build sprint: 23 Sep 2026 11:00 IST -> 11 Oct 2026 23:59 IST. Submit by afternoon of 11 Oct, not at the deadline.
- Team: user (solo, part-time alongside a full-time job) + Claude. Budget ~90 hours (≈3 h weekdays, ≈9 h weekend days).
- Goal: top 3. Optimize for the 8 evaluation criteria and a defensible grid claim.
- Required deliverables: (1) working demo covering every claimed area, (2) detailed structural architecture (process flow, actions, decisions, model usage, features). Self-declared 3x3 grid position with justification; over- AND under-claiming are penalized.

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
- ZERO internal material from the user's employer (a bank). No policies, control libraries, templates, or data — not even anonymized. Public sources or synthetic only.
- User must check: employer code of conduct (outside activities, IP clause); hackathon rules on AI-assisted code disclosure and "built during window"; Unstop submission format (video length, deck, repo, live URL).
- Commit daily so git history shows real progress.
- Only public data goes to any LLM provider.

## Data and ground truth
- Regulation: RBI KYC Master Direction + its amendment notifications (rbi.org.in). Need two versions for change intelligence. If the older version is unavailable, reconstruct it from amendment notifications.
- Controls: publicly published KYC/AML policies of banks (not the user's employer).
- Gap planting: a script mutates the public policies and writes an answer key. The answer key is committed to git BEFORE any system run (timestamped proof against "self-grading").
- Mutation operators: delete control; weaken threshold/frequency; narrow scope; introduce contradiction; make stale (pre-amendment rule); strip owner/evidence (design deficiency).
- Mutation themes (from public RBI penalty patterns; user to validate): periodic re-KYC, risk categorization, beneficial-owner identification, CKYCR upload timelines, STR/CTR reporting to FIU-IND, transaction-monitoring alert review.
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
1. Structural parse by RBI paragraph numbering (no LLM; never fixed-size chunking).
2. Obligation extraction: cheap model, strict JSON, two passes; disagreement is flagged.
3. Control extraction: same pattern.
4. Candidate retrieval: local embeddings -> local reranker -> top 5 controls per obligation.
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
- Routing: LiteLLM in-process. Eval mode = pinned model per stage, fallback OFF. Demo mode = fallback ON, served model logged per trace.
- Cache: exact-match on (prompt hash, model, input hash). NEVER semantic cache (near-identical clauses differ in thresholds).
- Batch API for offline extraction. Hard spend cap in provider console.
- Tracing: Langfuse (self-hosted) or Logfire free tier.
- Checkpointing: LangGraph Postgres checkpointer (resume after crash).
- Security: uploaded docs treated as untrusted data; delimited in prompts; instruction-like content flagged.
- Trainability: reviewer overrides stored and fed back as few-shot corrections + threshold recalibration.
- Replay mode: deterministic demo from cache.
- UI: Streamlit — graph view, gap dashboard, per-verdict "why" panel, review queue, metrics page, change timeline.

Rejected tools (do not reintroduce without the user's say-so): OmniRoute (fallback mixes models into eval numbers; compression can drop "shall not"/thresholds; ToS risk), semantic caching, NeMo guardrails, AWS ECS deployment, multimodal parsing (ColPali/OCR), Neo4j.
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
| Date | Work | Exit |
|---|---|---|
| Wed 23 Sep | Rules/format check, code-of-conduct read, repo, corpus download, verify older version | Constraints known, corpus on disk |
| Thu 24 Sep | Schemas + mutation taxonomy | Schemas committed |
| Fri 25 Sep | Mutation script + answer key committed; start hand-labeling (15/day) | Answer key in git |
| Sat–Sun 26–27 Sep | Parse -> extract -> map -> gaps, crude end to end | Gap list for one policy |
| Mon 28 Sep | Eval harness v1, citation gate, baseline | First metrics table |
| Tue–Wed 29–30 Sep | Iterate on numbers, tiering, review thresholds, optional Jev | Metrics improving |
| Thu–Fri 1–2 Oct | Change agent loop + versioned graph | Agent handles one real amendment |
| Sat–Sun 3–4 Oct | Feed, what-if, prioritization, remediation, effectiveness, feedback loop | All 12 candidates exist |
| Mon–Tue 5–6 Oct | UI | Demo path clickable |
| Wed 7 Oct | Hardening, replay mode, final eval | Final numbers |
| Thu 8 Oct | FEATURE FREEZE. Evidence matrix, decide claim | Claim decided |
| Fri 9 Oct | Architecture document | Written |
| Sat 10 Oct | Demo video, finalize matrix | Video done |
| Sun 11 Oct | Buffer, submit by afternoon | Submitted |

Checkpoints: 28 Sep with no end-to-end run -> single-pass extraction, no dual judge, push change agent later.
4 Oct with unstable agent -> reduce to diff -> graph query -> re-map with recovery; cut what-if.

Cut order when slipping: UI polish -> Jev -> remediation depth -> what-if -> feedback loop.
Never cut: eval harness, citation gate, change agent, evidence matrix.

## Evidence matrix (build as you go)
Columns: feature | demo timestamp | architecture section | metric. One row per claimed feature.

## Demo script (~5 min)
Bank profile -> applicable obligations with citations -> graph + prioritized gaps + one "why" panel -> new amendment arrives, agent plans, re-maps only affected edges, recovers from one injected failure, opens remediation -> what-if on a draft circular -> reviewer override changes a re-run -> metrics page -> evidence matrix.

## After submission
Prepare a 5-minute pitch and a live-demo path for the finale (check finale date on Unstop).

## Working agreement with the user
- Direct, precise, no fluff or praise, no emojis. Explain intuition and first principles.
- Challenge weak assumptions. Name analysis paralysis when scope refinement replaces building.
- Do not remove or alter provided code unnecessarily. Refer to exact code segments, not line numbers.
- Say explicitly when something is uncertain or speculative.

## Next action
Draft the core schemas (above) as Pydantic models + Postgres DDL, and the mutation taxonomy/script design. The user validates the mutation themes against real-world KYC findings (generic, no employer specifics).
