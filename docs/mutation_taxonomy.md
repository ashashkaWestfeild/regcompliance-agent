# Mutation taxonomy and answer-key design

Purpose: plant known gaps into public bank KYC/AML policies so gap detection can be scored
with precision/recall per mutation type. The answer key is committed to git **before** any
system run; the commit timestamp is the proof against self-grading.

## Operators

Each operator maps to exactly one `GapType` (src/regcomp/schemas.py), so scoring is a join.

| Operator | What the script does | Expected mapping verdict | Expected `GapType` |
|---|---|---|---|
| `delete_control` | Remove the policy section(s) implementing an obligation | `missing` | `missing_control` |
| `weaken_threshold` | Loosen a number: longer deadline, lower frequency, higher monetary/percent threshold | `partial` | `weak_threshold` |
| `narrow_scope` | Drop a customer segment / product / entity type from a control's scope | `partial` | `narrow_scope` |
| `contradict` | Insert a second clause elsewhere in the policy that conflicts with an existing one | `partial` | `internal_contradiction` |
| `make_stale` | Revert a control to the pre-amendment rule (e.g. the 25% BO threshold) | `partial` (against new version), `covered` (against old) | `stale_control` |
| `strip_design` | Remove owner and/or evidence/record-keeping language | `covered` on substance | `design_deficiency` |

Not a text mutation: `operating_failure` is planted through the synthetic evidence CSVs
(exception rate above tolerance). Separate answer-key file, same format.

## Themes

Regulation base: **RBI (Commercial Banks – Know Your Customer) Directions, 2025**, which
replaced the 2016 Master Direction on 28 Nov 2025. Status column: checked against the
current text (`data/raw/rbi/kycdir_v3_20260918.html`) on 2026-09-26. The user still has to
confirm the themes match real-world KYC findings (generic only).

| Theme | Obligation in the 2025 Directions | Status | Example mutation |
|---|---|---|---|
| `periodic_rekyc` | Periodic updation at least once every 2 yrs (high risk), 8 yrs (medium), 10 yrs (low) | verified | high risk 2 -> 5 yrs (`weaken_threshold`) |
| `risk_categorization` | Periodic review of risk categorisation at least once every six months | verified | 6 -> 12 months (`weaken_threshold`); drop the review clause (`delete_control`) |
| `beneficial_owner` | BO = natural person with more than 10% ownership/profits (company; partnership) | verified | revert to pre-2023 25% (`make_stale`); drop partnership/trust (`narrow_scope`) |
| `ckycr_upload` | Upload KYC records to CKYCR within 10 days of commencement of an account-based relationship | verified | 10 -> 30 days (`weaken_threshold`) |
| `fiu_reporting` | Furnish information under PML Rules 3/7 to FIU-IND; use FIU-IND e-filing utilities; Principal Officer arrangements | verified (see note) | remove Principal Officer arrangement (`strip_design`); contradictory filing channel (`contradict`) |
| `ongoing_monitoring` | Align monitoring with risk category; intensified monitoring of high-risk accounts; money-mule diligence | verified, replaces `tm_alert_review` | drop high-risk intensified monitoring (`narrow_scope`); remove owner (`strip_design`) |

Notes:
- **STR 7 working days / CTR ₹10 lakh are not in the Directions.** They come from the PML
  (Maintenance of Records) Rules, 2005, which the Directions reference in para 52. Ingesting
  the PML Rules would be cross-regulation (feature 13, out of scope), so mutations must not
  target those numbers.
- **`tm_alert_review` was dropped.** The Directions require systems that *generate* alerts but
  say nothing about reviewing or closing them, so a mutation there would have no obligation
  to score against.
- The real amendments give the change-agent demo two cases:
  - Dec 2025: CKYCR reliance Explanation, theme `ckycr_upload`.
  - Sep 2026: FPIs added to the certified-copy alternative. Any policy naming only NRIs/PIOs
    becomes a `narrow_scope` gap after the amendment.

## Design rules

1. **Base policies:** 2 public commercial-bank KYC/AML policies (Nainital Bank, Central Bank of
   India; never any employer's material). Record
   URL + sha256 in `data/sources.yaml`.
2. **Density:** about 3 to 5 mutations per policy, at most one per section, so gaps stay
   attributable. Target around 25 to 30 planted gaps in total, enough to report per-operator
   recall without the numbers turning into noise.
3. **Decoys (negative controls):** about 8 edits that must **not** produce a gap: rephrasing,
   reordering, making a threshold *stricter*. Without them, precision is untestable, since a
   system that flags everything would score perfect recall.
4. **Seeded and deterministic:** `mutate.py --seed N` produces byte-identical output. The
   mutated policy's sha256 goes into the answer key.
5. **Mutations are hand-authored, not LLM-generated.** Each mutation is a YAML entry with
   exact `find` / `replace` strings, and the script only applies them. This keeps the answer
   key independent of the models under test.
6. **Unmutated baseline:** run the system on the original policies too. Pre-existing gaps in
   real public policies are real findings. Label them separately and never count them as false
   positives.

## Files

```
data/mutations/spec.yaml            # hand-authored operators (input)
data/mutated/<policy>__seed<N>.txt  # output
eval/answer_key.jsonl               # committed before first system run
eval/answer_key_evidence.jsonl      # operating_failure plants
```

### `spec.yaml` entry

```yaml
- mutation_id: M007
  policy: bank_a_kyc_policy
  operator: weaken_threshold
  theme: periodic_rekyc
  find: "at least once in every two years for high risk customers"
  replace: "at least once in every five years for high risk customers"
  target_obligation_ref: "MD-KYC:38"      # clause_ref in the regulation (verify)
  note: "frequency weakened 2y -> 5y"
```

### `answer_key.jsonl` row

```json
{"mutation_id": "M007", "policy_sha256": "...", "operator": "weaken_threshold",
 "theme": "periodic_rekyc", "is_decoy": false,
 "mutated_char_start": 18234, "mutated_char_end": 18291,
 "target_obligation_ref": "MD-KYC:38", "expected_verdict": "partial",
 "expected_gap_type": "weak_threshold", "regulation_version": "MD-2016-upd-2023"}
```

## Scoring

- A detected gap is a **true positive** when its obligation's `source_clause_ref` equals
  `target_obligation_ref` **and** its cited control span overlaps
  `[mutated_char_start, mutated_char_end)`.
- A detection that matches on location but gets `gap_type` wrong counts as a TP for
  detection and as a miss for classification. Report both numbers.
- Report per-operator precision/recall and a decoy false-positive rate.
