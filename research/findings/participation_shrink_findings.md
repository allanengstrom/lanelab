# Participation-aware value-add shrink — prototype findings (2026-06-09)

Basis: `overnight_cache.jsonl` (STALE-SEED, 488 deduped sides, 101 teams, 2025 W1–W5).
Script: `participation_shrink_proto.py` (stdlib + numpy; re-run with `python3 participation_shrink_proto.py`).
The league-wide calibration offset (~−15) is expected on this basis and is NOT the target;
the criterion is FLATNESS of (pred_actual + disp) − truth across participation buckets.
Buckets use the 2025 actual season_rate (descriptive); all formulas use the leakage-free
prior `participation_prior_2025.json` (so production-eligible).

## 1. The monotone relationship is confirmed

| p bucket (2025) | n | mean va | rec_err (pred−truth) | cal (pred_actual−truth) |
|---|---|---|---|---|
| <0.65 | 20 | **81.8** | **+87.3** | +5.4 |
| 0.65–0.80 | 52 | 28.4 | +8.4 | −20.0 |
| 0.80–0.90 | 117 | 23.3 | +4.4 | −18.9 |
| ≥0.90 | 299 | 18.8 | +4.6 | −14.1 |
| div 1–13 | 378 | 19.5 | +5.5 | −14.0 |
| div 14–17 | 110 | 37.0 | +18.0 | −18.9 |
| LEAGUE | 488 | 23.4 | +8.4 | −15.1 |

va is strictly monotone decreasing in participation; the rec_err blowup is entirely the
va term (calibration is roughly bucket-flat, even slightly positive at <0.65). The div
14–17 excess (+18 vs +5.5) is the same effect.

## 2. Formulas (fit on all teams, anchored to league mean disp = +7)

Fit: least-squares of va·k(p) against the +7 beat-coach target, then rescaled so league
mean disp = 7.00 exactly. Linear k is clipped at 0.

| formula | fitted constants |
|---|---|
| global | disp = 0.299·va |
| linear | disp = va·max(0, 0.323 + 0.598·(p − 0.894)) |
| power | disp = va·0.436·p^2.75 |
| **hinge** | **disp = va·0.425·max(0, (p − 0.525)/0.475)** |

Pure value-add term, mean disp by bucket (target = +7 flat):

| bucket | global | linear | power | hinge |
|---|---|---|---|---|
| <0.65 | 24.4 | 10.7 | 8.5 | **6.4** |
| 0.65–0.80 | 8.5 | 7.1 | 6.2 | 6.3 |
| 0.80–0.90 | 6.9 | 7.2 | 7.0 | 7.2 |
| ≥0.90 | 5.6 | 6.7 | 7.1 | 7.1 |

Displayed-pred residual (pred_actual + disp − truth) by bucket:

| bucket | raw pred | cal only (floor) | global | linear | power | hinge |
|---|---|---|---|---|---|---|
| <0.65 | +87.3 | +5.4 | +29.9 | +16.1 | +13.9 | **+11.8** |
| 0.65–0.80 | +8.4 | −20.0 | −11.5 | −12.8 | −13.8 | −13.6 |
| 0.80–0.90 | +4.4 | −18.9 | −11.9 | −11.7 | −11.9 | −11.7 |
| ≥0.90 | +4.6 | −14.1 | −8.5 | −7.5 | −7.1 | −7.0 |
| **flatness (max−min)** | 82.9 | 25.4 | 41.8 | 29.0 | 27.7 | **25.5** |
| slope vs p | | | −41.5 | −18.4 | −14.0 | −11.7 |

Hinge reaches the calibration floor (25.5 vs 25.4) — the bucket-dependent va component is
fully removed; what remains is the calibration term's own (small, stale-basis) bucket
variation. Div groups: hinge leaves a 1–13 vs 14–17 gap of −7.0 vs −11.9, exactly the
cal-only gap (−14.0 vs −18.9), i.e. the va term no longer differs by division group.
(Global *looks* group-flat, −8.1 vs −7.9, but only because <0.65 inflation cancels the
negative calibration — masking, not fixing.)

League MAE of displayed pred vs truth: raw 23.41 → global 20.60 → linear 20.09 →
power 20.00 → **hinge 19.96**.

## 3. Tails

- **Annandale** (prior 0.690, p25 0.613): rec_err +152…+203/meet → hinge displayed resid
  +36…+68 (mean +45; its own calibration is +23, so the residual va error is ~+22).
  Effective multiplier: global ×0.30, hinge ×0.148, power ×0.157 — matches the
  "Annandale needs ~×0.1" expectation in §8.
- **Edsall Park** (p25 0.432): +77.9 → +8.5 (hinge). **Pinewood Lake** (p25 0.245):
  +54.5 → +10.4 (its prior falls below p0 → disp=0; residual is its own +10 calibration).
- Already-negative div 16–17 teams (Brandywine −25, Long Branch −19, Herndon −21) get
  1–3 pts more negative under hinge vs global — that is the stale-basis calibration
  showing through, not a new va error (cal-only is more negative still).
- **Healthy teams (prior ≥ 0.90, 303 sides)**: mean disp global 5.77 vs hinge 7.33;
  mean |per-side change vs global| = 1.6 pts on a ~390-pt scale. Barely changed, as required.

## 4. Out-of-sample honesty (team-level random half, seed 42)

The seed-42 split put **all 10 p<0.8-heavy teams (incl. all <0.65) in the test half** —
a maximally adversarial draw.

- Fit on the half WITHOUT low-p teams → held-out flatness: global 45.9, linear 39.5,
  power 37.9, hinge 36.0. The participation forms still beat global on the unseen
  low-p teams even when fitted blind to them, but the shape constants degenerate
  (hinge p0→0, power γ→0.75): the curvature is identified by the low-p tail.
- Swapped direction (fit on the half WITH low-p teams) recovers constants close to the
  full fit (hinge p0=0.55 c=0.437; power γ=3.0; linear b=0.56), in-sample flatness
  25–30 vs global 41.9, and the held-out healthy half is barely perturbed (bucket
  means within ~4 pts, MAE 21.3 vs global 21.9).

Verdict: the FORM is validated out-of-sample in both directions; the CONSTANTS must be
fit on the full league because ~10 teams carry the identification. With y-o-y r=0.964
on participation, that is acceptable.

## 5. Recommendation

**disp = va × 0.425 × max(0, (p − 0.525)/0.475)**, p = leakage-free participation prior
(`participation_prior_2025.json`). Theory-defensible: real value-add scales with the
fraction of the optimizer's marginal lane fills the coach can actually field, with a
floor p0≈0.53 below which the optimizer's extra lanes are pure fantasy. Runner-up:
power form 0.436·p^2.75 (nearly identical metrics, no dead zone below p0, slightly
smoother — a fine substitute if a hard zero at very low p is unwanted).

## Caveats

1. Stale-seed basis: everything here is the va TERM only; the −15 calibration offset and
   its small bucket variation are out of scope and being re-baselined by
   mock_baseline_eval.py. Re-fit the anchor (the +7 target and the c scale) on the
   production basis — §9 partial signal suggests production va inflation is larger.
2. p0 and γ are identified by ~10 teams / ~70 sides; constants are stable only when
   low-p teams are in the fit. Don't fit on subsets.
3. The +7 real-value-add anchor is itself a league-wide SHBR/beat-coach estimate; if
   real value-add also scales with p (plausible), the low-p displayed values (~+6) are
   still generous.
4. <0.65 bucket residual stays ~+12 (vs +5.4 cal floor): a hard 7-point target cannot
   fully remove Annandale W5-type outliers; gating the optimizer pool by participation
   (idea (a) in §8) is the complementary fix.
