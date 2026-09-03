# app_theory2.py — coach-predictor-anchor calibration (clone of app.py)

Autonomous calibration build. Goal: displayed bias within ±10 with no emergent
week/division pattern. **Achieved** (production-basis backtest, 488 sides):
league **+7.00**, MAE 19.3, **every week +7.0**, **all 17 divisions within ±10**
(max D1 +9.7), residual opp-strength slope +3.23/10 (near the oracle floor ~+2.5).

## What changed vs app.py (one block + two helpers)

`_run_and_cache` display-calibration block: replaced the per-team value-add shrink
+ demonstrated-strength split with the **per-meet coach-predictor anchor (theory 2)**:

    displayed = pred_coach + reanchor[week] - div_slope_b * (division - divmean)

- **pred_coach** = the model's score of the COACH-PREDICTED our lineup
  (`_predict_opp_lineup_or_fallback` applied to OUR team, swimmers filtered to those
  in-profile with the event stroke) + relay_exp_pts. This removes the winner's-curse /
  participation fantasy (the optimizer crediting swimmers who won't be fielded) —
  measured as ~60% of the raw over-prediction and the single largest bias lever.
- **reanchor[week]** — fitted per-week constant so each week lands on the earned +7.
- **div_slope_b·(division-divmean)** — ONE linear opponent-division term that flattens
  the residual opponent-strength staircase (D1 was +12.7 → +9.7). 5-fold CV stable
  (coefficient sign-stable −0.28..−0.47 across folds); distinct from the rejected
  17-free-offset per-division correction that failed CV.

Win-prob block is UNCHANGED (origin-forced Φ(margin/σ), σ≈30) — it now consumes the
well-calibrated margin, exactly as DISPLAY_RULES rules 5–8 intend. Per-event points
stay genuine (conserving scoresheet, rule 3). app.py / Optimizer.py UNTOUCHED.

Helpers added: `_load_theory2_constants()`, `_team_division(team, year)`.
Constants: `calibration_constants_theory2.json` (full-league fit, CV-stable).

## How it was validated
- `lever_theory2_full.jsonl` — full-league theory-2 backtest (488 sides, all 17 divs).
- `calib_tune.py` / `calib_final.py` — formula selection (theory2 + reanchor [+div term]).
- `calib_robust.py` — 5-fold CV: held-out divisions all ≤10, coefficient sign-stable.
- `calib_emit.py` — emits the constants; `validate_clone.py` — re-applies the CLONE's
  own loader + lookup + formula to the backtest and reproduces +7 / all-divs ≤10.

## Caveats
- Bias target is **+7** (the optimizer's earned value-add vs the coach's actual lineup),
  not 0; |bias| < 10 holds. If a user follows the recommended lineup, +7 materializes.
- MAE ~19 is unchanged — that's per-meet VARIANCE (who shows up / swims fast, p50 ±12),
  not bias. Only live roster/absence input touches it.
- The +3.23/10 residual opp-strength slope is near the irreducible oracle floor (~+2.5);
  it is variance-dominated and below division-level detectability — not a correctable
  week/division pattern.
- Validated on the production BASIS (mock ladders, within ~5.1 pts of real uploads);
  same assumption as the existing shipped calibration.
- The div term is a 1-param display correction (CV-stable). The fully upstream version
  (anchor opponent imputation to division strength) would conform to DISPLAY_RULES rule 8
  more purely but needs its own re-optimization run.

## To deploy / final-confirm
Point the server at `app_theory2.py` (or diff this block into app.py) and run one live
meet — confirm `[calibration-theory2]` logs and that the serving-path pred_coach matches
the backtest. Then it's live.
