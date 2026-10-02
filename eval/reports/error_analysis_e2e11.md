# Error analysis: the 29 unkeyed high-confidence gaps of dev run e2e11

Date: 2 Oct 2026. Run: e2e11 (policy passages as candidates, no reranker, lead-in fix, judge with
the optional-duty issue) followed by the triage stage (`scripts/run_verify.py`). Key: `350b8e0`.

Method: every unkeyed gap in the high-confidence tier was read with its RBI sentence, the judge's
rationale, the passage the judge cited and the closest policy sentence by wording; then the full
policy text was searched for the subject of the obligation. The reading is by the coding
assistant (Claude), not by the user; it is an analysis aid, not a gold label.

## Result (counts)

| Outcome | Count | Rows (RBI ref) |
|---|---|---|
| Policy text is absent, technical V-CIP requirement | 13 | 27(1)(i) x2, 27(1)(ii), 27(1)(iii), 27(1)(v), 27(1)(vii), 27(1)(viii), 27(1)(ix), 27(2)(i), 27(2)(v), 27(2)(ix), 27(2)(x), 27(3)(i) |
| Policy text is absent, plausible real policy gap | 3 | 29 (KYC valid on transfer between branches), 65(8) (updated information to CKYCR within seven days), 65(10)(iv) (Dec 2025 amendment: who verifies after a CKYCR download) |
| Covered: the judge misread a passage that states it | 8 | 27(1)(ii) encryption, 42(3)(i), 42(4)(i), 43 x2, 48(1) x2, 65(8) retrieve |
| Covered: the obligation was cited at the wrong sentence, or is not an obligation | 3 | 2 (commencement clause), 42(4)(i) x2 (beneficial-ownership duties cited at the clause's first sentence) |
| Covered elsewhere, not among the candidates | 1 | 6(1) (policy approved by the Board: stated in the policy's introduction) |
| No gap by the user's rule of 2 Oct | 1 | 18 (application of mind) |

So of 29: 16 where the policy really says nothing (3 clear policy-level, 13 technical), 13 false.

## What it says about the pipeline

1. **Obligation level is now the largest open question (13 of 29).** The V-CIP requirements on
   infrastructure, encryption, IP addresses, testing and data location are absent from the
   policy. The labelling convention used on the 50-pair sheet treats such requirements as
   procedure- or system-level ("SOP expected", no policy gap), while the level classifier calls
   them policy-level. Whether they belong in the high-confidence tier or the review queue is a
   convention to decide, not a model error to fix blindly.
2. **Judge misreadings remain (8 of 29)**, mostly on passages that restate the obligation with a
   different sentence structure, where the text comparison finds too little shared wording to
   overrule the judge (overlap 0.45 to 0.60).
3. **Extraction (3) and retrieval (1) are small.**
4. **Three findings look real and are not in the answer key**: 29, 65(8) and 65(10)(iv). The
   last one is the December 2025 amendment, which the policy (effective 9 July 2025) predates.

## Not changed on the basis of this analysis

No rule was tuned after this reading. Lowering the comparison threshold would demote 2 to 4 more
false alarms on this policy, and a keyword rule for "technical requirement" would demote the 13
V-CIP rows, but both would be fitted to one policy. They are listed as options for the user.
