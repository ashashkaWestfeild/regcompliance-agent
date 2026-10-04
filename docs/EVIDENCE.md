# Evidence matrix

One row per claimed feature of Problem 1: where the demo shows it, where the architecture
document explains it, and what was measured. Counts only. "Unseen" means the three held-out banks,
each run once from the tag `eval-freeze-2026-10-03`; "dev" means the development bank the system
was built on. Demo times refer to the video script and are confirmed after recording.

**Claim: F3 / D1**, against the brief's definitions (full statement: README, "Grid position").

- **F3.** 11 of 14: 9 on real policies, plus 6 and 7 on development data with synthetic logs (1, 2, 3, 5, 8, 9, 10, 11, 12; then 6 and 7), all in the live
  demo; 4 is partial; 13 and 14 are not claimed.
- **D1** (acceptable outputs in a majority of situations), three unseen banks, frozen v1, per
  output type: high-confidence findings real in blind samples after the full-policy check 8 of 9, 9 of 9, 4 of 10 (21 of 28 overall); hidden
  instructions 3 of 3; decoys left alone 7 of 9 (first scoring 6 of 9: three code-only steps first
  ran with the development bank's defaults, P-057); real findings 4 of 4; a majority of planted
  gaps at the right obligation, 11 of 20 (9 of 20 exact). Blind spot: deleted duties 0 of 4.
- **Not D2.** A pre-registered attempt (`eval/d2_bar.md`) was stopped by its own gate on 3 Oct,
  on development data and before any third-bank run: 1 of 4 target misses found, new-finding
  ceiling broken on all three development banks (local qwen3:8b; closing note on the unmerged
  `d2` branch).
- **Scope of the demo.** One regulation (RBI KYC Directions) end to end; published bank policies
  (no control libraries, SOPs or test records); no upload in the hosted app (new inputs run
  offline on the local GPU). The demo never writes: one commit of the change agent and two reviewer decisions, recorded on a copy of the database (d2, development data), are shown read-only.

| # | Feature | Demo | Architecture | Measured |
|---|---|---|---|---|
| 1 | Regulatory intelligence and ingestion | Overview: the Direction with reference, issue date and version | §2 stage 1 | 3 versions of the KYC Direction and 9 other Directions parsed into clause trees with exact positions; every quote is sliced from the source |
| 2 | Regulatory change intelligence | Change agent, real amendment of 18 Sep 2026; version history (one recorded commit on the d2 copy: clause 18, 3 obligations closed and 4 added, 2 gaps closed and 2 opened, nothing deleted) | §4 | 2 of 2 amendments on the KYC Direction; 262 of 266 amended clauses on nine other Directions; 1 substantive change reported for the Dec 2025 version where a line diff reports 507 |
| 3 | Obligation extraction | Gaps tab: obligation beside its RBI sentence | §2 stage 2 | 458 obligations, each citation verified against the source (16 rejected by the citation gate); prohibitions: 21 of 37 sentences extracted as "must not" (P-049) |
| 4 | Bank control-framework understanding (partial: policy text, not a control library) | Gaps tab: the policy passage | §2 stages 2, 4 | Controls extracted: 495 dev, 482 Central Bank, 28 Dhanlaxmi (its 4.1.2 numbering left about 8% of the text covered; every passage is still a candidate) |
| 5 | Regulatory-to-control mapping | Gaps tab: cited passage and full citation | §2 stage 4 | Right passage in the top five: 16 of 18 on the dev retrieval check; unseen: 11 of 20 planted gaps raised at the right obligation (three banks) |
| 8 | Gap identification | Gaps and Review queue tabs | §3 | Three unseen banks: every weakened number and stale threshold 7 of 7 (4 of 7 right type), all high-confidence; decoys left alone 7 of 9 (first scoring 6 of 9); deletions 0 of 4, narrowed scope 1 of 4, contradictions 0 of 2, removed owner 0 of 1, made optional 1 of 2. High-tier precision on blind samples (after the full-policy check): Central Bank 8 of 9 (6 of 7 duties only), Dhanlaxmi 9 of 9 (8 of 8), South Indian Bank 4 of 10 (7 of 10 as first labelled; duties stated in a different passage from the one compared); 21 of 28 overall; covered pairs really covered 8 of 10, 9 of 10, 9 of 10 ([report](../eval/reports/heldout_precision/report.md)) |
| 9 | Risk-based gap prioritisation | Gaps tab: residual risk and priority | §2 stage 8 | Rule-based rubric ([`risk_rubric.yaml`](../data/risk_rubric.yaml)); not scored against a key |
| 11 | Autonomous regulatory impact analysis | Change agent: scope and gaps that would open or close | §4 | 3 of 458 mappings in the scope of each real amendment; wall time per circular (dry run, first run included): hosted model 1.1 to 22 s, local qwen3:8b on one laptop GPU 1.7 to 81 s; analyst baseline 5-10 h is the author's estimate ([timing](../eval/reports/change_agent_timing.json)) |
| | **Built extras** | | | |
| 6 | Control effectiveness (design and operating) | Evidence tab: design tests of every cited control; operating tests | §2 stage 6 | Design (rule: owner, frequency and evidence stated, not judged adequate): 213 cited controls of the development policy, 74 design-effective, 139 missing an attribute; not scored against a key. Operating, synthetic logs: 4 of 4 results match the generated exception rates (2 stored, 2 in the October batch) |
| 7 | Evidence-based assessment and monitoring | Evidence tab: "Test a new evidence batch (simulation)", live in code, nothing written | §4 (second trigger) | October batch against each control's last result: re-KYC 42(1) newly failing (121 of 1,200 overdue, tolerance 5%), CKYCR 65(2) recovered (13 of 600 late); a recovered control waits for a reviewer; the model never sees evidence rows |
| 10 | Remediation recommendations | Gaps tab: one remedy per paragraph, owner and due date | §2 stage 9 | Every open high-confidence gap on dev has a remedy: 24 gaps, 16 remedies (one per paragraph, 3 Oct); 11 keep the model's wording, 4 were replaced by the regulation's own sentence after failing the fidelity check, 1 is a rule-written evidence remedy. Remedies follow the gaps, so a false alarm gets a remedy too; appropriateness not rated |
| 12 | What-if and simulation | Change agent on a draft circular; Applicability tab what-if | §4 | Dry run cannot reach the write step; hypothetical "no V-CIP": 12 obligations stop applying, 6 open gaps drop out (nothing written) |
| | Applicability by bank profile | Applicability tab | §2 stage 3b | Excluded nothing on the three banks tested; no accuracy number of its own |
| | Citations with dates | Gaps tab: source citation | §2 stage 10 | Fields tested against the source record; three dates labelled separately |
| | Guardrail: hidden instructions | Evaluation tab | §7 | Unseen: 3 of 3 caught (Central Bank and Dhanlaxmi by the code-level scan; the model flagged neither); 0 false flags on the unaltered dev policy |
| 13 | Cross-regulation intelligence | | | Not claimed |
| 14 | Regulatory contradiction detection | | | Not claimed. Development analysis: numeric conflicts inside one policy, 3 of 3 planted on the development keys, no other flag, a best case ([report](../eval/reports/policy_conflicts_dev.md)) |
