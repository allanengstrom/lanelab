# Baseline Stats — Pre-Calibration (2026-06-09)

The raw, as-measured numbers from the overnight stats run (488 sides, 2025 W1–W5
full-league backtest) plus the SHBR real-ladder test — **before any calibration
experiments**. This is what production code (`eb6d461`) produces today. All the
knobs explored afterward (us_scale, per-week/division scales, IPF, variance,
freshness, opponent age-up, presence-MC, combos) were offline only and changed
none of these numbers. Companion docs: `OVERNIGHT_REPORT.md` (raw report),
`CALIBRATION_INVESTIGATION.md` (what was tried and what to do).

## 1. Score accuracy by week (recommended lineup vs truth)

| wk | bias | MAE | median AE | blowouts | n |
|---|---|---|---|---|---|
| W1 | −2.86 | 30.97 | 22.7 | 3 | 98 |
| W2 | +10.60 | 22.78 | 17.3 | 2 | 98 |
| W3 | +11.07 | 21.08 | 17.2 | 2 | 96 |
| W4 | +11.37 | 22.56 | 14.9 | 2 | 96 |
| W5 | +11.68 | 19.55 | 16.9 | 2 | 105 |
| **ALL** | **+8.40** | **23.35** | 17.3 | 11 | 493 |

## 2. The decomposition (calibration vs value-add)

pred_actual = the coach's ACTUAL lineup scored by our model vs the predicted
opponent. calibration = pred_actual − truth (pure model accuracy);
value-add = pred − pred_actual (optimizer's in-model claimed improvement);
recommended = calibration + value-add (identity).

| wk | calibration bias | recommended bias | value-add |
|---|---|---|---|
| W1 | −18.09 (MAE 29.3) | −2.86 | +15.2 |
| W2 | −15.36 (MAE 25.0) | +10.60 | +26.0 |
| W3 | −15.89 (MAE 21.8) | +11.07 | +27.0 |
| W4 | −15.07 (MAE 19.9) | +11.37 | +26.4 |
| W5 | −11.25 (MAE 16.6) | +11.68 | +22.9 |
| **ALL** | **−15.07 (MAE 22.5)** | **+8.40** | **+23.5** |

Real value-add from beat-coach (actual times): **+6.95** — the in-model +23.5 is
winner's-curse inflated ~3.4×. The healthy-looking +8.4 recommended bias is
−15 + 23 cancelling. Correct targets: calibration → 0, value-add → +7,
recommended → +7 (earned, not lucky).

## 3. By division (recommended bias)

| div | bias | MAE | blowouts | n |
|---|---|---|---|---|
| 1 | +2.74 | 26.27 | 0 | 30 |
| 2 | −0.17 | 18.84 | 0 | 24 |
| 3 | +2.73 | 17.03 | 0 | 30 |
| 4 | +4.43 | 16.47 | 0 | 30 |
| 5 | +2.00 | 21.08 | 0 | 30 |
| 6 | +7.04 | 19.91 | 0 | 30 |
| 7 | +5.34 | 22.17 | 0 | 30 |
| 8 | +9.00 | 16.08 | 0 | 30 |
| 9 | +4.38 | 15.18 | 0 | 30 |
| 10 | +7.14 | 17.85 | 0 | 30 |
| 11 | +7.59 | 15.52 | 0 | 30 |
| 12 | +8.07 | 22.02 | 0 | 30 |
| 13 | +11.68 | 18.32 | 0 | 24 |
| 14 | +7.77 | 16.77 | 0 | 30 |
| 15 | +14.34 | 25.45 | 0 | 20 |
| **16** | **+19.91** | **54.58** | **8** | 34 |
| **17** | **+27.50** | **47.19** | **3** | 31 |

Calibration bias by division: −9 to −24 (worst: div 11 −21.4, div 16 −23.8,
div 17 −23.9). By opponent strength: **−2.7 vs strong opponents (scored ≥210),
−34.3 vs weak (<190)** — the error is concentrated where we're the favorite.

## 4. Per-band points (pred − actual)

| band | bias | MAE |
|---|---|---|
| 8U | **−0.74** | 6.85 |
| 9-10 | +2.86 | 6.29 |
| 11-12 | +2.62 | 6.04 |
| 13-14 | +4.42 | 7.40 |
| 15-18 | +4.71 | 7.92 |

Band × week bias: W1 is the outlier (8U −10.6, 9-10 +7.7, 11-12 +6.4,
13-14 +10.7, 15-18 +12.3); W2–W5 all bands sit between +0.8 and +3.2.

## 5. Margin

| wk | pred margin mean | actual | bias | MAE | amp(std) |
|---|---|---|---|---|---|
| W1 | +50.4 | +0.0 | +50.4 | 72.4 | 0.77 |
| W2 | +24.8 | +0.0 | +24.8 | 47.0 | 0.80 |
| W3 | +23.4 | +0.0 | +23.4 | 42.5 | 0.94 |
| W4 | +23.1 | +0.0 | +23.1 | 44.9 | 0.84 |
| W5 | +23.6 | +0.6 | +23.0 | 39.1 | 1.00 |

## 6. Win probability

- **W1**: refit Φ(−0.2136 + 0.00371·margin) ≈ shipped (−0.2262/0.00404).
  Brier 0.2412 vs 0.2411 — shipped constants fine; W1 is near coin-flip.
- **W2–5**: refit on production margins: actual ≈ **0.782**·pred_margin,
  residual σ = **58.1** (shipped: k=0.455, σ=64 — fit on greedy margins).
  Brier: refit 0.1661 vs shipped 0.1828. Per-week k: W2 0.896, W3 0.753,
  W4 0.823, W5 0.650. → Open item: adopt k≈0.78.

## 7. v5 predictor & relay

- v5 crash/fallback rate: **0.0%** every week (n=98/98/96/96/105).
- Jaccard (predicted vs actual opponent lineup): W1 0.192 → W2 0.453 →
  W3 0.497 → W4 0.534 → W5 0.558.
- Relay: pred 30.0 vs implied actual 29.4–29.6 → bias **+0.4 to +0.6** every week.

## 8. SHBR real-ladder production test (baseline, no fixes)

Real uploaded weekly ladders (`time_trials/shbr_weekly/`), our side fresh,
all 5 opponents stale (has_current=False):

| wk | opponent | truth | WITH-ladder err | WITHOUT-ladder err |
|---|---|---|---|---|
| W1 | South Run | 232 | +17.3 | −31.9 |
| W2 | Hunter Mill | 265 | +3.2 | −3.1 |
| W3 | Canterbury Woods | 210 | +15.3 | −1.4 |
| W4 | Waynewood | 227 | +18.3 | +6.0 |
| W5 | Dunn Loring | 241 | −13.2 | −22.3 |
| | | **mean** | **+8.2 (MAE 13.4)** | (MAE 13.5) |

With fresh ladder the bias flips to over-prediction (stale opponent under-modeled
+ full-lineup assumption). The ladder-upload workflow itself is validated
(MAE 13.4 vs 13.5, and hugely better at W1).
