# Project plan: submit Sat 10 Oct 2026

Hard deadline is 11 Oct 23:59 IST. Target is **Sat 10 Oct, 15:00**, which leaves Sunday as
the emergency buffer.

## 1. Reality check

- **Time left:** from Sat 26 Sep evening, about 36 h over the weekends (26-27 Sep, 3-4 Oct),
  30 h on weekdays (10 x 3 h) and 6 h on Sat 10 Oct, so **about 70 h**. The original plan had 90.
- **Slip:** about 3 days behind. Nothing runs yet and there is no corpus on disk.
- **Consequence:** the plan below cuts tooling, not features. The F3 claim still needs 8
  proven features, but several of them share one piece of machinery, which makes that feasible.

## 2. What we are building, in plain terms

Two documents go in: the regulation (RBI KYC Master Direction) and a bank's KYC policy.
The questions to answer: *which rules does the bank's policy fail to cover, how badly, and
what changes when RBI amends a rule?*

```
 RBI Master Direction ──parse──> clauses ──LLM extract──> obligations ─┐
                                                                       ├─ retrieve top-5 ─> LLM judge ─> mapping
 Bank KYC policy ──────parse──> sections ─LLM extract──> controls ─────┘                    (covered/partial/missing)
                                                                                                │
 synthetic evidence CSVs ────────────────> operating test ───────────┐                          │
                                                                     v                          v
                                                  gaps (deterministic rules) ──> risk score ──> remediation (LLM)

 RBI amendment arrives ──> CHANGE AGENT: diff -> classify -> re-extract changed clauses
                           -> re-map only affected edges -> new/closed gaps -> remediation
                           (same agent with dry_run=True on a draft circular = what-if)
```

Why this design scores well: the LLM handles reading and judging, while deterministic code
handles parsing, citation checks and risk scores. Every LLM claim is checked against the
source text. That split is the "high demonstrable reliability" argument for D2.

## 3. Stack (simplified from CLAUDE.md)

| Piece | Choice | Change vs CLAUDE.md |
|---|---|---|
| DB | Postgres 16 + pgvector in Docker (fallback: Neon free tier) | none |
| LLM routing | LiteLLM; cheap = Claude Haiku 4.5, strong = Claude Sonnet 5 | provider to confirm |
| Embeddings | bge-m3 local via sentence-transformers | reranker becomes optional |
| Agent | LangGraph + Postgres checkpointer | none |
| Tracing | Logfire free tier | chosen over self-hosted Langfuse (no extra container) |
| Cache | exact-match table in Postgres | none |
| UI | Streamlit | none |
| **Dropped** | Batch API (small corpus, and up to 24 h latency kills iteration speed); Jev | Jev was already optional |

## 4. Who does what

Claude writes the code, tests and docs, explains each component as it is built, and runs the
pipeline. **Only you can do these:**

- Install WSL2 + Docker Desktop and create the LLM API key with a spend cap.
- Check hackathon rules (AI-assisted code disclosure, "built during window", video length,
  deck/repo/URL format) and your employer's code of conduct (outside activities, IP clause).
- Validate the mutation themes and the RBI numbers against the Master Direction.
- **Hand-label about 30 obligation-to-control mappings blind**, before seeing system output.
  This is the ground truth for the D2 claim, so it cannot be delegated to the model under test.
- Give a manual-baseline estimate: how long a compliance analyst takes to assess one circular.
- Record the demo video and submit.

## 5. Feature claim strategy

| Tier | Features | Built on |
|---|---|---|
| **Floor (the 8 that make F3)** | 1 ingestion, 3 obligation extraction, 4 control understanding, 5 mapping, 8 gap identification, 9 risk prioritization, 2 change intelligence, 11 autonomous impact analysis | core pipeline + change agent |
| Stretch (cheap, shared machinery) | 10 remediation, 7 evidence-based assessment, 6 design vs operating effectiveness, 12 what-if | one LLM call; CSV + rules; dry-run flag on the change agent |
| Declared not covered | 13 cross-regulation, 14 contradiction detection | none |

Internal contradictions *within* a bank policy are a planted mutation. That is not feature 14,
which means contradictions *between regulations*. Do not blur the two in the claim.

Final claim is decided on **Wed 7 Oct** from the evidence matrix. Claim only what the demo
video shows **and** a metric supports.

## 6. Schedule

| Day | Hours | Work | Exit criterion |
|---|---|---|---|
| **Sat 26 Sep** | 3 | You: WSL2 + Docker, API key + spend cap, rules check. Claude: download corpus, `docker-compose.yml`, DDL applied | Postgres up, corpus on disk |
| **Sun 27 Sep** | 9 | Deterministic parsers (RBI paragraphs, policy sections) and load. Pick 2 public bank policies. Hand-write `spec.yaml` (~25 mutations + 8 decoys), `mutate.py`, **commit answer key** | Answer key in git before any LLM run |
| Mon 28 Sep | 3 | Obligation extraction (single pass, strict JSON) on the 6 themes. You: label 15 mappings | Obligations in DB with verified spans |
| Tue 29 Sep | 3 | Control extraction, embeddings, top-5 retrieval. You: label 15 more | Candidates per obligation |
| **Wed 30 Sep** | 3 | Mapping judge, citation gate, gap rules, **first end-to-end run** | Gap list for one policy. **CHECKPOINT** |
| Thu 1 Oct | 3 | Eval harness v1: gap P/R per operator, decoy FP rate, citation validity, extraction P/R vs your labels | First metrics table |
| Fri 2 Oct | 3 | Tiering (agree + high confidence -> auto, else strong model -> review queue), second extraction pass, risk rubric, exact cache | Numbers improving; auto-accept accuracy measured |
| **Sat 3 Oct** | 9 | Change agent (LangGraph): simulated feed replays the real beneficial-owner amendment -> diff -> classify -> re-extract -> re-map affected -> gaps. Repair-retry, escalation, "cannot assess", checkpointer | Agent handles one real amendment |
| **Sun 4 Oct** | 9 | Evidence CSVs + design/operating tests, remediation drafting, what-if dry-run, reviewer override feeding back as few-shots | All claimed features exist. **CHECKPOINT** |
| Mon 5 Oct | 3 | Streamlit: bank profile, gap dashboard, "why" panel, review queue | Core demo path clickable |
| Tue 6 Oct | 3 | Streamlit: change timeline, metrics page, graph view. Replay mode from cache | Full demo path clickable offline |
| **Wed 7 Oct** | 3 | **FEATURE FREEZE.** Final eval run, calibration plot, cost/latency. Evidence matrix, decide claim | Numbers and claim frozen |
| Thu 8 Oct | 3 | Architecture document: flow, decisions, model usage per stage, reliability mechanisms, grid justification | Doc written |
| Fri 9 Oct | 3 | Rehearse demo script, record video, README / run instructions | Video recorded |
| **Sat 10 Oct** | 6 | Fix what the rehearsal exposed, final check against submission format, **submit by 15:00** | Submitted |
| Sun 11 Oct | - | Emergency buffer only | - |

### Checkpoints and cuts

- **Wed 30 Sep, no end-to-end run:** single-pass extraction only, one judge, skip the second
  extraction pass on Fri, and start the change agent Fri instead of Sat.
- **Sun 4 Oct, agent unstable:** reduce it to diff -> graph query -> re-map with recovery, and
  cut what-if (feature 12).
- **Cut order when slipping:** UI polish -> graph view -> reviewer feedback loop -> what-if ->
  remediation depth -> evidence/effectiveness (features 6/7).
- **Never cut:** answer key before first run, citation gate, eval harness, change agent,
  evidence matrix.

## 7. Submission package

1. **Demo video (~5 min)**, following the script in CLAUDE.md.
2. **Architecture document:** process flow, the agent graph (nodes, tools, decisions,
   recovery), model per stage and why, reliability mechanisms, data provenance, grid claim with
   the evidence matrix.
3. **Repo:** README with one-command run (`docker compose up` + `uv run ...`), answer-key
   commit hash, and a statement that all data is public or synthetic.
4. **Evidence matrix:** feature | demo timestamp | architecture section | metric.
5. **Grid claim F3/D2**, justified by the matrix. Never claim D3 (no multimodal input).

## 8. Open decisions

- LLM provider/key. Plan assumes Anthropic; LiteLLM makes it swappable. Expected spend is
  well under USD 20 for this corpus (estimate, not measured).
- Docker Desktop (recommended) vs Neon.
- Which 2 public bank KYC policies to use. Claude will shortlist 3-4 candidates.
