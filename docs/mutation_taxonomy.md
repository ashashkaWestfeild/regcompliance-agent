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
| `make_stale` | Revert a control to the pre-amendment rule | `partial` (against new version), `covered` (against old) | `stale_control` |
| `strip_design` | Remove owner and/or evidence/record-keeping language | `covered` on substance | `design_deficiency` |

Not a text mutation: `operating_failure` is planted through the synthetic evidence CSVs
(exception rate above tolerance). Separate answer-key file, same format.

## Themes

The themes come from public RBI penalty patterns. The user still has to check them against
real KYC findings (generic only). Every example value below must be **verified against the
Master Direction text before the answer key is generated**. I wrote them from memory and
have not checked them.

| Theme | Obligation (to verify in MD) | Example mutation |
|---|---|---|
| `periodic_rekyc` | Periodic updation: high risk at least every 2 yrs, medium 8, low 10 | high risk 2 -> 5 yrs (`weaken_threshold`) |
| `risk_categorization` | Customers risk-categorised; categorisation reviewed periodically | drop review clause (`delete_control`) |
| `beneficial_owner` | Identify BO; company threshold lowered 25% -> 10% by the 2023 amendment | keep 25% (`make_stale`); drop trusts (`narrow_scope`) |
| `ckycr_upload` | Upload KYC records to CKYCR within a fixed number of days of account opening | 10 -> 30 days (`weaken_threshold`) |
| `str_ctr_reporting` | STR within 7 working days of the suspicion conclusion; CTR monthly for cash > INR 10 lakh | add "CTR filed quarterly" elsewhere (`contradict`) |
| `tm_alert_review` | Transaction-monitoring alerts reviewed and closed with documented rationale | remove reviewer + record-keeping (`strip_design`) |

The beneficial-owner threshold change is the best `make_stale` case. It is a real
amendment, so the same fact also drives the change-intelligence demo.

## Design rules

1. **Base policies:** 2 or 3 public bank KYC/AML policies (never the user's employer). Record
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
