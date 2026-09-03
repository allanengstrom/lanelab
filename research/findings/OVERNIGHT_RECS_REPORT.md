# Overnight evaluation of the four recommendations (2026-06-19)

Verdict on each: **ADD**, **SKIP**, or **NEEDS-WORK**, with evidence. Default behavior of
every new knob is byte-identical (gated, off) so nothing ships until you say so.

---

## REC 1 — Age-graduated spread (vs the flat 2% I'd tested)   → **ADD** ✅
Implemented as `SIM_CV_AGEGRAD=1` (Optimizer `_single_cv`, single-swim CV = trim-band × 0.4;
8U ~6.5%, teens ~2%). Default off = byte-identical.

All-40-events scan of the SHBR vs SHR wk-1 meet (`scan_event_odds.py`), three spreads:
- **Teens tighten correctly** (the fix you wanted): 13-14 Girls 50-free 42%→**9%**, 50-back 57%→**34%**;
  clear favorites sharpen to ~99%, clear underdogs to ~1%. Zero suspicious events (default had ≥1).
- **8U stays honest — and this is why flat 2% was wrong.** 8U Girls 25-back is a near-tossup (0.6s back):
  default 39%, **flat-2% over-tightens to 25%** (a coin-flip read as decided), **age-graded keeps it 43%**.
  8U kids genuinely swim ±2s, so the wider 8U spread is correct. Flat 2% would just move the overconfidence
  bug onto the little kids; age-graded fixes teens without doing that.

**Verdict: age-graded is the right form of the spread fix. Worth adding.** (Still gated pending the
calibration refit — see REC 4.)

## REC 2 — All-events pre-meet odds scan   → **ADD (as a tool)** ✅
`scan_event_odds.py` flags any event where a clear favorite reads <60% or a clear underdog reads >40%.
On the live meet it caught the default's overconfident events and confirmed they're sane under age-graded.
Cheap, runs in seconds, genuinely catches bad reads a coach would otherwise trust. Keep it as a pre-meet check.

## REC 3 — Refit the participation value-add shrink   → **SKIP (for your use)** ⚠️
Tested whether it adds value beyond the SHIPPED theory-2 calibration (`rec3_eval.py`, 488 sides):
- theory-2 already lands the league at mean +7.0 (on target), MAE 19.3, with corr(residual, participation)
  = **−0.07** — i.e. it already removes the participation structure league-wide.
- The ONLY gap is the low-turnout tail: <0.65 participation leans +15, 0.65-0.8 leans +12 (vs +7 target),
  MAE ~25. The shrink would help *those ~53 high-division weak-team sides specifically.*
- SHBR has healthy turnout, and you predict mostly normal opponents, so this barely touches your numbers.

**Verdict: skip.** Real but niche (only the weakest, lowest-turnout teams), and it carries the
fit-on-full-league / refit-the-constants risk the docs warn about. Not worth it unless you start caring
about predictions for the div-14-17 low-attendance teams.

## REC 4 — Refit win-prob/reanchor on the new spread basis   → **REQUIRED before shipping REC 1** (in progress)
Not optional — it's the gate. Measuring the basis shift from the age-graded backtest (running).

### REC 1 backtest validation (68-side sample, paired vs default)
default 5%: bias +35.7 / MAE 39.6 · flat 2%: +37.5 / 41.6 · **age-graded: +37.1 / 41.0**.
Age-graded costs ~+1.4 raw bias (vs +1.8 for flat 2% — 8U widening recovers some), absorbed by calibration. Aggregate stays sane; per-event honesty is the win.

## REC 4 — Calibration refit on the new spread basis   → **REQUIRED but MINOR** ✅
Measured the basis shift (paired, 68 sides). The aggregate margin basis barely moves:
- win-prob σ (sd of pred−actual margin): default **61.2** → age-graded **63.1** (~+3%)
- mean pred-margin: +71.1 → +74.4 (+3.3); total bias +1.4
The per-event win%s — what the coach actually reads — change a lot (42%→9%) and are shown RAW, so they
need no refit, they just get honest. Only the headline Φ(margin/σ) and the reanchor shift, and only ~3%.
**Verdict: the refit is a small σ bump (~+3%) + a few-point reanchor, not a big project. Low ship risk.**
A fresh full-488 backtest on the age-graded basis would re-fit both cleanly in one pass.

## BONUS — Recheck the +7 value-add target (your question)   → **+7 HOLDS for W2-5; W1 BROKE** ⚠️
Re-measured honest optimizer-vs-coach value-add on CURRENT code (beat_coach_v2, same-day-form, actual
times, 150 sides). (First attempt was contaminated by the harness's resume-skip; redone clean.)
| week | current va | stale (Jun 5) | beat-rate |
|---|---:|---:|---:|
| W1 | **+0.03** | +18.56 | 16/30 (~coin flip, was 81%) |
| W2 | +3.03 | +3.13 | unchanged |
| W3 | +7.90 | +7.43 | unchanged |
| W4 | +9.03 | +9.87 | unchanged |
| W5 | +6.90 | +7.37 | unchanged |
- **W2-5 value-add = +6.7, basically identical to stale.** The +7 target is still right for the core season.
- **W1 collapsed +18.6 → ~0.** A recent default regressed the W1 optimizer (age curve is the prime suspect —
  W1 leans entirely on projection). Implication: the W1 per-week reanchor may now over-credit the optimizer
  by ~+18 (W1 displayed prediction reads too high), AND the W1 lineup quality itself regressed. Diagnosing now.

### W1 regression — CONFIRMED real, cause NOT the age curve (NEW, unprompted find)
Ruled out both alternative explanations:
- **Sample**: on the EXACT same 16 meets the stale run used, current value-add is **−0.56** (vs stale +18.56).
  Not a sample-composition effect — it's a true regression on identical meets.
- **Age curve**: W1 with USE_AGE_CURVE=0 recovers only to +1.97 (from +0.03). The age curve explains ~+2 of
  the ~+19 drop, not the rest.
Per-team drops are large & systematic (McLean +36→−7, High Point +22→−10, Highlands +35→+5, Wakefield +31→+6).
The optimizer now *loses* to the coach at W1 (beat-rate ~53%, was 81%).

**Implications:** (1) some change between 2026-06-05 and now regressed the W1 optimizer/profiles — worth a
`git bisect` running beat_coach_v2 W1 (this finding's harness) to find it. (2) The W1 per-week reanchor was fit
when the W1 edge was ~+18; it likely now over-credits the optimizer, so W1 predictions read too high.
NOTE: none of MY overnight changes caused this — they're all gated off by default and inert in this run.

## W1 8U-projection prototype (your hypothesis)   → **REAL FIX, but minority of the regression**
Measured: W1 8U profiles run **+20% too slow** (heatmap_w1_underadjust.png); older ages only +2-3%.
Prototype `W1_8U_BOOST` (prod_eval, gated, default 1.0=off): boost=0.83 zeroes the 8U error (+20%→−0.2%).
Re-measured W1 value-add (beat_coach_v2, same-day-form, n=30):
| config | W1 value-add | beat-rate |
|---|---:|---:|
| stale (Jun 5) | +18.56 | 81% |
| current, no boost | +0.03 | 53% |
| current, age-off | +1.97 | — |
| **current, 8U boost 0.83** | **+3.73** | 60% |
- **The 8U fix is real and worth keeping**: corrects a genuine +20% modeling bug, recovers +3.7 value-add,
  makes 8U placements honest. (8U times are now ~correct, so +3.7 is the full ceiling of this fix.)
- **But it's a STANDING bug, not the regression**: it recovers only ~3.7 of the ~18.5 lost (~20%). ~15 points
  are still missing from a different change between 2026-06-05 and now → **git bisect on beat_coach_v2 W1**
  remains the way to find the main culprit.
NOTE production version needs: gate to W1/no-current-data only, and boost by 8U-EVENT strokes (not all strokes
of 8U swimmers, to avoid touching their swim-up times). Derive the factor from multi-year 8U YoY data, not the
in-sample 0.83.
