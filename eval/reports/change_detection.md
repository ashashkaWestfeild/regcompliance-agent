# Change detection vs RBI amendment markers

Ground truth: clauses carrying RBI's own "with effect from <date>" marker for the amendment. Counts only.

| Amendment | Diff | Clauses compared | Unchanged | Cosmetic | Substantive reported | Marked by RBI | Found | Missed | Extra |
|---|---|---|---|---|---|---|---|---|---|
| 29 Dec 2025 (CKYCR reliance) | PDF -> PDF | 478 | 463 | 14 | 1 | 1 | 1/1 | 0 | 0 |
| 18 Sep 2026 (FPIs, certified copy) | HTML -> HTML | 548 | 547 | 0 | 1 | 1 | 1/1 | 0 | 0 |

  - 29 Dec 2025 (CKYCR reliance): found ['65(10)(iv)']
  - 18 Sep 2026 (FPIs, certified copy): found ['5(1)(v)']

Cosmetic = differs only in whitespace, quotes, hyphens, case or footnote brackets; never sent to the model. A naive line diff of the same PDF pair reported 507 changes.
