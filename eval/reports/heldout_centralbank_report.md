Evaluated code: tag `eval-freeze-2026-10-03`, commit `5cb728b`, run from a clean checkout (git worktree) of the tag; nothing tuned after these runs.

# Evaluation report: run `ho_centralbank`, policy `centralbank` (test set)

Answer key: `eval/answer_key_centralbank.jsonl` at commit 350b8e0 2026-09-27T14:48:06+05:30; policy text sha256 verified (1a579625b8e2...).

## Against the answer key (counts)
- planted gaps detected 3/7 (type accepted 2/7; near misses 1/7)
- planted gaps raised at the right obligation, any passage (location-tolerant) 4/7
- decoys flagged 1/3
- injections caught 1/1
- high-confidence tier: planted 3/7 (exact 3), decoys 1/3, unkeyed 15
- review queue: planted 1/7 (exact 0), decoys 0/3, unkeyed 36
- real findings correct 1/1 (0 excluded)
- by operator: contradict 0/1, delete_control 0/1, make_stale 1/1, narrow_scope 0/1, strip_design 0/1, weaken_threshold 2/2
- precision inputs: 3 planted-gap hits, 1 decoy hits, 51 unkeyed reports awaiting blind adjudication

| Row | Operator | Detected | Tier | Type accepted | Reported types |
|---|---|---|---|---|---|
| C01 | weaken_threshold | yes | high | yes | weak_threshold |
| C02 | weaken_threshold | yes | high | yes | weak_threshold |
| C03 | make_stale | yes | high | no | weak_threshold |
| C04 | delete_control | no | - | no | - |
| C05 | narrow_scope | no | - | no | - |
| C06 | contradict | near miss | review | no | weak_threshold |
| C07 | strip_design | no | - | no | - |

- Decoy C-D01: not flagged
- Decoy C-D02: FLAGGED in the high tier (false positive)
- Decoy C-D03: not flagged
- Injection C-I01: caught
- Real finding R01 (no_gap): correct

## Evidence key (operating tests)
- no evidence key

## Applicability (bank profile)
- obligations checked against the bank profile `centralbank`: applies 457, does not apply 0, to confirm 1 (decided by rule 458, by model 0)
- gaps taken out of scoring as not applicable 0; gaps carrying a 'to confirm' note 1 (a note moves nothing)
- planted gaps whose obligation was taken out: none

## Pipeline metrics (counts)
- obligations extracted 458, rejected by citation gate 16, duplicates collapsed 68
- obligation level (gaps scored only on policy-level): not_applicable 14, policy 316, sop_system 128
- controls extracted 482, rejected by citation gate 39
- mappings 458: covered 398, partial 57, missing 3
- judge control citations verified 444/458; auto-accepted 438, escalated 20
- gaps reported 59 (high-confidence 19, review queue 40); unkeyed (to blind adjudication) 51
- model time by stage (cache totals): classify_condition: 40 calls, 6.0 model-min, 28357 output tokens; classify_level: 207 calls, 51.2 model-min, 21142 output tokens; compare_numbers: 4 calls, 0.2 model-min, 125 output tokens; draft_remediation: 22 calls, 2.4 model-min, 2538 output tokens; extract_controls: 587 calls, 68.1 model-min, 108070 output tokens; extract_definitions: 102 calls, 7.5 model-min, 8785 output tokens; extract_obligations: 204 calls, 39.8 model-min, 48931 output tokens; judge: 1732 calls, 411.0 model-min, 702847 output tokens

Judge confidence and signal records: eval/reports/confidence_table.json (fitted on the development bank). Not yet measured: extraction precision/recall vs the user's labels.
