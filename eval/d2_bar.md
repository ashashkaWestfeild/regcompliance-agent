# D2 bar for the second evaluation (pre-registered)

Status: confirmed by the author on 3 Oct 2026. Committed before the third bank is chosen or
drafted; no edit after this commit without a logged reason (commit message and PROBLEMS_LOG).

## Scope of the attempt
- The evaluation of record for v1 stays tag `eval-freeze-2026-10-03` (claim F3 / D1). The v0
  submission on Unstop (Sun 4) carries that claim and is made before any D2 work.
- From 4 Oct, Central Bank and Dhanlaxmi are development banks: their misses are analysed and the
  detector is built with them in view. Their numbers are no longer evidence of anything unseen.
- One new detector: duties missing or narrowed in the policy (operators `delete_control` and
  `narrow_scope`). Contradictions stay on the roadmap. Prompts stay schema-generic.
- Detector findings go to the review queue by default; they reach the high-confidence tier only if
  the development gates below hold.
- All D2 work runs on the `d2` git branch and a separate Neon database branch; `main` and the live
  app are untouched unless D2 is earned.
- Everything is built, run and submitted by Sat 10 Oct 15:00. Nothing developed after 11 Oct is
  presented as part of the solution.

## Third-bank selection rule (code only, no model)
Candidates in order: South Indian Bank (KYC/AML/CFT policy, updated to Aug 2025), Bank of India
(KYC/AML/CFT policy), CSB Bank (2021 policy). The first candidate whose PDF parses with passage
coverage of at least 60% of its text (parser only, no model call) is used, and the coverage figure
is recorded with the key. Coverage is measured with the parser from `eval-freeze-2026-10-03`, the
same code as the v1 run. No switching to a candidate that would make the test easier.

Applied 3 Oct (logged before the key freeze, PROBLEMS_LOG P-053): passage coverage came out at about
99% for every bank, Dhanlaxmi included (166,558 of 168,189), so it does not show the problem that
hurt Dhanlaxmi. Selection therefore also used extraction-unit coverage, the text the v1 unit
builder sends to the model (code only, same v1 parser): South Indian Bank 134,634 of 165,629
non-space characters, against Dhanlaxmi 14,022 of 168,189. South Indian Bank passes both measures
(passages 164,260 of 165,629).

## Answer key composition for the third bank (fixed in advance)
7 planted gaps: 2 `delete_control`, 2 `narrow_scope`, 2 number-type (`weaken_threshold` or
`make_stale`), 1 drawn from {`contradict`, `weaken_modality`, `strip_design`}. Plus 3 decoys and
1 injection. Targets by a seeded draw, seed committed first; every delete / narrow mutation passes
`scripts/coverage_check.py` as before. The author reviews the key; it is frozen and pushed before
any model reads the policy.

## Runs on the third bank (both pre-registered, each run once)
- **v1 run:** from a clean checkout of `eval-freeze-2026-10-03`, run only after the kill point is
  passed and the second tag exists, so its results cannot be seen while the detector is built and
  the D2 database is not shared with development re-measurements in the meantime (amended 3 Oct,
  PROBLEMS_LOG P-054).
- **v2 run:** from a clean checkout of the second tag, after the v1 run.
- Both read the same frozen key and policy copy, on the D2 database branch, in chunks of 30
  minutes or less. The report states what the detector added: planted gaps found and extras
  (unkeyed findings), v2 against v1.
- If compute does not allow the v1 run, the volume condition falls back to a fixed cap tied to
  v1's level (at most 85 extras, the higher of the two v1 held-out banks), and the report says why.

## The bar
On the v2 run, all conditions must hold:

1. Planted gaps found at the right obligation (either tier): at least 5 of 7, including at least
   1 of 2 `delete_control` and at least 1 of 2 `narrow_scope`.
2. Volume: v2 extras (unkeyed findings, both tiers together) at most v1 extras + 25 on the same
   bank (fallback: at most 85, see above).
3. Decoys flagged: at most 1 of 3, and none in the high-confidence tier.
4. High-confidence precision on a blind sample (10 findings + 10 covered pairs, seed committed
   first, the author labels, every "gap" label checked against the whole policy): at least 8
   decided findings, and at least 8 of the decided findings real. If the tier holds fewer than 10
   findings, all are labelled and at most 2 may be false.
5. The detector's own findings: a blind sample of up to 10 of them (seed committed first, the
   author labels, full-policy check on every "gap" label): at least 5 of the decided ones real.
   If the detector raises fewer than 10 findings, all are labelled; at least half of the decided
   ones must be real, with at least 3 decided. (Amended 3 Oct before any third-bank work: see
   PROBLEMS_LOG P-052.)
6. The injection is caught.
7. Number-type gaps: both found at the exact passage in the high-confidence tier (v1: 5 of 5).

If any condition fails, the claim stays F3 / D1 and the attempt is reported on the roadmap with
its numbers.

## Gates before the second freeze (development data only)
- Recall on all four existing keys (Nainital, Nainital second key, Central Bank, Dhanlaxmi): the
  detector finds at least 3 of the 4 held-out deletion / narrowed-scope misses (C04, C05, L01,
  L03) at the right obligation, and loses none of the planted gaps found today.
- Precision gate: on the author's already-labelled rows (the 21-row dev sheet and the two 20-row
  held-out sheets), the detector raises no new high-confidence finding on a row marked "no gap".
  If it does, detector findings stay in the review queue.
- Kill point: if the gates are not met by Wed 7 Oct night, the attempt stops and v0 stands.

## If D2 is earned
Merge `d2` into `main`, redeploy the app and re-take the result lock as soon as the result is in,
and no later than Fri 9 Oct. Sat 10 then touches only the deck, the README and the video.
