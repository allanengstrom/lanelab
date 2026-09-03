# Calibration Investigation — Full Handoff (2026-06-09)

> **SUPERSEDED 2026-06-10: read `CALIBRATION_STATE.md` first.** It has the
> current targets, the production-basis baseline, the MDB rulebook, the
> staircase attribution, and the full accepted/rejected change list. This file
> remains as history; several of its recommendations (age-up ≈0.994, the §6
> list) were later tested league-wide and REJECTED — see CALIBRATION_STATE §6.

**For a fresh agent.** This documents an overnight stats run + a deep calibration
investigation. **NOTHING from this investigation is wired into production** —
`app.py`/`Optimizer.py`/`prod_eval.py` are clean vs git (last prod commit: `eb6d461`,
the 8U div-avg fill + DQ model from the prior session). Everything here lives in
standalone analysis scripts + caches. Read this before re-deriving anything: several
plausible theories were **tested and refuted** — don't re-chase them.

---

## 1. The three-number framework (core conceptual result)

For each meet side, with `truth` = the team's actual final score:

| metric | definition | measures |
|---|---|---|
| **recommended bias** | pred(optimized lineup) − truth | what the app user sees |
| **calibration bias** | pred(coach's ACTUAL lineup) − truth | pure model accuracy |
| **in-model value-add** | pred(optimized) − pred(actual) | optimizer's claimed improvement |

Identity: `recommended = calibration + value-add` (two legs of the same trip).

**Measured (488 sides, 2025 W1–W5, full league backtest):**

- recommended bias **+8.4** (looks healthy)
- calibration bias **−15.1** (model under-predicts real lineups every week)
- in-model value-add **+23.5** — but the REAL value-add (beat-coach on actual
  times) is only **+6.95**, so the in-model number is winner's-curse inflated ~3.4×

→ The healthy-looking +8 is **two ~20-pt errors cancelling** (−15 + 23). They are
coupled: "fix" one without the other and the displayed bias swings ±15.

**Correct targets (don't zero everything):** calibration → 0, value-add → +7
(real), recommended → +7 (earned). A +7 recommended bias is CORRECT — the
optimizer's lineup genuinely is ~7 better than the coach's.

## 2. Overnight stats run results (OVERNIGHT_REPORT.md, cache: overnight_cache.jsonl)

Per-week: W1 rec bias −2.9 / W2–W5 ≈ +11. Calibration −18 (W1) → −11 (W5).
Validated: **8U band bias −0.74** (prior session's work paid off), **relay +0.5**
(essentially perfect), **v5 crash rate 0%**, Jaccard 0.19→0.56 W1→W5.
Divisions 1–15 fine; **div 16–17 blow up** (MAE 47–55, rec bias +20/+27).
Win-prob: W1 shipped constants fine (Brier .241); **W2–5 k should be ~0.78, not
the shipped 0.455** (refit on production margins; Brier .183→.166). Open item.

## 3. Theories TESTED AND REFUTED (do not re-chase)

All testable offline via `overnight_opt_cache.jsonl` (lineups + slim profiles per
side, re-scorable) and `freshness_cache.jsonl` (same + source labels + has_current).

1. **"Opponent modeled too strong / phantom over-fill."** Looked compelling:
   calibration −2.7 vs strong opponents but −34 vs weak. BUT:
   - v4Rt phantom injection is already DISABLED (w1_predictor.py, since 2026-06-03).
   - Opponent profiles are ~74% fabricated entries (imputation/coverage_blend) for
     weak AND strong opponents alike — fabrication % uncorrelated with error.
   - Decisive: rebuilding opponents with ONLY real entries made calibration WORSE
     (weak −29.7 → −33.7). **Opponent strength is not the cause.**
2. **"Win-probability regression"** (probabilistic scoring under-credits favorites).
   Deterministic rank-by-mean scoring gives the SAME calibration as MC (−16.1 vs
   −15.7, identical per week). **Refuted — it's a mean/time problem, not variance.**
3. **"Variance shape"** — narrowing swimmer std does narrow the strong/weak spread
   in the right direction but only ~2 pts at 0.6×; widening helps value-add only
   ~5 pts at 3×. **Real but far too weak to matter.**
4. **"Symmetric seed-freshness boost"** (both teams' stale seeds improved):
   makes calibration WORSE (−7.8 → −11.6 at 0.94) because boosting is symmetric
   and the opponent has more stale entries. **Refuted.**
5. **Anti-compression / regression of pred on truth**: slope is 0.785
   (over-dispersed, not compressed); expanding predictions worsens MAE. **Refuted.**

## 4. What the backtest calibration gap ACTUALLY is

Scoring the coach's actual swimmers at their (stale, 2024-based) seeds under-ranks
them ~12 pts even vs correctly-modeled strong opponents, ~24 vs weak. The model's
own swimmers outperform stale seeds on race day (improvement + coach knowledge).
**This is mostly a BACKTEST ARTIFACT**: in production the user uploads a current
ladder (fresh times), so this specific under-prediction largely doesn't occur.
Evidence: gap shrinks −21.6 (W1, all-stale) → −10.1 (W5, freshest); and the SHBR
real-ladder test flips the sign entirely (below).

**Band-aids that DO zero the backtest bias** (offline-validated, NOT wired,
deliberately not recommended): `us_scale` ≈0.98 (our times 2% faster) zeroes
aggregate; per-week 0.965→0.99 zeroes each week; per-division scales zero each
division but re-break the week axis; an IPF week×division surface would zero both.
**None improve MAE** (~20; they re-centre, never tighten). See overnight_optimize.py.
The honest equivalent fact: ~2% uniform = the asymmetric "our swimmers beat stale
seeds" effect.

**Value-add shrink ×0.30 (+23.5 → +7) is NOT a band-aid** — it corrects the
optimizer's winner's curse, anchored to the measured beat-coach +7. Legitimate,
same family as the margin shrinkage. Candidate for wiring (display layer).

## 5. The PRODUCTION scenario (SHBR real ladders) — where the sign flips

`time_trials/shbr_weekly/W{1..5}_*.json` = real SHBR ladders. Test harness swaps
them into `time_trials/sleepy_hollow_b_r.json` (restores after).

With fresh ladder, all 5 opponents has_current=False (stale 2024):
**bias +8.2 over, MAE 13.4** — W1 +17, W2 +3, W3 +15, W4 +18, W5 −13.
(Without ladder: −31 W1, MAE 13.5 — ladder workflow validated, keep it.)

**Fixes swept on SHBR (5 meets — thin validation, be honest about this):**

| fix | bias | MAE | verdict |
|---|---|---|---|
| none | +6.3/+7.6* | 13.3 | (*two runs, MC noise) |
| **opponent age-up ×0.99 on stale seeds** | **−4.2** | **11.1** | best; zero-crossing ≈0.994 |
| presence-MC p=0.80 (absence) | −1.2 | 13.2 | centers but p=0.80 indefensible (20% no-show) |
| presence-MC p=0.90 (realistic) | +5.6 | 13.8 | defensible but does nothing |

- **Age-up defensibility:** the pipeline relabels bands but applies NO within-band
  year-over-year speed gain to stale opponent seeds. Empirical residual ≈0.8%
  (15-18 time_ratio in `w1_v4_params.json`; younger-band big ratios are mostly the
  band-change already handled). Fitted ≈0.6–0.7%. **They match** → an opponent
  age-up of ~0.7% (factor ≈0.993) is "the measured improvement we currently drop."
  Caveat: uniform age-up hurts W5 (−13 → −30 at 0.99); W5's miss is meet-specific.
- **Absence (user's theory):** mechanism confirmed (lowers over-predicted weeks)
  but next-man-up backfill makes each absence cost only ~1-2 pts, so realistic
  absence rates barely move totals. Not the main story for the +8.
- **Combo TESTED (12-config grid, shbr_combo_results.json):** presence adds
  nothing on top of age-up. Best |bias| configs (p0.95+f0.993 → −0.06; p0.90+
  f0.995 → −0.13) pay for it in MAE (~13.1–13.2) because presence drags the
  already-under weeks (W5 → −25). Age-up ALONE dominates: f0.995 → +0.9/12.6,
  f0.993 → −1.5/12.3, f0.99 → −5.5/11.3. The bias↔MAE trade lives on the age-up
  axis; presence p<1 strictly worsens MAE at equal bias. **Drop the presence
  component for uploaded-ladder weeks; pick age-up ≈0.994.**

## 6. Recommendations (none implemented)

1. **Wire the value-add shrink ×~0.30** into the displayed score (legitimate).
2. **Probably wire opponent age-up ≈0.994** on stale real opponent seeds for the
   uploaded-ladder path (combo grid says don't add a presence component; ideally
   validate on more teams' ladders first — 5 meets is thin).
3. **W2–5 win-prob: DONE 2026-06-09 — but NOT as k≈0.78.** The 0.782 number came
   from `np.polyfit` (slope of a fit WITH an intercept, intercept then discarded)
   on the non-deduped cache; evaluated honestly it has WORSE bias than shipped
   (+0.089 vs +0.060). Refit properly on 390 deduped sides: an intercept probit
   (same family as W1) dominates — Φ(−0.2737 + 0.01122·margin), 5-fold CV Brier
   0.164 vs 0.184 shipped, bias −0.006, stable per week. Wired as `_w25_winprob`
   in app.py (replaces `_shrunk_winprob`/WINP_SHRINK_K). The intercept absorbs the
   ~+24 value-add margin inflation; margin 0 → 39% is correct, not a bug. If a
   margin shrink is ever fed into the win-prob input, refit these constants.
4. **Leave the backtest calibration alone** — artifact; don't ship us_scale surfaces.
5. Div 16–17 MAE (~35) is irreducible roster volatility; document, don't knob.

## 7. Artifacts map

| file | what |
|---|---|
| overnight_stats.py / overnight_cache.jsonl / overnight_report.py / OVERNIGHT_REPORT.md | main 488-side stats pass + report |
| overnight_optimize.py / overnight_opt_cache.jsonl / overnight_opt_results.json | re-scorable cache + us_scale/opp_p sweeps |
| build_freshness_cache.py / freshness_cache.jsonl / freshness_loop.py | source-labelled cache + symmetric-freshness refutation |
| ipf_calibrate.py | (killed mid-run) IPF week×div surface — abandoned as band-aid |
| overnight_ladder.py / overnight_ladder_results.jsonl | SHBR with/without-ladder test |
| shbr_ageup.py / shbr_ageup_results.json | opponent age-up sweep (production scenario) |
| shbr_presence.py / shbr_presence_results.json | absence/presence-MC sweep (production scenario) |
| w1_8u_revalidate.py, build_8u_div_avg.py, build_dq_rates.py | prior-session 8U validation/builders |

## 8. Session 2026-06-09 PM: combo sweep + cross-team validation (shbr_combo.py, annandale_combo.py)

**SHBR combo sweep** (12-pt grid, p∈{1,.95,.9}×f∈{1,.995,.993,.99}, shbr_combo.log):
baseline reproduced (+6.65/13.30). **Age-up alone f=0.995 is the winner: bias +0.86,
MAE 12.55** — near-zero bias AND best MAE-per-complexity; its value is league-derived
(w1_v4_params time_ratios ≈0.5–0.7%/yr), so SHBR only confirms, doesn't fit. Combos
with presence-MC also zero bias (p.95×f.993 → −0.06) but always at worse MAE; presence
alone (f=1) moves bias ≤1–2 pts (backfill makes absences cheap — confirmed again).
W5 stays the outlier (−15 baseline → −23 at f=.995); meet-specific, don't tune to it.
A refined-grid rerun (shbr_combo_refined.log) is TAINTED — two concurrent
shbr_combo.py instances raced on the shared ladder backup; one deleted the other's
.bak and the ladder itself (restored from git, cedffc0). Never run two SHBR
harnesses at once — or better, give each a unique backup suffix.

**Annandale (the only other real ladder) CANNOT validate the knobs** — it exposes a
bigger fish. All 5 Annandale 2025 meets: rec bias ≈ **+170** (pred ~330–353, truth
150–184), identical in the overnight backtest (so not a harness artifact; age-up
barely moves it). Decomposition via overnight_cache pred_actual:
calibration bias only ~+23 (W1 +16 … W5 +45) — **~150/meet is pure optimizer
value-add fantasy**. Cause: profile pool has 150–174 names but the coach fields ~72
swims (~60% of lanes; ~10 events single-swimmer) — the optimizer fills empty lanes
with swimmers who never show up. Annandale IS the div-16 blowup signal (5 of the 8);
"div 16–17 irreducible volatility" (§6.5) is the WRONG diagnosis — it's systematic,
measurable **roster participation**, not noise.

**Implication / new idea — participation-aware value-add:** estimate per-team
availability from history (fielded swims ÷ 120, recent meets; Annandale ≈0.6, healthy
teams ≈0.9+) and (a) gate the optimizer pool or presence-p by it, (b) scale the
displayed value-add by it instead of a single global ×0.30 (which is the league
*average* of exactly this effect — Annandale needs ~×0.1). Fixes div 16–17 without
touching divisions 1–15. League-wide, measurable, no SHBR-fitting.

## 9. Session 2026-06-09 late PM: production-basis rebuild (mock ladders)

**Decision: recalibrate everything against the forced-upload PRODUCTION scenario**
— every team uploads a ladder; backtest must mimic it (asymmetric: evaluated side
fresh, opponent stale). Steps 2–4 of the calibration plan wait for this baseline.

**Landmines found (do not re-trip):**
- `time_trials/annandale.json` was SHBR's swimmers labeled "Annandale" (100/102
  name overlap) — the §8 "cross-team validation" was SHBR-vs-SHBR; its knob
  numbers are tainted. File renamed to `.mislabeled_shbr_copy`. SHBR weekly is
  the ONLY real ladder ground truth.
- `venv/bin/python` lacks sklearn → coach_predictor silently disabled (log line
  "No module named 'sklearn'"). All documented baselines used SYSTEM python3.
- Profile stroke keys are `'50-free'`-style (use `Optimizer.parse_event`), NOT
  bare `'free'` — an early mock_baseline run had empty pred_actual from this.
- `leaders_cache.json` already injects every team's in-season A-MEET times (date-
  gated) into backtest profiles — a ladder's unique add is TIME-TRIAL + B-meet
  times. The W2-5 "freshness" story is therefore mostly about W1/TT.

**Built (all validated, see file headers):** `build_mock_ladders.py` (TT layer
for all 101 teams; SHBR-fit ratios: same-band 0.98, 8U→9-10 1.98, newcomer
1.14×first-race), `validate_mock_ladders.py` (returners med −0.2% vs real TT;
newcomers +8.9% — thin n=4 fit), `shbr_mock_ab.py` (prediction-level: mock
within 5.1 pts of real-ladder predictions vs 13.0 for none; W1 2.6),
`mock_baseline_eval.py` + `mock_baseline_report.py` (986-side production-basis
baseline; running overnight → `mock_baseline_results.jsonl`).

**Participation measured league-wide** (`participation_rates.json`, report .md):
2025 mean 0.890, Annandale 0.613 (anchor held), div 16–17 concentrate the tail,
y-o-y r=0.964, within-season std 0.026 → ONE per-team scalar suffices.
`participation_prior_2025.json` = leakage-free prior (2024 rate, fallback 2023);
predicts 2025 with MAE 0.021. Ready for participation-aware value-add.

**Early partial signal (divisions 1–8, n=226, PRELIMINARY):** production-basis
recommended bias ≈ +28 (W1 +54 → W5 +15), far above the old basis +8.4 and the
SHBR-only test +8. If it holds on the full league with the fixed decomposition,
production over-prediction is much larger than the SHBR test suggested — the
value-add shrink becomes even more important. Win-prob will need refit on the
new margins (report script section 4 does it; shipped _w25_winprob showed
bias +0.08 / refit b0≈−0.91 b1≈0.0205 on the partial — REFIT ON FULL DATA).

Gotchas for re-running: presence-MC is gated W1-no-upload in app.py (~line 2591);
`_presence_adjusted_rows(p=...)` is sweepable. SHBR harnesses MUST restore the
ladder file (try/finally). prod_eval mirrors but is not identical to the live app.
Background runs: use nohup+disown, write progress to a log, expect ~0.7s/side for
profile-only caches and ~15-20s/side for full predictions. macOS has no `timeout`.
Dedup caches on (week, meet_id, side) — concurrent restarts create duplicate lines.
