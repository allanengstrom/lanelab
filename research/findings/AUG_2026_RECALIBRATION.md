# August 2026 Recalibration — stale chart, two leaks, one constant

*2026-08-28. Full-league 2025-season backtest (production-faithful harness,
488 sides after data repair). Numbers final in the README chart; this doc
records the investigation.*

## Why this happened

The README's calibration heatmap dated June 15 showed division 17 over-predicted
by +11 to +19 every week. Investigating that stripe found three separate
problems, none of which was the one the chart suggested.

## Finding 1 — the published chart was stale

The June-15 chart predates the June-24 build and the July–August work. A
June-26 full eval (488 sides, `data/prod_eval_results.jsonl`) already showed
league bias +8.1 (target +7), division spread 1.88, and D17 at only +5.8 —
the published chart was two generations of code behind the repo.

## Finding 2 — a fresh eval ran +14 hot; bisected into two causes

Re-running the same harness on current code predicted **+14.3 higher on
identical sides** than June-26. Worktree bisection (June code+data vs August
code+data, 15-side panel, W2–5) attributed it:

| cause | effect | nature |
|---|---|---|
| 2026-season history present in the file during a 2025 backtest | **+5.4** | eval-only leakage — production never sees the future; fixed with the `HISTORY_MAX_YEAR` guard in `_load_history` (prod_eval sets it) |
| deliberate July/Aug improvements (5-year z-projected prior lookup, `_prefer_real_over_imputed_fill`, Optimizer home-band re-homing) | **+5.5** | real — lineups got faster with no recalibration |
| residual small data diffs / MC noise | +2.3 | — |

## Finding 3 — a mislabeled ladder file was poisoning division 16

`time_trials/annandale.json` contained **Sleepy Hollow B&R's 2025 ladder**
saved under Annandale's name (a `.mislabeled_shbr_copy` sibling shows it had
been noticed before, but the live file survived). Annandale's profile carried
172 swimmers — its own roster plus all of SHBR — and the model predicted them
at ~340 points against a ~160-point reality, inverting every Annandale meet
and poisoning half of division 16's sample (MAE 81 in that cell). The file is
removed; the affected sides were re-run on clean data.

## The fix that shipped

1. **Forfeit discount** (`FORFEIT_DISCOUNT=team`): each fill-containing event's
   points are blended toward the fill-stripped score with probability equal to
   the team's *measured* prior-year no-show rate (1 − participation). No fitted
   constants. Applied to the per-event rows so the conserving scoresheet keeps
   it — the June participation shrink was silently discarded because it
   adjusted only the total, which the conserve pass re-sums from rows.
2. **League reanchor** (`calibration_constants.json` → `_league_reanchor`):
   after the above, the per-division deviations are uniform — a level offset,
   not structure. One league-wide constant (**C = 10.25**, fitted on the full
   488-side run, 2-fold cross-validated, fold-transfer residual ±1.2, weeks
   flat after subtraction) is applied multiplicatively across the
   individual-event rows in the conserve pass, so sweeps stay sweeps and rows
   still sum to the headline.

**Isolated forfeit-discount effect** (100 identical sides, discount off vs on):
D17 **−9.1**, D16 −2.7, D15 −1.0, D5 elite control +1.4 (within noise) —
graded by participation exactly as the mechanism predicts.

**End state** (488 sides, honest basis): league bias on the +7 target by
construction, **MAE 20.88** (June-26 basis: 21.80; the stale June-15 chart:
19.84 on leaky, pre-improvement code — not comparable), **division spread
1.71** (published chart: 4.51), every division within ±3.3 of target, D17 row
at −2.4. Chart: `research/img/SHIPPED_honest_heatmap_aug2026.png`.

**Deliberately NOT done:** per-division fitted offsets (n≈20–30 per division —
the overfit trap the project has rejected before), and the multi-band phantom
extension from the D17 investigation (the forfeit discount addresses the same
mechanism at lower risk).

## Caveats

- C was fitted on the 2025-season backtest basis. Live-season data flows
  (uploaded ladders) differ from backtest reconstruction; re-validate the
  constant against live totals early next season before trusting it blindly.
- Bottom-division MAE remains elevated (D17 ≈ 40 vs league ≈ 21) — that is
  meet-level chaos (who shows up), not bias; one D17 meet in the backtest is
  predicted fully inverted even on clean data.
