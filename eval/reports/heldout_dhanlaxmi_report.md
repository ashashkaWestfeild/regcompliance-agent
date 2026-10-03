Evaluated code: tag `eval-freeze-2026-10-03`, commit `5cb728b`, run from a clean checkout (git worktree) of the tag; nothing tuned after these runs.

# Evaluation report: run `ho_dhanlaxmi`, policy `dhanlaxmi` (test2 set)

Answer key: `eval/answer_key_dhanlaxmi.jsonl` at commit da58e66 2026-10-02T13:19:39+05:30; policy text sha256 verified (3a5853451188...).

## Against the answer key (counts)
- planted gaps detected 2/6 (type accepted 1/6; near misses 1/6)
- planted gaps raised at the right obligation, any passage (location-tolerant) 3/6
- decoys flagged 0/3
- injections caught 1/1
- high-confidence tier: planted 2/6 (exact 2), decoys 0/3, unkeyed 42
- review queue: planted 1/6 (exact 0), decoys 0/3, unkeyed 43
- real findings correct 2/2 (2 excluded)
- by operator: contradict 0/1, delete_control 0/1, make_stale 1/1, narrow_scope 0/1, weaken_modality 0/1, weaken_threshold 1/1
- precision inputs: 2 planted-gap hits, 0 decoy hits, 85 unkeyed reports awaiting blind adjudication

| Row | Operator | Detected | Tier | Type accepted | Reported types |
|---|---|---|---|---|---|
| L01 | delete_control | no | - | no | - |
| L02 | weaken_modality | near miss | review | no | weak_modality |
| L03 | narrow_scope | no | - | no | - |
| L04 | contradict | no | - | no | - |
| L05 | make_stale | yes | high | no | weak_threshold |
| L07 | weaken_threshold | yes | high | yes | weak_threshold |

- Decoy L-D01: not flagged
- Decoy L-D02: not flagged
- Decoy L-D03: not flagged
- Injection L-I01: caught
- Real finding L-R01 (accept_set): correct
- Real finding L-R02 (known_gap): not flagged
- Real finding L-R03 (excluded): excluded
- Real finding L-R04 (no_gap): correct

## Evidence key (operating tests)
- no evidence key

## Applicability (bank profile)
- obligations checked against the bank profile `dhanlaxmi`: applies 455, does not apply 0, to confirm 3 (decided by rule 458, by model 0)
- gaps taken out of scoring as not applicable 0; gaps carrying a 'to confirm' note 0 (a note moves nothing)
- planted gaps whose obligation was taken out: none

## Pipeline metrics (counts)
- obligations extracted 458, rejected by citation gate 16, duplicates collapsed 68
- obligation level (gaps scored only on policy-level): not_applicable 14, policy 316, sop_system 128
- controls extracted 28, rejected by citation gate 1
- mappings 458: covered 371, partial 75, missing 12
- judge control citations verified 430/458; auto-accepted 415, escalated 43
- gaps reported 88 (high-confidence 44, review queue 44); unkeyed (to blind adjudication) 85
- model time by stage (cache totals): classify_condition: 40 calls, 6.0 model-min, 28357 output tokens; classify_level: 207 calls, 51.2 model-min, 21142 output tokens; compare_numbers: 6 calls, 0.3 model-min, 188 output tokens; draft_remediation: 22 calls, 2.4 model-min, 2538 output tokens; extract_controls: 607 calls, 69.9 model-min, 110721 output tokens; extract_definitions: 102 calls, 7.5 model-min, 8785 output tokens; extract_obligations: 204 calls, 39.8 model-min, 48931 output tokens; judge: 1921 calls, 440.1 model-min, 747134 output tokens

Judge confidence and signal records: eval/reports/confidence_table.json (fitted on the development bank). Not yet measured: extraction precision/recall vs the user's labels.
