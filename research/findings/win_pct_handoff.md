# Win % redesign — handoff data + code map

Everything you asked for, from the 488-side production-basis backtest
(`mock_baseline_results.jsonl`, weeks 1–5, both sides of each meet).

---

## 1. Validation data → `win_pct_validation.csv` (488 rows)

Columns: `week, team, opp, division, raw_pred_margin, biascorr_pred_margin, actual_margin, won, has_current`

- `raw_pred_margin` = the optimizer's simulate_match margin **before** display calibration. **Biased +60.6 pts on average** (W1 +106, W5 +33) — this is the inflation the legacy intercept-probit was papering over. Do **not** fit on this directly.
- `biascorr_pred_margin` = `raw_pred_margin` with the systematic per-(week, division) bias removed. This is a faithful proxy for the live **displayed** margin (the calibration is exactly a per-week reanchor + per-division slope; see §3). Mean bias **+0.00**. Fit on this.
- `actual_margin` = `truth − opp_truth`; `won` = 1 if we actually won. Use either for MLE.

Caveat: `biascorr_pred_margin` is the bias removed *statistically* (group de-mean), which matches the calibration's distribution but not its exact per-team coach-anchor. For the truly exact displayed margin per side, a backtest re-run can record it — say the word and I'll add it to `predict_side` and re-run. σ below is stable either way.

## 2. Calibration summary (the numbers you wanted)

**σ for Φ(margin/σ), measured on the bias-corrected margin:**

| basis | σ (residual SD of pred − actual margin) |
|---|---|
| raw margin | 58.0 (with +60.6 mean bias — unusable) |
| after week correction | 51.1 |
| **after week + division correction** | **49.9**, mean bias **+0.00** |

Per-week σ (week+division corrected) — a per-week σ fits noticeably better than one global value:

```
W1 σ=70.6   W2 σ=45.1   W3 σ=41.3   W4 σ=50.1   W5 σ=34.9
```

**Win rate by bias-corrected predicted margin** (this is the curve Φ must reproduce — clean and monotonic):

```
margin [-999,-40):  8.5%      [ 5, 15): 56.7%
margin [ -40,-25): 26.2%      [15, 25): 67.7%
margin [ -25,-15): 36.4%      [25, 40): 69.7%
margin [ -15, -5): 41.2%      [40,999): 91.3%
margin [  -5,  5): 46.3%
```

**Brier score** (0.25 = coin flip):
- Current shipped `Φ(raw_margin / 30)` → **0.2805** (worse than a coin flip — confirms it's broken)
- Origin-forced `Φ(biascorr_margin / 50)` → **0.1501**

So: origin-forced Φ with σ≈50 (or per-week) on the unbiased margin is already well-calibrated; the intercept is not needed (mean bias is 0 by construction). If an intercept survives your MLE, it means the bias fix left a per-side residual — chase that, don't absorb it.

## 3. What the fix is and where it lives (the incoherence)

The displayed **points** and the displayed **win %** are computed from **two different margins**, in `_run_and_cache` (app.py). That's the whole bug.

1. **Win %** (`analytical_winp`) is computed at **app.py:3614–3617** from the *theory-2* margin: `mstats["margin"]` at that point = raw sim margin + `delta` (the theory-2 anchor, set at **app.py:3604**), passed through `Φ(m / σ)` with **σ = `_winprob_sigma_margin` ≈ 30** (app.py:3614). This becomes the headline (app.py:2392 / 2401, `headline_wp = analytical * 100`).
2. **Displayed points / margin** (the "Median us – them") is **recomputed afterward** by the conserving pass at **app.py:3651–3655**: `our_median = your_full`, `opp_median = pool − your_full`, `margin = 2·your_full − pool`, where `your_full` = the calibrated total (`mc_total` after the theory-2 adjustment at ~app.py:3559, = `pred_coach + reanchor[week] − div_slope·(division − divmean)`).

Because the win % is computed **before** the conserve pass and from a different margin, a displayed +71-pt margin can read 85 % (the win-% margin was ~+30), and a displayed tie can read ~10 % (its win-% margin was negative). The honest, unbiased displayed number is the **conserve margin at app.py:3655** — that is what the win % should read.

**The fix:** move/compute `analytical_winp` **after** the conserve pass, from the post-conserve `mstats["margin"]`, origin-forced `Φ(margin / σ)` with σ refit from §2 (≈50 global, or per-week). Delete the σ=30 / theory-2-margin computation at app.py:3614–3617 (and the no-longer-needed `_winp_margin`/`_winp_fn` capture at app.py:3533–3542). Then points and win % finally read one margin.

**Don't miss:** the Predicted↔Last-week toggle reuses `_winp_fn` + `_winp_margin` to compute the last-week win % (app.py:3699–3712, `wlw = _winp_fn(_winp_margin + (raw_lw_margin − raw_pred_margin))`). If you repoint the basis/σ, update that path too so the toggle stays consistent.
