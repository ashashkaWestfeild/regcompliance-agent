Evaluated code: tag `eval-freeze-2026-10-03`, commit `5cb728b`, run once, on 3 Oct, from a clean checkout (git worktree) of the tag with only South Indian Bank's data files added (key c556c42, profile 79a164b); nothing tuned after this run.

Procedure note: Corrected tail. The first pass ran three code-only steps without --policy, so they took Nainital defaults: load_metadata stored Nainital's title, run_tests used Nainital's synthetic evidence logs (a CKYCR exception log landed on this bank's 10-day CKYCR sentence, decoy S-D01, and flagged it high), and run_applicability used Nainital's profile (0 gaps moved). Those three steps were re-run with --policy southindianbank, as in the Central Bank and Dhanlaxmi runs (with run_verify between them, in the v1 order), and the bank was scored again with the tag's score.py. No model output changed (every model call came from the cache). First scoring: planted 4/7 exact, decoys flagged 2/3 (S-D01 high, S-D03 review); corrected: planted 4/7 exact, decoys flagged 1/3 (S-D03 review).

# Evaluation report: run `ho_southindianbank`, policy `southindianbank` (test3 set)

Answer key: `eval/answer_key_southindianbank.jsonl` frozen at commit c556c42 (2026-10-03); the run used the file as at af84d91, which differs only in the theme label of real finding S-R01 (ckycr_upload -> vcip; scoring unchanged, PROBLEMS_LOG P-054). The key was copied into the tag worktree and hash-checked against the committed file (sha256 23b503fde833...); policy text sha256 verified (b2ce07d2bb24...).

## Against the answer key (counts)
- planted gaps detected 4/7 (type accepted 3/7; near misses 0/7)
- planted gaps raised at the right obligation, any passage (location-tolerant) 4/7
- decoys flagged 1/3
- injections caught 1/1
- high-confidence tier: planted 2/7 (exact 2), decoys 0/3, unkeyed 12
- review queue: planted 2/7 (exact 2), decoys 1/3, unkeyed 29
- real findings correct 1/1 (0 excluded)
- by operator: delete_control 0/2, make_stale 1/1, narrow_scope 1/2, weaken_modality 1/1, weaken_threshold 1/1
- precision inputs: 4 planted-gap hits, 1 decoy hits, 41 unkeyed reports awaiting blind adjudication

| Row | Operator | Detected | Tier | Type accepted | Reported types |
|---|---|---|---|---|---|
| S01 | delete_control | no | - | no | - |
| S02 | delete_control | no | - | no | - |
| S03 | narrow_scope | no | - | no | - |
| S04 | narrow_scope | yes | review | yes | narrow_scope |
| S05 | make_stale | yes | high | no | weak_threshold |
| S06 | weaken_threshold | yes | high | yes | weak_threshold |
| S07 | weaken_modality | yes | review | yes | weak_modality |

- Decoy S-D01: not flagged
- Decoy S-D02: not flagged
- Decoy S-D03: FLAGGED in the review tier (false positive)
- Injection S-I01: caught
- Real finding S-R01 (no_gap): correct

## Evidence key (operating tests)
- no evidence key

## Applicability (bank profile)
- obligations checked against the bank profile `southindianbank`: applies 458, does not apply 0, to confirm 0 (decided by rule 458, by model 0)
- gaps taken out of scoring as not applicable 0; gaps carrying a 'to confirm' note 0 (a note moves nothing)
- planted gaps whose obligation was taken out: none

## Pipeline metrics (counts)
- obligations extracted 458, rejected by citation gate 16, duplicates collapsed 68
- obligation level (gaps scored only on policy-level): policy 458
- controls extracted 373, rejected by citation gate 12
- mappings 458: covered 409, partial 46, missing 3
- judge control citations verified 437/458; auto-accepted 436, escalated 22
- gaps reported 49 (high-confidence 16, review queue 33); unkeyed (to blind adjudication) 41
- model time by stage, totals for the whole d2 database cache, not this run (scope_check is the stopped D2 detector and was not part of this run): classify_condition: 40 calls, 6.0 model-min, 28357 output tokens; classify_level: 207 calls, 51.2 model-min, 21142 output tokens; compare_numbers: 10 calls, 0.5 model-min, 331 output tokens; draft_remediation: 40 calls, 4.1 model-min, 4953 output tokens; extract_controls: 819 calls, 93.0 model-min, 148394 output tokens; extract_definitions: 102 calls, 7.5 model-min, 8785 output tokens; extract_obligations: 205 calls, 40.2 model-min, 49246 output tokens; judge: 2112 calls, 466.4 model-min, 793891 output tokens; scope_check: 164 calls, 21.2 model-min, 34480 output tokens
- model calls made during this run (cache rows created 22:15-23:30 IST on 3 Oct): extract_controls 212 calls, 23.2 model-min; judge 189 calls, 26.2 model-min; compare_numbers 4 calls, 0.2 model-min. Every other call (the regulation side, obligation level, definitions) came from the cache.

Judge confidence and signal records: eval/reports/confidence_table.json (fitted on the development bank). Not yet measured: extraction precision/recall vs the user's labels.
