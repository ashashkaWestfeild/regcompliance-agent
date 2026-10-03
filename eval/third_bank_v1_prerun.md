# Third unseen bank, v1 only: pre-run note (3 Oct 2026)

Committed before the run. The frozen v1 code (tag `eval-freeze-2026-10-03`, commit `5cb728b`) will
run **once** on South Indian Bank (split test3) against the frozen answer key at commit `c556c42`
(7 planted gaps, 3 decoys, 1 injection, 1 real finding). The D2 detector is not part of this run;
the D2 attempt was stopped by its own gate (branch `d2`, closing note there).

- Run: Mon 5 - Tue 6 Oct, from a clean checkout of the tag, on the separate d2 database (the live
  app's database is not touched), in chunks of 25 minutes or less, local qwen3:8b.
- **The results will be reported whatever they are**, in the same format as Central Bank and
  Dhanlaxmi: `eval/reports/scorecard_southindianbank.json` and
  `eval/reports/heldout_southindianbank_report.md`, both carrying the tag and commit.
- After scoring, a blind sheet of the high-confidence findings (sample plan and seed committed
  first, as for the other two banks) goes to the author for labelling.
- Nothing is tuned on this bank, before or after the run.
