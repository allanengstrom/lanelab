# Optimizer improvement priorities

Tracking real problems identified during the 2026-05-27 stats audit.

## High-priority issues

### 1. Score bias — we under-predict by ~22 pts (SOLVED: two structural causes, real cure found, no multiplier)
**Status:** cure validated empirically (2026-05-29), ready to implement
**Current (production D0):** Score Bias = −22.01 pts, Score MAE = 31.90 pts (W2–W5)

**THE KEY INSIGHT — reality is flat across the season.** From ground truth (actual
placements + final scores), per team, EVERY week:
- individual points ≈ **179** (flat)
- relay points ≈ **29.5** (flat)
- final total ≈ **208** (flat)

There is **no real "week slope"** in the world. The per-week bias gradient we saw
(W2 −7 → W5 −35) is entirely an artifact of our *prediction* degrading over the season.
The multiplicative week-correction "worked" only by fitting away our own prediction
drift — a band-aid, not a cure.

**Two real structural causes of the −22 bias:**

**(a) Missing relays (~30 pts/team, the level).** Relays (medley + free, per age/gender)
are in the actual final score but NOT in the lineup data → never predicted. Ground-truth
relay contribution = final − individual ≈ **29.5/team, flat every week**. A simple relay
model (best swimmer per stroke for medley; 4 fastest for free; head-to-head, **3 pts per
relay win**, ~10 wins/team) reproduces this: 29.8/28.1/29.6/29.6 by week. Validated
directly against truth.

**(b) Coverage-driven week slope (the slope).** Early season, only ~58% of an opponent's
actual swimmers have a profile (W2) → unprofiled swimmers are *invisible* to the scorer →
my swimmers face phantom-thin fields and over-win. Coverage climbs to ~85% by W5, so the
over-prediction shrinks. opp_prof_frac by week: W2 .581, W3 .714, W4 .809, W5 .854. This
same thin coverage also *under*-fills relays early (W2 relay predicted 14.6 vs 29.6 truth).

**THE CURE (no multiplier, no per-week fitting):**
1. **Add relay events** (P=3/win) — fixes the ~30 level. Displayed as their own events, so
   per-race expected points still sum to the total (consistency requirement satisfied).
2. **Coverage blend** — fill a missing 2025 swimmer with their REAL prior-year (2024) time
   instead of leaving them invisible (or a synthetic percentile, which overshoots — see
   footnote). This deflates the early individual over-prediction AND fills the relay hole
   with one mechanistic change.

**Empirical result (exp_blend.py, W2–W5, n=384), vs the multiplier baseline:**
- RAW (ind only): MAE 32.01, bias −22.01
- MULT band-aid: MAE 22.03, bias ~0 (fitted per-week factor)
- RELAY only (P=3, no fitting): MAE 21.88, bias +3.62  ← already beats the band-aid
- **CURE: relay + coverage blend: MAE 20.5, bias +0.5** ← beats everything, no multiplier
  - relay now flat ~30 every week (coverage hole cured)
  - residual per-week total bias: W2 +8.4, W3 +4.5, W4 −1.7, W5 −8.7 (small, within noise)

**Footnote — synthetic-percentile imputation overshoots, use real prior-year times.**
Imputing missing opponents at the event *median* drove bias to −51 (median phantoms are too
competitive and flood every event). No single percentile flattens all weeks because the
*composition* of missing swimmers changes: early missings are real competitors (no profile
yet), late missings are slow/exhibition (even a 90th-pctile phantom overstates them). Real
prior-year times are self-calibrating and the right tool.

**W1 is a separate regime — SOLVED 2026-05-30 with mechanistic v3 + imperfect picker.**

*Background (2026-05-29):* W1 uses prior-year (2024) profiles with no same-season data.
Full prediction overshot final by **+67/team** due to (a) ~24% ghost roster (2024 swimmers
who don't return in 2025), (b) ~40% age-ups, (c) opponent rookie invisibility. Earlier
analysis suggested ~26-pt centered-MAE noise floor and recommended ×0.73 calibration.

*Update (2026-05-30):* an architectural cure was found that beats the calibration with no
fudge factor — bias near 0, mechanistically defensible.

**The cure — three components:**

1. **Per-division v3 rookie imputation on opp profile.** For each (team, band, gender),
   inject N imputed rookies (band-specific counts: 8U=12, 9-10=6, 11-12=5, 13-14=4, 15-18=4)
   at percentiles calibrated by that team's *division-specific* star rate (measured from
   2021-2024 transitions) + specialty modeling (primary stroke at full percentile, others
   30pp slower). Times mapped via per-division 2024 league pools. This fills the
   rookie-invisibility gap with realistic depth.

2. **Imperfect self-optimal picker.** Coach-realistic lineup chooser — pass 1 fills all 3
   slots per event with primary-stroke matches (swimmer's fastest stroke), pass 2 greedy-fills
   remaining slots. Matches actual W1 coach behavior (fielding specialists in their primary
   stroke, not strategically reallocating for global optimization).

3. **Enriched profile for users with ladder data.** SwimTopia roster + HY-TEK ladder PDF +
   2024 fallback (in priority order). Kills ~24% ghost problem at source. NO v3
   augmentation on the enriched side (asymmetry handled by opp picker choice).

**Per-division calibration is the key.** 17 NVSL divisions of 6 teams each, inferred from
the 2024 meet graph (connected components — teams that play each other are in the same
division). Star rates vary dramatically across divisions (div 0 has 100% 8U star rate, div 6
has 83%, lower divisions ~30%). Using league-wide rates over/under-imputed; per-div rates
calibrate properly.

**Production architecture A — B&R with ladder ("Option B"):**
- US: enriched profile (no v3), `imperfect_self_opt(primary_quota=3)`
- OPP: 2024 + per-div v3 augmentation, `self_optimal` (full LP, current production)
- Score head-to-head, add relay points

**Production architecture B — fallback (teams without ladder/SwimTopia):**
- US & OPP: raw 2024 + per-div v3 augmentation
- Both sides: `imperfect_self_opt(primary_quota=3)`
- Score head-to-head, add relay points

**Empirical results:**
- B&R W1 2025 single meet: pred 241 vs truth 232, **err +9** (n=1)
- Batch fallback architecture (n=98, no ladder for any team): bias **+3.67**, MAE **28.49**,
  cMAE 28.35
- Cross-week generalization confirmed (W2-W5 with simulated-enriched profiles): bias stays
  +4-5 across all weeks when "enriched" is built from in-season prior weeks → architecture
  pattern is stable, not W1-specific
- Compared to old production: bias was −22 in W2-W5 batch, +67 at W1 raw; now ~+4-9 at W1

**Scripts:** /tmp/w1_overnight_search.py (126-config search), /tmp/w1_br_full_matrix.py (5x5
picker matrix for B&R), /tmp/w1_simulated_enriched.py (cross-week validation), /tmp/MORNING_REPORT.md
(full writeup), /tmp/w1_diag.py and /tmp/w1_diag2.py (original noise-floor analysis).

**Implementation status:** architecture validated, production wiring not yet done — see
"Next tests / experiments" below.

**Scripts:** /tmp/exp_blend.py (cure), /tmp/exp_relay2.py (relay vs multiplier),
/tmp/exp_impute_scan.py (why synthetic impute overshoots), /tmp/build_cache.py +
/tmp/meet_cache.pkl (241 meets: profiles, optimal lineups, raw actual lineups w/ places).

### 2. Margin bias inflates the headline win prob
**Status:** 🟡 PARTIALLY SHIPPED 2026-06-05. Shrinkage wired + W1 gated, but the constants were fit
on the wrong margin (greedy, not MC) → over-shrinks. **Re-fit on production margins is the open task.**
See "Implementation status" + "CALIBRATION BUG" below.
**Original (May 27):** Margin Bias = +19.71 pts.
**After interim work (June 4 measurement before fix):** +11.86 pts (halved by coverage_blend, v4Rt, polish v2, hybrid 8U, Bug 1).
**After shrinkage fix (held-out 2025 result):** **+1.59 pts.** Bias essentially zero.

**Root cause** — the optimizer maximizes both teams' scores by picking each team's BEST swimmers per event. The max of a noisy estimator is biased upward (winner's curse / selection bias). So predicted margins amplify real strength differences by ~2.2× league-wide:
  - Actual mean margin (team_a − team_b across 2025 meets): +9.7
  - Predicted mean margin: +21.7
  - Amplification: 2.24×

**Mechanism is symmetric across tiers** — per-tier `k` fits range 0.42–0.50 (elite 0.50, lower 0.42), so a single global shrinkage handles it cleanly. No per-tier complexity needed.

**The cure — Stein-style shrinkage + analytical Φ:**
```python
SHRINK_K = 0.455        # fitted on 2023+2024 W2-W5, n=392 meets
SIGMA    = 64.0         # post-shrinkage residual SD on held-out 2025

adjusted_margin = SHRINK_K * (our_pred - opp_pred)
win_prob        = norm.cdf(adjusted_margin / SIGMA)
```

**Why shrinkage (not subtraction):**
- Subtraction is constant-additive — wrong for blowouts AND can flip the sign of close meets (pred +5 → −7 means "we win" became "we lose")
- Shrinkage is proportional — scales with prediction magnitude (which is exactly how the inflation works)
- Preserves sign always; calibrates the magnitude

**Empirical results (2023+2024 train, 2025 test, all W2-W5):**
```
                                  bias        MAE       SD
  k=1.0 (no shrinkage)         +11.86     53.26    77.69    ← previous state
  k=0.455 (global fit)          +1.59     48.38    64.17    ← shipped (TBD)
  per-tier k                    +1.36     48.31    64.01    ← marginal upside, not worth complexity
```

**Win-prob calibration with analytical Φ:**
```
                                σ   winp_bias   |err|    Brier
  k=1.0,   σ=measured        77.7   +0.0296    0.3303   0.1753
  k=0.455, σ=measured        64.2   +0.0119    0.3869   0.1841
  naive 50/50 baseline                         0.5000   0.2500
```

Shrinkage improves win-prob bias (+2.96% → +1.19%) and slightly worsens Brier (humble predictions trade sharpness for calibration). For a coaching tool, "more honest" is correct.

**Additional benefit — drops `strategy_robust` from 2× to 1×.** The analytical headline only needs OUR optimization (our predicted score) + opp's predicted score from a single `simulate_match`. Eliminates the second `strategy_robust(opp_perspective)` call from the pipeline → **optimizer wall time drops ~60s** (≈ half).

**Refit cadence:** annually, as more years of data accumulate. The 2.2× amplification ratio could drift as the model evolves.

**Scripts:** `/tmp/test_shrinkage.py` (fit + validate), `/tmp/test_analytical_winprob.py` (W1 sanity check), `/tmp/test_analytical_w2_w4.py` (W2-W4 sanity check), `/tmp/identify_team_a.py` (confirmed team_a = alphabetically first, not home team; ruled out home/away modeling).

**Implementation status: 🟡 WIRED 2026-06-05, but the CONSTANTS ARE MISCALIBRATED — re-fit needed.**
Done in `app.py`:
1. Added `WINP_SHRINK_K = 0.455`, `WINP_MARGIN_SIGMA = 64.0`, and `_shrunk_winprob(pred_margin)`
   (right after `match_stats`). Φ implemented via `math.erf` — no scipy dependency.
2. Production feeds it `mstats["margin"]` = `mean(our_totals − opp_totals)` over the N=10k
   `simulate_match` draws: `analytical_winp = _shrunk_winprob(mstats["margin"])` in `_run_and_cache`.
3. Dropped the symmetric opp-perspective `strategy_robust` call (the old `robust_norm_winp`
   normalization) → ~60s faster. `robust_norm_winp`/`robust_their_ewp` stay `None` (back-compat).
4. `/lineup` route: headline reads `analytical_winp`, label = **"win probability"**.
5. **W1 week-gate (added after Flag 2):** `analytical_winp` is `None` at W1 and the `/lineup`
   route suppresses the W1 headline entirely (W1 margins are a different regime — see below).

**⚠️ CALIBRATION BUG (flagged by the margin-bias agent 2026-06-05 — must re-fit):**
The constants `k=0.455`/`σ=64` were fit (in `/tmp/test_shrinkage.py`) on **`race_points(pure_greedy)`
margins** — confirmed: the script computes `pred_margin = race_points(pure_greedy(profiles))`.
But production feeds them the **`simulate_match` MC mean margin**, which is a *different quantity*:
MC sampling softens blowouts, so the production margin is typically **~0.4× the greedy margin**
(observed ratios across 4 meets: 0.39, 0.42, 1.54, 0.25 — small AND inconsistent). So the wired
headline **over-shrinks → reads too timid (pulled toward 50%)**. It is directionally de-biased
(far better than the old broken ~95%) but NOT properly calibrated. My earlier note here claiming
`mstats["margin"]` "IS the margin the fit was done on" was **wrong** — that conflation is the bug.

**Fix:** re-fit `k` and `σ` directly on **production margins** — run the real pipeline
(`strategy_robust` → `simulate_match`), log `mstats["margin"]` vs the actual final margin across
many W2–W5 meets (a `prod_eval`-style harness), and fit `actual_margin ≈ k·prod_margin` + residual
`σ`. Same method as `test_shrinkage.py`, correct inputs. Until then, treat the headline as a
conservative estimate, not a calibrated probability.

**W1 is a separate regime (do NOT use these constants there):** measured W1 margin bias +42
(vs +12 for W2–W5), `σ ≈ 192` (vs 64), W1-specific `k ≈ 0.07` (vs 0.455). The W1 headline is now
suppressed; give it its own constants only once W1 itself is calibrated.

### 3. % better than coach "collapses by W5 (95.7 → 28.0)" — ❌ DEBUNKED 2026-06-05, it was a measurement artifact
**Status:** RESOLVED as a measurement bug, NOT a real model problem. There is **no W5 collapse.**

**The "collapse" was the CIRCULAR metric.** The logged 95.7%→28.0% scored our optimizer's
lineup against the coach using **model/profile times** — the exact quantity the optimizer
maximizes — so we "win" by construction, and the number tracks profile coverage (high early,
noisy late) rather than real performance. Proof on the same meets, both ways: **MODEL-times
beat-coach 100% (20/20) vs ACTUAL-times 55% (11/20).** The 95.7%/62.5% logged figures were the
model-times version. **Always score beat-coach on ACTUAL times.**

**The honest metric (actual times + same-day-form + present-roster) shows the OPPOSITE shape —
a ramp, not a collapse:**
```
W2 50%   W3 83%   W4 83%   W5 80%   |   ALL 74%, +6.95 pts/team   (n=120)
Outcome flips: 8 GOOD (loss->win), 0 BAD. Downside-free.
```
We get *better* vs coaches as current-season data accumulates, and plateau ~82%. The two
honesty fixes (operator-driven):
- **Same-day-form scaling** for moved swimmers — scale a swimmer's stale profile by their
  `mean(actual/profile)` over events they DID swim that day, instead of using the stale time.
  Lift: W1 56→81%, W2 31→81% (both converge → the old low numbers were stale-profile artifacts).
- **Present-roster restriction** — optimize only over swimmers who actually competed (absences
  otherwise inflate both bias AND beat-coach). Symmetric/fair. See `beat_coach_v2.py`.

**The real residual is W2 = 50%, and it is an INFORMATION gap, not a fixable bug.** At W2 we have
1 noisy current week; profiles are mostly stale 2024; the coach knows current form. Shrinkage
(regularizing thin W2 profiles toward 2024) was tested and is a WASH (0/10 flips, bias/MAE
unchanged — see `test_w2_shrink.py`) because the problem is *missing current info*, not noise.
Only more data (W3+) or an external current-form signal (roster uploads, taper info) closes it.

**Scripts:** `reconcile_beat_coach.py` (model-vs-actual proof), `beat_coach_v2.py` (honest
metric), `test_w2_shrink.py` (W2 shrinkage wash). Full writeup in `PROGRESS_AND_IDEAS.md`.

## Recently completed

- ✅ Silent v5 regression diagnosed: training/inference drift after `Optimizer.py` was edited post-train
- ✅ v5 retrained (2026-05-27 21:32) — Jaccard recovered 47.6% → 51.55%
- ✅ Staleness check added in `coach_predictor._load_model()` to flag future drift
- ✅ Lineup template restored — scenarios + pct_needed re-wired into payload
- ✅ Coach-vs-coach margin calibration verified at +0.00 pts (matches historical +0.01)
- ✅ Per-swimmer tapering trend tested → REJECTED, 24% worse MAE (noise dominates slope)
- ✅ Uniform population taper multiplier tested → REJECTED, 0.00 effect on placement-based scoring
- ✅ Coach lineup coverage hypothesis confirmed — 24.8% of actual-lineup swimmers unprofiled
- ✅ League-avg imputation cuts coach score bias 49% (−37.80 → −19.24, MAE 38.60 → 27.50)
- ✅ Optimizer pool augmentation cuts optimizer score bias 45% (−22.01 → −12.31)
- ✅ W1 cure architecture found (2026-05-30) — per-div v3 + imperfect picker, bias ~0 with
  no fudge factor. Mechanistic across W1-W5 (cross-week validated).
- ✅ **v4Rt shipped to production (2026-06-02)** — tier-aware augmentation, cross-year
  validated. Bias improvement vs prior v3 wire: −14 → −0.8 on W1 2025, −14 → −0.06 on
  W1 2024 (held-out). See `w1_predictor.augment_v4r_tier_aware` and the W1 branch in
  `app.py::_build_opp_mixture`.
- ✅ **Fix #2 (prior-band carry-forward) shipped 2026-06-03** — `build_profiles_recency_weighted`
  now scales prior-band race times forward with empirical growth factors instead of dropping
  them. Fixes the Nicholas-Ferrante class of cases (13-14 50-breast 40.43 → 15-18 50-breast 39.54
  instead of imputed 43.03).
- ✅ **Fix #4 (within-band CRN polish) shipped 2026-06-03** — `_polish_within_band_swaps` catches
  same-band cross-stroke 2-opt swaps the optimizer misses (e.g. Soren ↔ Nico back/fly in
  15-18 Boys, +1.0 pt). Uses Common Random Numbers + combined value function (score + style ×
  real-stroke-delta) + best-improvement greedy. ~30-60s per run.
- ✅ **Bug 1 (leaders cache year-mismatch) fixed 2026-06-04** — `_build_team_dated_from_leaders`
  now refuses to return cached data when the cache's `metadata.year` doesn't match the requested
  year. Was contaminating cross-year batch evaluation (2024 D1/D3/D11 had artificial −41 to −70pt
  biases that snapped to ±2 after fix).
- ✅ **Hybrid 8U opp filler shipped 2026-06-03** — `_hybrid_fill_opp_8u` keeps opp's real 8U
  swimmers and fills empty slots with division-typical-depth synthetic swimmers. Cuts the SHB-vs-SHR
  W1 8U sweep from 7-of-8 to 4-of-8. Also fixed the `_cache["opp_profiles"]` rebind bug that was
  causing phantom +5pt deltas on the Check tab.
- ✅ **Shrinkage validated 2026-06-04 (issue #2)** — fitted k=0.455 on 2023+2024 (n=392),
  validated on held-out 2025 (n=195). Margin bias drops from +11.86 → +1.59 (~86% reduction)
  on held-out data. Combined with analytical Φ at σ=64 gives a clean, honest headline win prob.
- 🟡 **Shrinkage win-prob WIRED 2026-06-05 (issue #2 — NOT closed; constants miscalibrated)** —
  `_shrunk_winprob` + `WINP_SHRINK_K=0.455`/`WINP_MARGIN_SIGMA=64` in `app.py`; headline
  `Φ(0.455 × mstats["margin"] / 64)` (margin = `mean(our−opp)` from `simulate_match`). Dropped the
  symmetric `strategy_robust` run (~60s faster); W1 headline gated off. **Open:** the constants were
  fit on `race_points(pure_greedy)` margins, not the MC `simulate_match` margin production feeds —
  over-shrinks (too timid). Re-fit on production margins. See issue #2.
- ✅ **W1 thin-leaders source-selection guard shipped 2026-06-05** — in `api_load_setup`: a team
  with a single stray pre-season leaders entry was getting a 1-swimmer profile that SUPPRESSED its
  full 2024 record → near-empty profile → ±200 blowouts. Guard: if leaders coverage <
  `LEADERS_MIN_SWIMMERS` (20), merge the prior-year baseline underneath. **W1 blowouts 13→5,
  MAE 108→38.** Mirrored in `prod_eval.py::build_profiles`.
- ✅ **Beat-coach metric de-fogged 2026-06-05 (issue #3 debunked)** — proved the 95.7%→28% "W5
  collapse" was the circular model-times metric; honest actual-times + same-day-form +
  present-roster metric shows a 74% ALL / +6.95 pts/team ramp with 8 GOOD flips / 0 BAD. See
  issue #3 and `PROGRESS_AND_IDEAS.md`.

## Next tests / experiments

- [x] **Wire W1 architecture into production** (issue #1) — DONE (2026-06-02):
   - `w1_predictor.augment_v4r_tier_aware` wired into `_build_opp_mixture`
   - Top-tier opps (D1-D6) get raw 2024 (already calibrated)
   - Mid/bot-tier opps (D7-D17) get v4R phantoms (per-tier mean_n_per_team and
     star_rate from 2022-2024 transitions)
   - `nvsl_divisions_by_year.json` provides year-aware tier lookup
   - `w1_v4_params.json` holds the empirical rookie distributions
- [ ] **Implement pool augmentation in production app for W2-W5** — port the H2 logic into the app's profile-build pipeline (issue #1 residual)
- [ ] **Combine pool augmentation + cherry-pick** — does layering them close the residual −12 to near zero? (issue #1 residual)
- [x] **Wire analytical-Φ shrinkage headline** (issue #2) — DONE 2026-06-05:
   - Added `WINP_SHRINK_K = 0.455` / `WINP_MARGIN_SIGMA = 64.0` + `_shrunk_winprob` (math.erf Φ)
   - `analytical_winp = _shrunk_winprob(mstats["margin"])` in `_run_and_cache`
   - Dropped the opp-side symmetric `strategy_robust` call (~60s wall time)
   - `headline_label` → "win probability" in `app.py::lineup`
   - (Optional, not done) show shrunk margin alongside raw for transparency — the raw
     `margin`/`our_median`/`opp_median` are still in the payload if we want this later
- [ ] **Multi-band phantom extension** — paused pending tonight's production data. Other agent
   flagged that 8U is structurally special (full turnover yearly = all rookies); older bands have
   returners so phantom-fill yields diminishing returns. See `division17_findings.md`
   for the empirical case and the addendum on why to wait. Also: production may have a flat
   league-wide +2-4 baseline over-prediction that needs addressing separately.
- [ ] **Refit shrinkage k annually** — as more years of data accumulate, the amplification
   ratio (currently ~2.2×) may drift. Rerun `/tmp/test_shrinkage.py` each off-season.
- [ ] Multi-event fatigue penalty — deferred (low priority)

## Reference: current measured stats

```
Score MAE              31.90 pts    (bias −22.01)   → augmentation: 34.50 / −12.31
Coach Score MAE        38.60 pts    (bias −37.80)   → league_avg: 27.50 / −19.24
Margin MAE             46.46 pts    (bias +19.73 — issue #2)
Coach-vs-coach Margin  33.71 pts    (bias +0.00 — calibrated ✓)

% better than coach    62.5% overall    (240/384, +15.86 pts/meet gain)
  W2: 95.7   W3: 77.1   W4: 52.1   W5: 28.0    (issue #3)

v5 Jaccard             51.55% mean    (n=384)
  W2: 48.18  W3: 49.94  W4: 52.49  W5: 55.28
```

### W1 architecture (shipped 2026-06-02 — v4Rt tier-aware)

```
Cross-year validation (n=98 W1 2025, n=100 W1 2024, both batches):

                                     bias    MAE
W1 2025:
  v3 (legacy)                      −14.00  33.03
  raw 2024 (no aug)                 +1.48  32.17
  v4R  (per-tier league phantoms)   −7.22  32.59
  v4Rt (TIER-AWARE) ★               −0.81  31.42

W1 2024 (held-out: params from 2022-23 only):
  v3 (legacy)                      −14.34  39.89
  raw 2023 (no aug)                 +1.89  38.24
  v4R                               −7.54  40.19
  v4Rt (TIER-AWARE) ★               −0.06  38.21

Per-tier bias breakdown (v4Rt, 2025 / 2024):
  top  (D1-D6):   −0.03 / +0.14   ← raw passes through; teams already calibrated
  mid  (D7-D11):  −3.57 / −5.40   ← slight overshoot, acceptable
  bot  (D12-D17): +0.91 / +2.15   ← v4R closes the +3.75/+4.85 raw gap
```

Key empirical findings driving v4Rt (`/tmp/measure_v4_params.py`,
`/tmp/measure_star_origins.py`):
- 85-90% of "new stars" in W1 prediction are RETURNERS who improved, not true rookies
- True-rookie star rate is only ~10% for 9-18 bands, ~28% for 8U top tier
- Top-tier teams have ~10 above-p50 swimmers per band; bot-tier has ~4-5
- Returner upgrade modeling (multipliers on existing times) FAILS catastrophically
  because of the ghost-roster problem — many 2024 swimmers don't return, and
  upgrading ghosts inflates opp by −76 bias
- The tier-aware rule wins because top-tier 2024 rosters are already complete
  (no augmentation needed) while mid/bot have real rookie gaps to fill (v4R helps)
```

## Estimated noise floor

Empirical estimate from earlier session: ~28-29 pts Score MAE is the irreducible noise floor (race-to-race variance, conditions, etc.). We're currently at 31.90; with coverage fix we land at 34.50. That puts us within ~5 pts of the noise floor on MAE — and bias is the more important metric to keep moving.

## 8U opponent fill (2026-06-03)

**Problem:** at W1 we know our own 8U (ladder) but model the opponent's unknown 8U.
The original symptom was a sweep (SHB took ~7/8 of 8U) because the v5 predictor
under-fielded the opponent (1–2 swimmers in breast/fly). Fixed with a **hybrid
fill**: keep the opponent's REAL 8U swimmers, fill empty slots with division-typical
synthetic swimmers (`_hybrid_fill_opp_8u` in app.py).

**Calibration (data-derived, not guessed):** `build_8u_div_fill.py` measures, per
division from 2021–2024, (a) the percentile a typical team's 1st/2nd/3rd 8U swimmer
occupies in the division pool, and (b) `fill_n` = the typical # of 8U finishers a
team fields (turnout). Bottom divisions (10–17) field ~2, not 3 → fill to 2.
Bottom-tier fills also shifted slower by a 0.20 percentile offset (real W1 bottom-div
8U is rookie-heavy/slower than the historical pool). Written to `w1_8u_div_pcts.json`
as `[p_fast, p_med, p_slow, fill_n]`.

**Validation (faux-ladder, W1-exact, n=98):** aggregate 8U bias ~ -2.0, MAE ~7.1.
Most divisions within ±5; residual top-division scatter (div 1/4/9) is n=6 noise.

**HARNESS LESSON (important):** the hybrid only fills 8U events present in the
`events` list it's handed. Production passes the **union** of both teams' events
(your_dated | opp_dated), so our ladder's 8U puts 8U in the list and the opponent
gets filled. An early faux-ladder harness passed **opponent-only** events, which
left teams with no pre-W1 8U races fielding NOBODY → phantom blowouts (the "D1
+19.8" panic was entirely this bug, not a production problem). Any future 8U
validation MUST pass union events.

### Open follow-ups
- **DQ vs no-show in turnout (operator-noted):** `fill_n` counts swimmers who
  *finished* (have a time). A chunk of the thin bottom-division/8U-technical-stroke
  turnout is almost certainly DQs (entered 3, one DQ'd → 2 finishers), not absences
  — supported by breast/fly finishing ~2.2 vs free/back ~2.8. This does NOT bias the
  scoring model (a DQ'd swimmer scores 0, identical to a no-show, and we measure
  finishers), but it adds **meet-to-meet variance** a fixed `fill_n` can't capture
  (a team that usually fields 3 may field 2 this week on a DQ). Contributes to the
  irreducible ~7–8 pt 8U MAE; only the real roster could remove it.
- **Top-division per-division calibration** needs more validation data than n=6
  meets/division to pin down (multi-year). Current values are structurally derived
  and well-behaved in aggregate; don't overfit the n=6 extremes.
