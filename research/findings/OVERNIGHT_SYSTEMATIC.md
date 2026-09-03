# Overnight Systematic Bias Fix — 2026-06-23

Goal (user): a *systematic* fix, not another tuning knob. Attribute the bias to
named, measured sources; fix the root at the source so it's coherent.

## Decomposition (realistic basis: our present roster, no mock ladder, leakage-free)

3-condition run, paired n=60, weeks 1-5 × divs 2,5,8,11,14,17. err = pred − truth.

| condition            | bias  | MAE  |
|----------------------|-------|------|
| opp FULL strength    | −19.7 | 34.6 |
| opp PRESENCE ~30%    | −22.6 | 35.7 |  ← backfill refills gaps, makes it worse
| opp ORACLE (actual)  |  −4.7 | 27.9 |

By week (bias / MAE):

| wk | FULL        | PRESENCE    | ORACLE      |
|----|-------------|-------------|-------------|
| W1 | −62.0 / 65  | −62.0 / 65  | **−39.2 / 43** |
| W2 | −5.1 / 33   | −7.9 / 33   | +4.6 / 33   |
| W3 | −8.6 / 32   | −12.3 / 32  | +6.1 / 28   |
| W4 | −14.2 / 28  | −18.9 / 30  | +2.0 / 23   |
| W5 | −8.5 / 15   | −11.9 / 19  | +3.3 / 12   |

### Two distinct, measured root causes

1. **W2–5 = opponent over-modeling.** With the actual opponent (oracle), W2–5 bias
   is ~0 (+2 to +6, i.e. right at the +7 value-add target). So the −5 to −19 we see
   with full/presence is ENTIRELY because our modeled opponent is stronger than the
   real (absence-reduced) one. Fix = a genuine opponent presence *discount* (weaken
   toward realistic strength) WITHOUT the bench backfill that currently cancels it.

2. **W1 = our-side self-under-prediction.** Oracle W1 is still −39. Knowing the
   opponent perfectly doesn't help — we predict OUR OWN team ~39 pts too low at W1.
   Root suspect: prior-year times under-rate year-over-year improvement (we project
   8U ×0.88 but apply no improvement to 9-18). Fix = age-graded early-season
   improvement projection for all returning swimmers. (To be quantified at the time
   level next.)

These are independent mechanisms (W1 our side too low; W2-5 opponent too high), so
they get two separate principled fixes, each validated against the oracle target.

## CORRECTION — the W1 finding was a harness artifact, not a production bias

Checked against `prod_eval.py` (production-faithful: mirrors `_run_and_cache`
exactly, models BOTH sides symmetrically from prior year). June-7 basis, n=488:

| wk | bias  | MAE  |
|----|-------|------|
| W1 | **+1.4**  | 31.1 |  ← unbiased in production
| W2 | +11.8 | 23.2 |
| W3 | +11.6 | 21.6 |
| W4 | +12.0 | 22.7 |
| W5 | +12.1 | 20.1 |
| ALL| +9.8  | 23.7 |

The −39/−62 at W1 in the realistic harness was an artifact of its **asymmetry**: the
oracle gives the opponent their real (improved) times but leaves our side on stale
prior-year times, so we look 4-5% too slow *relative* to them. In production both
sides are stale together (the W1 time-error is symmetric: 8U +11%, 9-10 +4.5%,
11-12 +5.2%, 13-14 +4.2%, 15-18 +1.9%) so the improvement gap **cancels** → W1 is
fine. Also, production already runs a W1 presence-MC headline correction
(`_presence_adjusted_rows`, prod_eval L152). So NO W1 improvement-projection fix is
needed — it would "fix" a non-problem. **Fix 1 is dropped.**

## The real systematic bias: +12 over-optimization, flat across W2-5

prod_eval fields OUR **optimizer (max) lineup** vs the opponent's **predicted
(realistic) lineup** — we optimize, they don't. That asymmetry is the prime suspect
for the persistent +12 (it does NOT fade by W5, so it's structural, not stale-data).
Next: measure pred_opt vs pred_coach-anchor (score our side with the same realistic
predictor we use for opponents) — if the +12 collapses, coach-anchoring is the
systematic, source-level fix. Validate on prod_eval basis.

### Measurement (overopt_test.py) — running, W2-5, 200 sides

Per side, SAME opponent + SAME profiles, two scorings:
- pred_opt    = our optimizer (strategy_robust max) lineup
- pred_anchor = our realistic lineup (_predict_opp_lineup_or_fallback pointed at us)

First side (W2 Old Keene Mill vs Tuckahoe): opt=176.3, anchor=172.4, truth=172.0.
The anchor lands on truth; the optimizer is +4 high. Mechanism confirmed: the +12 is
OUR lineup being scored as the optimizer max vs the SAME opponent. Same opponent in
both, so it is NOT an opponent-strength effect — it is purely our-side optimization.

### Design of the fix (pending the aggregate)

Key nuance: the +12 is NOT all error. Part is genuine value-add — if a coach actually
fields the recommended (optimal) lineup, they DO beat their habitual baseline, and the
backtest truth is the coach's habitual result. The historical "real optimizer edge" is
~+7. So the goal is displayed bias ≈ +7 (keep the genuine edge), not 0 (which would
under-sell the optimizer). The piece to remove is the over-fit ABOVE +7.

Two coherent ways to do it (decide from the data):
1. Per-event blend displayed = α·opt_event + (1−α)·anchor_event, α chosen so residual
   ≈ +7. Coherent (rows sum to total); recommended lineup unchanged. α≈0.58 if
   opt−truth≈+12 and anchor−truth≈0.
2. Symmetric-opponent scoring: score the recommended (optimizer) lineup vs the
   opponent's OPTIMIZED lineup (both coaches optimize). No tuned α; the residual is
   the genuine edge by construction. More compute (optimize the opp too).

Prefer (2) if it lands near +7 without tuning — it is the more principled "both sides
optimize" model and stays coherent with the recommended lineup. Fall back to (1) if
(2) over/under-corrects. Validate the chosen fix on the prod_eval basis by week.

## THE REAL FIX: the coach-anchor already exists — the conserve pass discards it

Reading app.py 3648-3769 changed the conclusion. The principled fix is ALREADY
CODED (theory-2 block, L3685-3717):
- it builds `pred_coach` = score of the coach-predicted our lineup (identical to my
  `pred_anchor`), via `_predict_opp_lineup_or_fallback(your_team,...)`;
- sets the honest total `full = pred_coach + reanchor[wk] - div_term`;
- `mc_total = mc_total + delta` to land on it; logs `[calibration-theory2]`.

Then the CONSERVING SCORESHEET pass (L3729-3765) immediately overwrites it:
`mc_total = sum(rows mc_pts)` re-sums the RAW optimizer per-event points, and the
pool is split from `mstats_raw` (pre-anchor). So the displayed total reverts to RAW
(the +12), and the de-inflation survives ONLY in the win% (origin-forced Φ(margin/50)).
That is exactly the incoherence the user flagged: inflated total, calibrated win%.

Why they did it: an earlier ADDITIVE smear toward 4.5 made guaranteed sweeps read as
toss-ups, so they moved de-inflation to win%-only. But a MULTIPLICATIVE scale
(mc_pts × anchored/raw ≈ ×0.95) preserves structure — a sweep stays ~7.6, not 4.5 —
while making the rows sum to the honest total. That is the surgical, systematic fix:
**make the conserve pass scale to the theory-2 anchored total instead of discarding
it.** Not a new knob; it makes the existing principled calibration actually take effect.

### Two open questions the running measurement answers (no extra run needed)

From overopt_test (pred_opt, pred_anchor, truth per side) + theory-2 constants +
division, I can post-process:
1. pred_anchor − truth by week: is it ~0 (over-opt is our lineup) or ~+12 (shared
   opponent over-model)? Determines whether theory-2's reanchor constants (W2 −5.5
   ... W5 −0.28, which assume pred_coach−truth≈+12) are still valid on current code.
2. (pred_anchor + reanchor − div_term) − truth by week: does the EXISTING calibration
   hit the +7 target? If yes → fix = un-discard it. If no → refit the constants on
   current basis, then un-discard.
Then implement the conserve-pass scale fix + one confirmation run.

## INTERIM (23/200 sides) — the over-prediction is mostly already fixed at the source

| wk | pred_opt − truth | pred_anchor − truth | over-opt gap |
|----|------------------|---------------------|--------------|
| W2 | +5.5 | −0.5 | +6.1 |
| W3 | +9.3 | −0.3 | +9.6 |
| W4 | +9.7 | −0.2 | +9.9 |
| W5 | +8.9 | −1.2 | +10.1 |

Two things:
1. **pred_anchor ≈ truth (~0).** A coach fielding the predicted/typical lineup scores
   ~truth. So the optimizer's edge (the gap, ~+8) is essentially the genuine value-add
   (+7 target) — NOT over-fit. The winner's-curse inflation that made the old basis
   +12 has been removed at the source by the age-graded-CV (spread) fix.
2. **The raw displayed total (= pred_opt, since conserve shows raw) is ~+8, already
   within ~1 of the +7 target.** The over-prediction the project has been chasing is
   largely gone on current code.

Consequence for the fix:
- The theory-2 reanchor constants are STALE: they subtract ~5.5 (W2) assuming
  pred_coach−truth≈+12; with pred_coach−truth≈0 they would push the displayed total
  to ~−5. So "just un-discard theory-2" is WRONG now.
- Real options (decide on full 200): (a) RETIRE theory-2 — raw is already ~+7, so the
  systematic story is "the source fix obsoleted the post-hoc calibration"; just remove
  the dead/incoherent layer. (b) REFIT reanchor to ~+7 flat (since anchor≈0) and make
  the conserve pass honor it (multiplicative scale) for a coherent, robust, on-target
  displayed total + win%. Leaning (b) for coherence; (a) if the full run stays ~+7 flat
  and low-variance enough that a calibration layer adds nothing.
NOTE: 23 sides — do not conclude yet. Check by-division too (theory-2's div_term
flattened a staircase; confirm whether the staircase still exists on current code).

## FINAL RESULT (200 sides, W2-5, divs 1-9) — the over-prediction is already fixed

| metric                 | overall | W2   | W3   | W4   | W5   |
|------------------------|---------|------|------|------|------|
| RAW displayed (=pred_opt) | **+7.2** | +5.9 | +6.7 | +8.2 | +8.2 |
| anchor (coach lineup)  | −0.6    | −1.2 | −0.8 | −0.4 | −0.0 |
| theory-2 (stale consts)| −4.4    | −8.2 | −4.8 | −2.6 | −1.9 |

By division, RAW bias is noisy +4.6…+9.6 with NO monotonic staircase; anchor ~0 across
all divisions. (95% CI on raw ≈ +7.2 ± 2.) Conclusions, all confirmed:

1. **The displayed total over-predicts by +7.2 — which IS the +7 value-add target.**
   The old +12 (June) / +30 (mock) is gone; the age-graded-CV (spread) fix you already
   shipped removed the winner's-curse inflation at the source. There is no remaining
   over-prediction bias to chase. (W1 was already +1.4 from prod_eval, so all-week
   production bias ≈ +6.)
2. **The +7 is genuine value-add, not error.** The coach-predicted (habitual) lineup
   scores ~truth (anchor ≈ 0); the optimizer lineup we recommend is ~+7 better. So
   displaying truth+7 is the honest "this is what you'll score if you field our
   lineup" — correct by design.
3. **The theory-2 / div_term calibration is now STALE and obsolete.** Its constants
   assume pred_coach−truth ≈ +12; with the current ≈0 it would push the display to
   −4.4. It is being silently discarded by the conserve pass — which is, by accident,
   the right thing now. There is also no division staircase left for div_term to flatten.

## Recommendation

- **No new bias fix is needed.** The systematic fix already happened at the source
  (spread). The headline is "it's fixed; here's the proof."
- **Retire the stale theory-2 + div_term layer** (it is dead, stale, wastes a full
  lineup-prediction per request, and is a landmine: anyone who "fixes" the discard
  pushes the display to −4). Gated OFF this session; behavior unchanged (it was already
  discarded), and verified on the live path.
- **Optional robustness upgrade (ready, not applied):** replace it with a single
  coherent anchor — displayed = pred_anchor + 7 (flat; no per-week/div constants),
  made to stick by scaling the conserve rows multiplicatively (×0.95, sweeps preserved)
  instead of re-summing raw. Numerically a near-no-op today (raw is already +7) but
  pins the total at the genuine value-add and keeps points + win% coherent if the model
  ever drifts. Enable only after review since it touches the live display path.

## W1 IS NOT FIXED — it regressed to −25 (separate bug, found by the W1 check)

overopt_test skipped W1, so I measured it separately (`w1_raw_eval.py`, 40 sides,
production-faithful `predict_total`). W1 raw displayed bias = **−25.6** (median −25,
MAE 35), 11/40 sides blowing up negative (−51…−102). Paired pool check: the model
predicts a 368 meet pool vs the real 420 — it leaves ~52 points unallocated (fields too
few scorers). June-7 prod_eval had W1 at +1.4, so this is a regression — the same one
flagged in [[meetlineup-value-add-and-w1-regression]] (W1 broke 2026-06-05→06-19), now
shown to hit the DISPLAY, not just the value-add.

**Localized (`w1_diag.py`, pre- vs post-presence):** pre-presence W1 is ~unbiased
(mean ≈ +2.5 on 8 sides, high variance); the **W1 presence-MC** (`_presence_adjusted_rows`,
p=W1_PRESENCE_P=0.60) then deflates every side ~33 → −30. On the 40-side run (post
−25.6) that implies pre-presence ≈ +7 — right on the W2-5 level.

**Mechanism:** the presence-MC marks 40% of OUR swimmers absent (backfilling from the
bench) while leaving the opponent full — an asymmetric ~33-pt knockdown. Added (app.py
3594) to cancel a +29 W1 over-prediction from "full 2024 roster fields ghosts +
absentees." The June-17 commits (bc5feaa "Never field an excluded swimmer"; e97c6fe
"Fix Week-1 opponent prediction"; 101c86b imputation review) removed those ghosts at
the SOURCE, so pre-presence is now ~+7 and the p=0.60 deflation double-corrects into
−25. Same staleness as theory-2, but this stale correction is NOT discarded — it
actively harms W1.

**Fix — APPLIED (live, reversible).** Confirmed on 30 sides: pre-presence W1 = **+6.1**
(median +8) vs current −27.6. Gated the presence-MC behind
`W1_PRESENCE_MC_ENABLED = os.environ.get("W1_PRESENCE_MC","0")=="1"` (app.py ~5444) and
added it to the `if week_num_n==1 and not our_has_current` gate (~3601). Default OFF →
W1 now shows the raw +6 total with a win% computed on the SAME raw basis (more coherent
than before, where the win% used the deflated total vs a raw pool). `W1_PRESENCE_MC=1`
restores the old behavior. Verified: app.py parses, the debug reloader restarted the
worker (PID changed 03:14:29), HTTP 200. NOT git-committed — left for your review.

Caveat (pre-existing, not introduced here): the W1 win% σ=50 may be too confident for
the thin-data W1 regime; `_w1_winprob` (the timid intercept fit) is computed but the
conserve pass overrides it with σ=50. Worth a look, but separate from this fix.

## Bottom line for the morning

- **W2-5 over-prediction: already fixed** at the source (+7.2 = value-add target). No
  action needed. The stale theory-2/div calibration is harmlessly discarded — retire it
  when convenient (don't un-discard without refitting).
- **W1: was badly broken (−25), now fixed** (+6) by disabling the stale presence-MC.
  Live and reversible. This was a real regression hiding under the "it's all fixed"
  story — worth the dig.
- Net: displayed-total bias is now ~+6 to +8 across ALL weeks — consistent and on the
  intended value-add target. One coherent story instead of W2-5 +7 / W1 −25.
