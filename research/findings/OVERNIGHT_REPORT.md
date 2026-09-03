# Overnight Measurement Report

sides=493  meets≈246

## 1. Score accuracy

### By week
  W1             bias   -2.86  MAE  30.97  med  22.7  blow  3  cBias  -7.51  n=98
  W2             bias  +10.60  MAE  22.78  med  17.3  blow  2  cBias +10.30  n=98
  W3             bias  +11.07  MAE  21.08  med  17.2  blow  2  cBias +10.66  n=96
  W4             bias  +11.37  MAE  22.56  med  14.9  blow  2  cBias  +8.60  n=96
  W5             bias  +11.68  MAE  19.55  med  16.9  blow  2  cBias +11.02  n=105
  ALL            bias   +8.40  MAE  23.35  med  17.3  blow 11  cBias  +6.68  n=493

### Calibration vs optimizer value-add  (pred=our optimized lineup; pred_actual=coach's ACTUAL lineup scored by our model)
  Decomposes 'recommended bias' into clean prediction-calibration + in-model value-add.
  W1: CALIBRATION bias -18.09 (MAE  29.3)  |  recommended bias  -2.86  |  optimizer value-add +15.2  n=98
  W2: CALIBRATION bias -15.36 (MAE  25.0)  |  recommended bias +10.60  |  optimizer value-add +26.0  n=98
  W3: CALIBRATION bias -15.89 (MAE  21.8)  |  recommended bias +11.07  |  optimizer value-add +27.0  n=96
  W4: CALIBRATION bias -15.07 (MAE  19.9)  |  recommended bias +11.37  |  optimizer value-add +26.4  n=96
  W5: CALIBRATION bias -11.25 (MAE  16.6)  |  recommended bias +11.68  |  optimizer value-add +22.9  n=105
  ALL: CALIBRATION bias -15.07 (MAE  22.5)  |  value-add +23.5

### By division (us_div)
  div 1          bias   +2.74  MAE  26.27  med  18.7  blow  0  cBias  +2.74  n=30
  div 2          bias   -0.17  MAE  18.84  med  16.2  blow  0  cBias  -0.17  n=24
  div 3          bias   +2.73  MAE  17.03  med  12.7  blow  0  cBias  +2.73  n=30
  div 4          bias   +4.43  MAE  16.47  med  10.6  blow  0  cBias  +4.43  n=30
  div 5          bias   +2.00  MAE  21.08  med  19.5  blow  0  cBias  +2.00  n=30
  div 6          bias   +7.04  MAE  19.91  med  13.6  blow  0  cBias  +7.04  n=30
  div 7          bias   +5.34  MAE  22.17  med  19.1  blow  0  cBias  +5.34  n=30
  div 8          bias   +9.00  MAE  16.08  med  16.0  blow  0  cBias  +9.00  n=30
  div 9          bias   +4.38  MAE  15.18  med  13.8  blow  0  cBias  +4.38  n=30
  div 10         bias   +7.14  MAE  17.85  med  14.7  blow  0  cBias  +7.14  n=30
  div 11         bias   +7.59  MAE  15.52  med  10.5  blow  0  cBias  +7.59  n=30
  div 12         bias   +8.07  MAE  22.02  med  18.7  blow  0  cBias  +8.07  n=30
  div 13         bias  +11.68  MAE  18.32  med  21.2  blow  0  cBias +11.68  n=24
  div 14         bias   +7.77  MAE  16.77  med  14.6  blow  0  cBias  +7.77  n=30
  div 15         bias  +14.34  MAE  25.45  med  25.3  blow  0  cBias +14.34  n=20
  div 16         bias  +19.91  MAE  54.58  med  32.9  blow  8  cBias  +5.47  n=34
  div 17         bias  +27.50  MAE  47.19  med  35.5  blow  3  cBias +16.73  n=31

### Per-week × division (bias only)
  div |  W1    W2    W3    W4    W5  
    1 | -18.4  +4.0  +8.5  +8.3 +11.2
    2 | -15.6  +3.1  +3.1  +6.5  +6.4
    3 | -16.6  +6.2  +6.9  +7.1 +10.1
    4 | -15.0 +10.6  +9.0  +6.7 +10.8
    5 | -15.2  +6.6  +5.7  +6.9  +6.0
    6 |  -1.1  +6.2  +8.9 +11.5  +9.7
    7 |  -2.6  +6.1  +6.6  +8.5  +8.1
    8 |  -9.1 +21.2 +11.5  +9.7 +11.6
    9 |  -5.8  +5.7  +7.7  +7.4  +7.0
   10 |  +6.6  +6.9  +5.3  +8.0  +8.9
   11 | -10.2 +12.5 +14.8 +10.3 +10.6
   12 |  -3.3 +11.1 +10.6 +10.4 +11.6
   13 |  +4.9 +17.1 +12.0 +12.3 +10.2
   14 |  -1.7 +10.3 +14.3  +9.9  +6.0
   15 |  +2.4 +22.5 +15.3 +15.6 +15.8
   16 | +17.4 +19.4 +22.1 +25.2 +17.2
   17 | +38.8 +12.3 +24.9 +29.1 +31.7

## 2. Per-band points (pred − actual)

### By band (all weeks)
  8U             bias   -0.74  MAE   6.85  med   4.7  blow  0  cBias  -0.74  n=493
  9-10           bias   +2.86  MAE   6.29  med   4.5  blow  0  cBias  +2.86  n=493
  11-12          bias   +2.62  MAE   6.04  med   4.4  blow  0  cBias  +2.62  n=493
  13-14          bias   +4.42  MAE   7.40  med   5.5  blow  0  cBias  +4.42  n=493
  15-18          bias   +4.71  MAE   7.92  med   5.6  blow  0  cBias  +4.71  n=493

### 8U by division
  div 1 8U       bias   -2.29  MAE   6.52  med   4.6  blow  0  cBias  -2.29  n=30
  div 2 8U       bias   -2.37  MAE   6.05  med   4.6  blow  0  cBias  -2.37  n=24
  div 3 8U       bias   -2.29  MAE   5.92  med   3.4  blow  0  cBias  -2.29  n=30
  div 4 8U       bias   -2.53  MAE   7.24  med   3.9  blow  0  cBias  -2.53  n=30
  div 5 8U       bias   -1.45  MAE   6.23  med   4.2  blow  0  cBias  -1.45  n=30
  div 6 8U       bias   -1.14  MAE   4.55  med   3.5  blow  0  cBias  -1.14  n=30
  div 7 8U       bias   -1.17  MAE   7.13  med   5.5  blow  0  cBias  -1.17  n=30
  div 8 8U       bias   -0.90  MAE   5.87  med   4.0  blow  0  cBias  -0.90  n=30
  div 9 8U       bias   -1.22  MAE   5.85  med   4.3  blow  0  cBias  -1.22  n=30
  div 10 8U      bias   -0.83  MAE   6.02  med   4.3  blow  0  cBias  -0.83  n=30
  div 11 8U      bias   -0.05  MAE   6.35  med   4.4  blow  0  cBias  -0.05  n=30
  div 12 8U      bias   +0.12  MAE   7.20  med   4.3  blow  0  cBias  +0.12  n=30
  div 13 8U      bias   -0.96  MAE   5.30  med   3.6  blow  0  cBias  -0.96  n=24
  div 14 8U      bias   -0.35  MAE   6.07  med   5.5  blow  0  cBias  -0.35  n=30
  div 15 8U      bias   +0.19  MAE   6.77  med   4.9  blow  0  cBias  +0.19  n=20
  div 16 8U      bias   +3.05  MAE  11.70  med   7.0  blow  0  cBias  +3.05  n=34
  div 17 8U      bias   +0.95  MAE  10.34  med   5.1  blow  0  cBias  +0.95  n=31

### Band × week (bias)
  band   |  W1    W2    W3    W4    W5  
  8U     | -10.6  +1.6  +1.9  +1.8  +1.6
  9-10   |  +7.7  +1.5  +1.6  +1.8  +1.8
  11-12  |  +6.4  +0.8  +1.7  +1.8  +2.3
  13-14  | +10.7  +3.0  +2.9  +2.6  +2.9
  15-18  | +12.3  +3.2  +2.7  +2.8  +2.6

## 3. Margin (pred margin vs actual margin)
  W1: pred_margin mean  +50.4  actual   +0.0  bias  +50.4  MAE  72.4  amp(std) 0.77  n=98
  W2: pred_margin mean  +24.8  actual   +0.0  bias  +24.8  MAE  47.0  amp(std) 0.80  n=98
  W3: pred_margin mean  +23.4  actual   +0.0  bias  +23.4  MAE  42.5  amp(std) 0.94  n=96
  W4: pred_margin mean  +23.1  actual   +0.0  bias  +23.1  MAE  44.9  amp(std) 0.84  n=96
  W5: pred_margin mean  +23.6  actual   +0.6  bias  +23.0  MAE  39.1  amp(std) 1.00  n=105

## 4. Win probability
  W1 refit: P(win)=Φ(-0.2136+0.00371·margin)  [shipped WINP_W1_B0/B1=-0.2262/0.00404]
  W1 refit                   winp-bias -0.000  Brier 0.2412  n=98
  W1 shipped                 winp-bias +0.001  Brier 0.2411  n=98
  flat 50%                   winp-bias +0.010  Brier 0.2500  n=98

  W2-5 refit on production margins: actual≈0.782·pred_margin, residual σ=58.1
  [shipped: k=0.455, σ=64 — fit on greedy margins, the miscalibration issue]
  W2-5 refit (k=0.782,σ=58)  winp-bias +0.089  Brier 0.1661  n=395
  W2-5 shipped (0.455/64)    winp-bias +0.059  Brier 0.1828  n=395
  flat 50%                   winp-bias +0.001  Brier 0.2500  n=395
  per-week k:
    W2: k=0.896  (n=98)
    W3: k=0.753  (n=96)
    W4: k=0.823  (n=96)
    W5: k=0.650  (n=105)

## 5. v5 predictor
  W1: v5 crash/fallback rate  0.0%  (n=98)
  W2: v5 crash/fallback rate  0.0%  (n=98)
  W3: v5 crash/fallback rate  0.0%  (n=96)
  W4: v5 crash/fallback rate  0.0%  (n=96)
  W5: v5 crash/fallback rate  0.0%  (n=105)
  Jaccard (opp predicted vs actual lineup), by week:
    W1: 0.192  (n=98)
    W2: 0.453  (n=98)
    W3: 0.497  (n=96)
    W4: 0.534  (n=96)
    W5: 0.558  (n=105)

## 6. Relay (pred vs implied actual = truth − Σ band_actual)
  W1: relay pred  30.0  implied-actual  29.5  bias  +0.5
  W2: relay pred  30.0  implied-actual  29.6  bias  +0.4
  W3: relay pred  30.0  implied-actual  29.6  bias  +0.4
  W4: relay pred  30.0  implied-actual  29.6  bias  +0.4
  W5: relay pred  30.0  implied-actual  29.4  bias  +0.6
