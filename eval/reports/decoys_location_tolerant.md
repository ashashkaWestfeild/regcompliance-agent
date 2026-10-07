# Decoys under the location-tolerant rule (computed 7 Oct 2026)

The published decoy figure, 7 of 9 left alone, is strict: a decoy counts as flagged only when a
gap points at the decoy's own passage. The planted figure 11 of 20 is location-tolerant: a gap
at the right obligation counts, whatever passage it points at. This report completes the pair by
applying the location-tolerant rule to the decoys. The frozen results do not change.

Computed from stored data only, with no model call and no write: the frozen runs' gap lists
(`eval/runs/ho_<bank>/gaps.csv` in the tag worktree, written by the frozen code on 3 Oct), the
held-out precision snapshots (every pair judged covered, saved 3-4 Oct), the frozen scorecards,
and the obligation references (the regulation's 458 extracted obligations, the same in every
run because extraction of the regulation is served from the same cache).

| Decoy | RBI ref | Obligations at the ref | Strict | Location-tolerant | Evidence |
|---|---|---|---|---|---|
| C-D01 | 44(1) | 2 | left alone | left alone | both judged covered |
| C-D02 | 5(1)(iv)(d) | 1 | flagged | flagged | the strict flag (high tier) |
| C-D03 | 43 | 5 | left alone | **flagged** | 2 narrowed-scope gaps on other passages (review queue) |
| L-D01 | 5(2)(v)(c) | **0** | left alone | left alone | no obligation extracted at this ref |
| L-D02 | 45, 45(1) | **0** | left alone | left alone | obligations exist only at 45(1)(i)-(v) and 45(2) |
| L-D03 | 21(6) | **0** | left alone | left alone | no obligation extracted at 21(6) (21(5) and 21(7) exist) |
| S-D01 | 65(2) | 1 | left alone | left alone | judged covered (corrected scoring, P-057) |
| S-D02 | 53 | 2 | left alone | left alone | both judged covered |
| S-D03 | 5(1)(iv)(d) | 1 | flagged | flagged | the strict flag (review tier) |

**Result.** Decoys left alone: 7 of 9 strict, 6 of 9 location-tolerant. The complete pairs:
9 of 20 planted at the exact passage against 7 of 9 decoys left alone (strict); 11 of 20 planted
at the right obligation against 6 of 9 decoys left alone (location-tolerant).

**Reachability.** The scorer matches regulation references exactly, and the three Dhanlaxmi
decoys sit at references where no obligation was extracted, so they could not have been flagged
under either rule. On the 6 reachable decoys: 4 of 6 left alone strict, 3 of 6
location-tolerant. Every one of the 20 planted rows is reachable (checked the same way), so the
planted figures are not affected.
