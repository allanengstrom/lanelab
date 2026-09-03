# Minimum-Detectable-Bias (MDB) Analysis — Production-Basis Baseline

Data: `mock_baseline_results.jsonl`, deduped on (week, meet_id, side): **488 sides / 244 meets** (weeks 1-5). Correction applied before all tests: per-week value-add anchor `c_w = 7.0 / mean_w(pred - pred_actual)`, corrected error `ce = pred_actual + c_w*va - truth`. c_w by week: W1=0.1291, W2=0.1730, W3=0.1999, W4=0.2183, W5=0.2584. Seed 42, B=10,000 clustered bootstrap (meets resampled whole).

## Clustering

Both sides of every meet are in the same division: True. Intra-meet correlation of corrected errors (ICC via doubled-pair Pearson, 244 meets): **r = -0.354** (raw err: r = -0.325). The correlation is NEGATIVE — the two sides' errors partially offset (point-conservation within a meet) — so the design effect for 2-side clusters is 1 + r = 0.646 < 1: clustered SEs are ~0.804x the iid SEs at levels where both sides of a meet share the slice (league/week/division/div-x-week). Per-division r ranges -0.83 to +0.61; divisions with positive r (D8, D11, D14) have clustering widen their MDB instead.

Method note: the cluster bootstrap is only trusted where a slice has >= 10 meets. Division-x-week cells have only 2-3 meets, where the recentered bootstrap null collapses and produces absurdly small MDBs / spurious rejections; for those cells the primary inference is the cluster-robust t-test on meet means (df = k-1), which is valid for either correlation sign. Per spec, c_w is estimated once on the full week and held fixed inside the bootstrap, so the MDBs exclude correction-estimation noise (a small extra term at the week level).

## 1. MDB table

MDB(analytic, iid) = t.975 * sd/sqrt(n); MDB(80% power) = (t.975 + t.80) * sd/sqrt(n); MDB(boot) = 95th pct of |null mean| from the clustered bootstrap of recentered errors (meets resampled whole); MDB(CR) = cluster-robust analytic, t.975(k-1) * sd(meet means)/sqrt(k). **Primary** = boot where k >= 10 meets, else CR.

| Level | Slice | n sides | k meets | bias (ce) | sd | MDB analytic (iid) | MDB 80% power (iid) | MDB cluster-boot | MDB CR | primary p |
|---|---|---|---|---|---|---|---|---|---|---|
| league | ALL | 488 | 244 | +0.09 | 23.9 | 2.12 | 3.03 | 1.72 | 1.71 | 0.9179 |
| week | W1 | 98 | 49 | +7.82 | 31.6 | 6.33 | 9.03 | 4.77 | 4.99 | 0.0023 |
| week | W2 | 98 | 49 | +5.18 | 25.3 | 5.08 | 7.24 | 4.76 | 5.07 | 0.0348 |
| week | W3 | 96 | 48 | -3.42 | 20.6 | 4.17 | 5.95 | 2.92 | 3.03 | 0.0214 |
| week | W4 | 96 | 48 | -6.20 | 20.8 | 4.21 | 6.00 | 1.72 | 1.77 | 0.0001 |
| week | W5 | 100 | 50 | -3.06 | 15.2 | 3.03 | 4.31 | 1.41 | 1.47 | 0.0001 |
| division | D1 | 30 | 15 | +8.66 | 29.0 | 10.82 | 15.34 | 4.16 | 4.72 | 0.0001 |
| division | D2 | 24 | 12 | +4.98 | 22.1 | 9.35 | 13.22 | 7.37 | 8.63 | 0.1860 |
| division | D3 | 30 | 15 | +4.66 | 19.6 | 7.31 | 10.37 | 5.61 | 6.34 | 0.1034 |
| division | D4 | 30 | 15 | -0.76 | 20.2 | 7.53 | 10.67 | 3.26 | 3.69 | 0.6574 |
| division | D5 | 30 | 15 | +1.10 | 20.2 | 7.53 | 10.67 | 3.18 | 3.60 | 0.5028 |
| division | D6 | 30 | 15 | +1.32 | 23.3 | 8.69 | 12.32 | 5.88 | 6.61 | 0.6691 |
| division | D7 | 30 | 15 | +1.01 | 23.3 | 8.71 | 12.35 | 4.59 | 5.19 | 0.6724 |
| division | D8 | 30 | 15 | -1.47 | 24.3 | 9.07 | 12.86 | 10.67 | 12.27 | 0.7899 |
| division | D9 | 30 | 15 | +1.29 | 18.3 | 6.82 | 9.67 | 5.86 | 6.78 | 0.6715 |
| division | D10 | 30 | 15 | +1.88 | 23.5 | 8.77 | 12.43 | 6.70 | 7.56 | 0.5911 |
| division | D11 | 30 | 15 | -6.14 | 22.0 | 8.23 | 11.67 | 8.97 | 10.32 | 0.1560 |
| division | D12 | 30 | 15 | -1.56 | 20.7 | 7.75 | 10.98 | 3.66 | 4.23 | 0.4187 |
| division | D13 | 24 | 12 | +4.20 | 17.9 | 7.56 | 10.70 | 5.58 | 6.65 | 0.1460 |
| division | D14 | 30 | 15 | -5.24 | 26.0 | 9.73 | 13.79 | 10.35 | 11.59 | 0.3092 |
| division | D15 | 20 | 10 | -1.45 | 21.8 | 10.21 | 14.41 | 7.05 | 8.67 | 0.6950 |
| division | D16 | 30 | 15 | -1.64 | 18.3 | 6.84 | 9.70 | 2.80 | 3.23 | 0.2476 |
| division | D17 | 30 | 15 | -8.02 | 42.5 | 15.85 | 22.48 | 9.17 | 10.39 | 0.0898 |
| opp_bucket | <170 | 74 | 74 | -21.44 | 22.5 | 5.20 | 7.41 | 5.09 | 5.20 | 0.0001 |
| opp_bucket | 170-200 | 123 | 122 | -8.30 | 20.2 | 3.60 | 5.14 | 3.58 | 3.62 | 0.0001 |
| opp_bucket | 200-230 | 152 | 104 | +2.07 | 17.7 | 2.83 | 4.04 | 2.64 | 3.22 | 0.1269 |
| opp_bucket | >=230 | 139 | 139 | +16.81 | 21.2 | 3.55 | 5.06 | 3.56 | 3.55 | 0.0001 |
| div_x_week | 85 cells (median / range) | 6 | 3 | median abs bias 5.1 | 19.6 | 21.0 (6.5-68.0) | 28.5 | (invalid, k=2-3) | 15.4 (1.4-164.6) | - |

Clustering matters wherever both sides of a meet share the slice: at the league level the boot/iid-analytic MDB ratio is 0.808 (consistent with sqrt(1+r) = 0.804) — i.e. ignoring clustering OVERSTATES the MDB by ~24% at meet-sharing levels because the negative within-meet correlation cancels noise. For opp-strength buckets the two sides usually land in different buckets, so boot ~= iid analytic there. Division-level boot MDBs agree with the CR analytic ones (k=10-15), so both are usable; div-x-week bootstrap MDBs are NOT (k=2-3) and the CR column is the honest number.

## 2. Slices rejecting H0 (bias = 0) after BH FDR (q = 0.10)

Primary p-values (clustered bootstrap; cluster-robust t for div-x-week), BH within each family.

**week** (5 tests):
- W1: bias = +7.82 (95% CI [+2.71, +12.25]), p = 0.0023, n = 98
- W2: bias = +5.18 (95% CI [-0.19, +9.49]), p = 0.0348, n = 98
- W3: bias = -3.42 (95% CI [-6.53, -0.70]), p = 0.0214, n = 96
- W4: bias = -6.20 (95% CI [-7.97, -4.54]), p = 0.0001, n = 96
- W5: bias = -3.06 (95% CI [-4.46, -1.64]), p = 0.0001, n = 100

**division** (17 tests):
- D1: bias = +8.66 (95% CI [+4.50, +12.83]), p = 0.0001, n = 30

**div_x_week** (85 tests): no survivors.

**opp_bucket** (4 tests):
- <170: bias = -21.44 (95% CI [-26.76, -16.60]), p = 0.0001, n = 74
- 170-200: bias = -8.30 (95% CI [-11.95, -4.82]), p = 0.0001, n = 123
- >=230: bias = +16.81 (95% CI [+13.28, +20.39]), p = 0.0001, n = 139

## 3. Opponent-strength staircase (trend test)

OLS of ce on centered opp_truth, clustered bootstrap on the slope:

- slope = **+0.3323** points of error per opponent point = **+3.32 per 10 opponent points**
- 95% CI [+0.2802, +0.3890], p = 0.0001 (SIGNIFICANT at alpha=.05)

Across the observed opp_truth range (38-368), the fitted trend spans +109.6 points of bias end-to-end.

## 4. Recommended calibration targets

A measured |bias| below the slice's MDB is statistically indistinguishable from perfect calibration at that sample size. Using the primary (clustered) MDBs:

- **League** (n=488): |bias| <= **1.7** pts is noise; only chase league bias beyond ~3.0 pts if you want 80% power to confirm a fix.
- **Week** (n~98): |bias| <= **3** pts (median MDB; range 1.4-4.8).
- **Division** (n~29): |bias| <= **6** pts (median; range 2.8-10.7).
- **Opp-strength bucket**: |bias| <= **4** pts (median).
- **Division x week cell** (n~6, k=2-3 meets): cluster-robust MDB is ~**15** pts (median; up to 165). 66/85 cells in the 17x5 heatmap sit below their own MDB — those cells should NOT be individually chased; any cell-level tuning would be fitting noise. Only the FDR survivors listed in section 2 (if any) carry real signal.

