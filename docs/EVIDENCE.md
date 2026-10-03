# Evidence matrix

One row per claimed feature of Problem 1: where the demo shows it, where the architecture
document explains it, and what was measured. Counts only. "Unseen" means the two held-out banks,
each run once from the tag `eval-freeze-2026-10-03`; "dev" means the development bank the system
was built on. Demo times refer to the video script and are confirmed after recording.

**Claim: F3 / D1.** Eight floor features plus built extras; depth D1 because gap detection on the
unseen banks is not yet reliable enough for D2 (see the architecture document, section 10).

| # | Feature | Demo | Architecture | Measured |
|---|---|---|---|---|
| 1 | Regulatory intelligence and ingestion | Overview: the Direction with reference, issue date and version | §2 stage 1 | 3 versions of the KYC Direction and 9 other Directions parsed into clause trees with exact positions; every quote is sliced from the source |
| 2 | Regulatory change intelligence | Change agent, real amendment of 18 Sep 2026 | §4 | 2 of 2 amendments on the KYC Direction; 262 of 266 amended clauses on nine other Directions; 1 substantive change reported for the Dec 2025 version where a line diff reports 507 |
| 3 | Obligation extraction | Gaps tab: obligation beside its RBI sentence | §2 stage 2 | 458 obligations, each citation verified against the source (16 rejected by the citation gate); prohibitions: 21 of 37 sentences extracted as "must not" (P-049) |
| 4 | Bank control-framework understanding | Gaps tab: the policy passage | §2 stages 2, 4 | Controls extracted: 495 dev, 482 Central Bank, 28 Dhanlaxmi (its 4.1.2 numbering left about 8% of the text covered; every passage is still a candidate) |
| 5 | Regulatory-to-control mapping | Gaps tab: cited passage and full citation | §2 stage 4 | Right passage in the top five: 16 of 18 on the dev retrieval check; unseen: 7 of 13 planted gaps raised at the right obligation |
| 8 | Gap identification | Gaps and Review queue tabs | §3 | Unseen: every weakened number and stale threshold 5 of 5 (3 of 5 right type), all high-confidence; decoys left alone 5 of 6; deletions 0 of 2, narrowed scope 0 of 2, contradictions 0 of 2, removed owner 0 of 1, made optional 0 of 1. High-tier precision: blind check in progress |
| 9 | Risk-based gap prioritisation | Gaps tab: residual risk and priority | §2 stage 8 | Rule-based rubric ([`risk_rubric.yaml`](../data/risk_rubric.yaml)); not scored against a key |
| 11 | Autonomous regulatory impact analysis | Change agent: scope and gaps that would open or close | §4 | 3 of 458 mappings in the scope of each real amendment; wall time per circular (dry run): about 2 s for a permissive amendment, 14-22 s with the hosted model when a duty is added, at most about 81 s on one laptop GPU; analyst baseline 5-10 h is the author's estimate ([timing](../eval/reports/change_agent_timing.json)) |
| | **Built extras** | | | |
| 6 | Control effectiveness (design and operating) | Evidence tab | §2 stage 6 | Operating tests on synthetic logs: 2 of 2 correct (dev) |
| 7 | Evidence-based assessment and monitoring | Evidence tab | §4 (second trigger) | Newly failing, still failing, recovered, healthy; the model never sees evidence rows |
| 10 | Remediation recommendations | Gaps tab: one remedy per paragraph, owner and due date | §2 stage 9 | 7 remedies on dev (one per paragraph); 5 of 7 keep the model's wording after the fidelity check; appropriateness rating pending |
| 12 | What-if and simulation | Change agent on a draft circular; Applicability tab what-if | §4 | Dry run cannot reach the write step; hypothetical "no V-CIP": 12 obligations stop applying, 6 open gaps drop out (nothing written) |
| | Applicability by bank profile | Applicability tab | §2 stage 3b | Excluded nothing on the three banks tested; no accuracy number of its own |
| | Citations with dates | Gaps tab: source citation | §2 stage 10 | Fields tested against the source record; three dates labelled separately |
| | Guardrail: hidden instructions | Evaluation tab | §7 | Unseen: 2 of 2 caught, both by the code-level scan (the model flagged neither); 0 false flags on the unaltered dev policy |
| 13 | Cross-regulation intelligence | | | Not claimed |
| 14 | Regulatory contradiction detection | | | Not claimed |
