# Overnight spread/bias sweep — paired on 68-side stratified sample (wks 2&4, all 17 div)

Goal: get raw backtest bias (pred-truth) to an acceptable level. err>0 = over-prediction.

## Reference (current runs, on these 68 sides)
- **ageon 5% (CURRENT DEFAULT)**: n=68, bias **+35.67**, MAE **39.62**
- **ageoff 5%**: n=68, bias **+29.06**, MAE **36.09**

## Configs

**cv2_ageon**  (n=68)  bias **+37.46**  MAE **41.58**  blowups(|err|>=100) 1
  vs ageon(5%): Δbias +1.78 (ref +35.7), ΔMAE +1.96  [paired n=68]
  vs ageoff(5%): Δbias +8.39 (ref +29.1), ΔMAE +5.49  [paired n=68]

**presence_ageon**  (n=68)  bias **+44.19**  MAE **46.35**  blowups(|err|>=100) 1
  vs ageon(5%): Δbias +8.52 (ref +35.7), ΔMAE +6.73  [paired n=68]
  vs ageoff(5%): Δbias +15.13 (ref +29.1), ΔMAE +10.27  [paired n=68]

## KEY FINDING (interim, ~23:45) — aggregate bias is a CALIBRATION lever, not a model knob
- **Spread 2% (cv2_ageon)**: raw bias +35.7 → +37.5 (Δ+1.8 WORSE), MAE +2.0 worse. Tightening spread
  raises a favorite's predicted total (fewer phantom losses). It FIXES per-event overconfidence
  (50-free 42%→9%) but is NOT an aggregate-bias fix. Needs win-prob/total calib REFIT to ship (margin basis shifts).
- **Opponent-presence (presence_ageon)**: raw bias +35.7 → +44.2 (Δ+8.5 WORSE). In this backtest OPP_PRESENCE
  models the OPPONENT no-showing → our swimmers face less competition → our total goes UP. Wrong direction
  for our-side over-prediction. Confirmed across weak & strong opponents.
- **Participation value-add shrink (offline, sanctioned, full 488)**: raw +37.5/MAE 39.0 → **+13.0/MAE 20.7**
  with STALE constants. Flattens the participation-dependent excess (<0.65 bucket → −0.4). Residual +16.8 on
  healthy teams = the uniform offset the shipped theory-2 reanchor removes. **This is the bias lever.**

**Direction:** keep the spread fix for per-event honesty (+refit calib); drive aggregate bias via the
calibration layer (va-shrink, constants refit on this basis, + reanchor). Model knobs confirmed not to help.

**allfix_ageoff**  (n=68)  bias **+49.72**  MAE **50.73**  blowups(|err|>=100) 6
  vs ageon(5%): Δbias +14.05 (ref +35.7), ΔMAE +11.11  [paired n=68]
  vs ageoff(5%): Δbias +20.66 (ref +29.1), ΔMAE +14.65  [paired n=68]

**compress_ageoff**  (n=68)  bias **+37.46**  MAE **41.22**  blowups(|err|>=100) 1
  vs ageon(5%): Δbias +1.79 (ref +35.7), ΔMAE +1.59  [paired n=68]
  vs ageoff(5%): Δbias +8.40 (ref +29.1), ΔMAE +5.13  [paired n=68]

**cv2_ageoff**  (n=68)  bias **+37.45**  MAE **41.56**  blowups(|err|>=100) 1
  vs ageon(5%): Δbias +1.78 (ref +35.7), ΔMAE +1.94  [paired n=68]
  vs ageoff(5%): Δbias +8.39 (ref +29.1), ΔMAE +5.47  [paired n=68]

---
# FINAL — conclusion & recommendation (sweep complete, 01:17)

## Full results (68-side stratified sample, wks 2&4, all 17 div; paired)
| config | env | bias | MAE | blow |
|---|---|---:|---:|---:|
| ageon 5% (CURRENT DEFAULT) | — | +35.7 | 39.6 | ref |
| ageoff 5% | USE_AGE_CURVE=0 | +29.1 | 36.1 | ref |
| cv2_ageon | SIM_CV_SET=.02 | +37.5 | 41.6 | 1 |
| cv2_ageoff | +age off | +37.5 | 41.6 | 1 |
| compress_ageoff | +relay .4 | +37.5 | 41.2 | 1 |
| presence_ageon | OPP_PRESENCE=1 | +44.2 | 46.4 | 1 |
| allfix_ageoff | presence+cv2+relay.4+EU | +49.7 | 50.7 | 6 |

## Three findings
1. **No simulator knob lowers the raw aggregate bias.** Spread 2% +1.8, relay-tighten +0 more,
   opponent-presence +8.5, kitchen-sink +14. In this mock-ladder backtest the evaluated side is the
   favorite, so tighter/again-modeled fields raise its total. Bias is NOT a model-knob lever.
2. **Aggregate bias is a CALIBRATION lever — and it's already shipped.** The raw +37.5 is the optimizer's
   value-add inflation (pre-calibration). A flat/per-week reanchor (= the shipped theory-2 calibration)
   takes it to ~0 bias / MAE ~20 OUT-OF-SAMPLE (held-out teams). Residual staircase (+34 pts per +100 opp)
   is handled by the div-slope + the (prototype) participation va-shrink. Per display-rule 8, this is exactly
   where bias belongs. The displayed prediction is already de-biased; the backtest +37 is the raw number.
3. **The age curve's +6 raw-bias cost is a SPREAD ARTIFACT.** Paired age-on minus age-off bias gap:
   +6.6 at 5% spread, **+0.0 at 2% spread**. Tightening the spread makes the age curve bias-neutral.

## Recommendation
- **Adopt the spread fix.** It fixes the per-event overconfidence you flagged (13-14 Girls 50-free 42%→9%)
  AND neutralizes the age-curve bias penalty (so the age curve stays on for lineup realism, bias-free).
- **PRE-REQUISITE before default-on:** refit the win-prob (k,σ) and the reanchor on the 2%-spread margin
  basis — the margin distribution shifts, and the docs are explicit those constants must be refit (W1_START_HERE §2.7).
  The knob stays env-gated (SIM_CV_SET/SIM_CV_CAP, default off) until then; the live app is unchanged.
- **Use an AGE-GRADUATED CV, not a flat 2%.** 2% is right for 11-12/13-14/15-18, but 8U/9-10 genuinely vary
  more (see _TRIM_BAND: 8U ~16%, teens ~5%). A flat 2% would over-confidence 8U. Derive per-swim CV from the
  existing age/gender trim bands (≈ band ÷ 2.5). The sweep used flat SIM_CV_SET=0.02 as a probe.
- **Do NOT** chase bias via opponent-presence/relay-tighten/event-universe (all worse here), and do not tighten
  RELAY_STD_SCALE below its shipped 0.5 (0.4 raised bias).

## Caveats
- 68-side sample (wks 2&4) for ranking; validate the chosen config on a full 488 run before shipping.
- OOS calibration demo used a flat/per-week anchor as a proxy for the shipped theory-2 reanchor (couldn't apply
  theory-2 offline without pred_coach); directionally it confirms the bias is fully calibratable.

**agegrad_ageon**  (n=68)  bias **+37.09**  MAE **41.05**  blowups(|err|>=100) 1
  vs ageon(5%): Δbias +1.41 (ref +35.7), ΔMAE +1.42  [paired n=68]
  vs ageoff(5%): Δbias +8.02 (ref +29.1), ΔMAE +4.96  [paired n=68]
