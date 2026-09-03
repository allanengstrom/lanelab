# Findings for other agent: D17 bias is multi-band, not 8U-specific

## TL;DR

Your `_hybrid_fill_opp_8u` fix is working as designed — it cuts D17 bias by **−13.2 pts**, almost entirely via 8U. But D17 still has **+14 pts residual bias** that lives in the 9-10 / 11-12 / 13-14 bands, not 8U. **Extending the same per-division phantom logic to those bands should close most of the gap.**

## Empirical setup

- 18 D17 team-side observations from W1 across 2023, 2024, 2025
- 18 D5 team-side observations from W1 as elite-tier control
- Pure-greedy picker, predicted score vs actual meet score
- Tested H1 (per-band breakdown) and H2 (with vs without `_hybrid_fill_opp_8u`)

## Result 1: bias spreads across all non-8U bands

```
D17 vs D5 per-band predicted points (D17 - D5 difference):
  band       D17_pred    D5_pred    D17-D5
  8U            36.44      38.44     -2.00     ← essentially equal
  9-10          39.44      36.94     +2.50     ← +2.5pt over D5
  11-12         39.61      36.00     +3.61     ← +3.6pt over D5  ← largest
  13-14         38.22      36.00     +2.22     ← +2.2pt over D5
  15-18         36.61      36.00     +0.61     ← small over D5
  relay         29.00      29.67     -0.67
```

The "developmental tier" issue is NOT concentrated in 8U. D17 over-predicts in 9-10, 11-12, 13-14 by a few points each — but the EFFECT IS CUMULATIVE: the sum is ~+9pt in the non-8U bands alone.

## Result 2: your 8U fix works exactly as designed

```
Without _hybrid_fill_opp_8u:    bias = +27.56     8U predicted = 36.44
With    _hybrid_fill_opp_8u:    bias = +14.33     8U predicted = 24.39
Δ:                              −13.22            −12.06
```

The 13.2pt bias reduction comes almost entirely (12 of 13 pts) from the 8U band. So the fix nails 8U. The remaining +14 pts is structurally elsewhere.

## Hypothesized mechanism (same as 8U, different bands)

Bottom-division teams (D15-D17) have many rookies in 9-10 / 11-12 / 13-14, not just 8U. Our imputation gives those rookies league-baseline times. The league-wide baseline is dominated by elite divisions, so:

- A D17 11-12 rookie gets imputed at the league baseline (~44s for 50-back)
- Reality: D17 11-12 rookies actually race ~50-55s in races
- Net: opp's predicted lineup looks artificially fast → we predict winning fewer points against them → we under-rate opp → we over-predict our own score

Same problem your 8U fix solves, just propagated up through the older age groups.

## Recommendation

Extend `_hybrid_fill_opp_8u` to a generalized `_hybrid_fill_opp_band(band)` for the four bands 8U, 9-10, 11-12, 13-14, applied only when the opp team is in a bottom-tier division (and that band's profile is mostly imputed).

Mechanism:
1. For each opp event, identify whether the swimmers in our predicted lineup are imputed-vs-real
2. If imputed fraction high AND opp is bottom-tier, replace imputed slots with division-typical-speed phantoms (from your existing `_load_8u_div_pcts()`-equivalent built for the broader bands)
3. Top divisions: leave alone (they already calibrate near-zero in our control)

You'll need division-specific percentile-time data for 9-10, 11-12, 13-14 — same shape as your 8U params.

## Estimated impact

If the fix works for the other bands proportional to how it worked for 8U:
- Current D17 residual: **+14.33pt**
- 8U fix gave 12pt reduction (about half the 8U over-prediction was burned)
- Each additional band probably yields 2-4pt reduction
- Estimated post-fix D17 bias: **near zero**, possibly slightly negative

## Bonus finding: prior reports understated production performance

My multi-year per-division batch (`/tmp/batch_per_div_multi_year.py`) doesn't call `_hybrid_fill_opp_8u`, so it measures the BASELINE without your fix. The numbers I reported earlier (D17 mean +21pt) are pre-your-fix. Production users actually see ~+14pt bias because your fix IS firing in `_run_and_cache`. Any future batches comparing should call `_hybrid_fill_opp_8u` to match production.

## Validation methodology (replication recipe)

```python
# Set up
d17_meets = [...]  # gather all D17 W1 meets across years
results_with    = []
results_without = []
for (year, week, team, opp, actual, events) in d17_meets:
    mp = build_profile(team, year, week)
    op = build_profile(opp, year, week)
    mlin = pure_greedy(mp, events)
    olin = pure_greedy(op, events)

    # WITHOUT fix
    pred_without = score(mlin, olin, mp, op, events) + relay_pts(mp, op)
    results_without.append(pred_without - actual)

    # WITH fix
    olin_fixed, op_fixed = A._hybrid_fill_opp_8u(opp, year, olin, op, events)
    pred_with = score(mlin, olin_fixed, mp, op_fixed, events) + relay_pts(mp, op_fixed)
    results_with.append(pred_with - actual)

# Compare distributions
```

After your multi-band extension lands, run this same recipe with your new code and compare the deltas. If the per-band breakdown shows the new fix reducing 9-10, 11-12, 13-14 predicted points (not just 8U), you've done the right thing.

## Files for context

- `/tmp/test_d17_hypotheses.py` — the empirical test that produced these numbers
- `/tmp/batch_per_div_multi_year.py` — the multi-year per-division bias batch
- `improvements.md` — original tracking of these issues (the +14 residual you flagged corresponds to improvements.md issue #1 residual)

---

## ADDENDUM (2026-06-04) — caveats the other agent raised after reading this

After reading this, the other agent flagged three points that meaningfully reshape the recommendation. Documented here so the next person doesn't re-walk the same path:

### 1. Pure_greedy ≠ production, so the +14 magnitude is methodology-specific

This test uses pure_greedy as the picker, not the production pipeline (`strategy_robust` + swim-up polish + within-band polish + MC). The DIRECTION of the finding (D17 over-predicts in older bands too) is probably real, but the +14 SIZE will not match production. Use it to motivate the question, not to spec the fix.

### 2. 8U is structurally special; older bands give diminishing returns

The 8U band is uniquely fixable because **the entire band turns over every year** — last year's 8U all aged into 9-10. So opp's 8U profile is pure rookies / pure imputation, and the phantom-fill has huge leverage (−12pt). The older bands DON'T behave this way — 9-10/11-12/13-14 retain real returners (last year's 8U is this year's 9-10, etc.), so those profiles carry real data and have far fewer imputed slots to fill.

Per the per-band numbers in this writeup, the over-prediction collapses from −12pt (8U) to roughly +2–4pt each for older bands. So extending the fix means **3× the engineering work (per-division percentile + fill_n + tier-offset tables for each band)** for diminishing per-band returns, AND overfitting risk on n≈18 obs per division.

### 3. Missing big-picture context: production has league-wide +2–4 over-prediction in EVERY band

This test isolates the DELTA between D17 and D5 (bottom-vs-elite increment). What it misses is that production over-predicts +2 to +4 points in every band, every division, every week. The structural bottom-tier residual is the INCREMENT on top of this league-wide baseline. A bottom-tier-only fix would only address the increment — not the systematic part hitting every team.

### Revised recommendation

**Wait for tonight's 2am production run** (real methodology — strategy_robust + polish + MC + already-shipped hybrid_fill_opp_8u) before deciding whether to build the multi-band extension. That will give actual per-band/per-division D17 numbers under production conditions, with much larger sample. If those still show meaningful older-band over-prediction at D15–D17 specifically, the extension is justified. If the residual is dominated by the league-wide +2–4 baseline, build a flat league-wide calibration layer instead — cheaper and addresses everyone, not just the bottom tier.

Higher-value targets in the meantime:
- **W1 source-selection bug** producing ±200 blowouts (dwarfs everything in the headline)
- **Systematic league-wide +2–4/band over-prediction** (affects all teams, not just D17)

