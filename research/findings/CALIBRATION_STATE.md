# Calibration State — 2026-06-13 (WIRED into app_calibrated.py)

## 0.0 SHIPPED TO app_calibrated.py (clone of app.py; production app.py UNTOUCHED)

The validated stack now lives as real code in `app_calibrated.py`. To go live:
diff it into app.py or point the server at the clone. Four changes:

1. **Relay sharpening** — `_build_relay_results` RELAY_STD_SCALE default 0.5
   (relay leg stds ×0.5 so the MC predicts the sweeps that actually happen in
   lopsided meets; 41% of the opponent-strength residual). Env-overridable.
2. **Event-universe** — `_run_and_cache` unions all 40 standard league events
   into the event list so lopsided matchups don't silently 0-0 uncontested
   events. Cannot hurt (empty events stay 0-0). ~4% of the residual.
3. **Display calibration layer** — `_run_and_cache`, after win-prob: subtracts
   the per-week value-add inflation (total_adj −44/−31/−29/−30/−26 W1→W5) from
   the displayed total, our_median, and margin together, then recomputes the
   win prob from intercept probits on the CALIBRATED margins. Constants in
   `calibration_constants.json` (built from sweep_v5a.jsonl, data-repaired,
   488 sides) — code reads the file, so re-tuning needs no code change.
   The optimizer's LINEUP is never altered; only displayed expectations move.
4. **Data repair** — `nvsl_meet_history.json` (shared by both apps) had 28
   name-swapped meets across 2021-2025 repaired (`repair_name_swaps.py`;
   backup .pre_swap_repair.bak). This is the biggest single accuracy win.

NOT wired (by design): the B-meet synth layer (mock_ladders_v5a) is BACKTEST
infrastructure — production gets real uploaded ladders, so there is nothing to
wire; it only existed to make the backtest faithful. The win-prob intercept is
NOT origin-forced (margin0→~33%): the residual is real opponent-side inflation,
and an option-2 strength term is UNKNOWABLE pre-meet (slope collapses to ~0 when
refit on predicted/division strength) — documented, not shippable.

## 0.01 FINAL v5a SCOREBOARD (data-repaired, production-feasible)

488 sides. League bias +6.84 (target +7), **MAE 17.58, medAE 14.20**
(campaign start 23.35/17.3 → −25% MAE on the honest production-feasible basis;
the 14.4 figure required the unknowable strength term — oracle view only).
Per-meet |err|: p50 ±12, p90 ±28 (this is VARIANCE — who-shows-and-swims-fast —
only live attendance data touches it, not any constant).
Weeks vs +7: W1 +3.1, W2 +2.7, W3 −3.4, W4 −4.3, W5 +1.0 (all ~at the
week-level detection floor). v5a chosen over v5b (v5b over-corrected W1 to +7).

## 0.012 THE 420-RECONCILIATION (2026-06-13) — the principled fix for div-1-2/W1-2

User's insight: NVSL dual meets are zero-sum at 420 points (verified: 61% sum
to exactly 420, median 420; sub-420 = uncontested/empty events). We were NOT
enforcing it. Key facts:
- Scoring BOTH teams' real lineups, the model TOTAL is near-perfect (416.3 vs
  true 416.6). The div-1-2 +8 over-prediction is a pure MIS-SPLIT: we over-
  credit the strong team and under-credit its opponent, but the sum is right.
- Both sides' independent predictions share the same opponent-under-modeling
  inflation, which CANCELS in the ratio. So the de-biased split = the ratio of
  the two teams' fair (un-optimized) scores.

THE FIX (validated on the both-sides backtest, sum420h.py): per meet, compute
each team's FAIR score (predicted lineups head-to-head, no optimizer), split
the meet total by that ratio with a DOWNWARD-ONLY 420 cap (never inflate
sub-420 meets — protects low-participation div 17), then re-anchor +7 per week:
  MAE 17.10 → 16.02 · p90 35.2 → 31.8 · division spread 3.37 → 1.39 ·
  per-week dev +3/+3/−3/−4/+1 → FLAT · div 1-2 +6.7 → ~+2.5 · div 17 −4.3 → −1.6.
Fixes div-1-2 AND the W3-4 dip AND tail variance at once. NO per-team fitted
params (only the 420 law + existing per-week +7), so it generalizes — unlike the
opp-division correction (§0.013) which failed CV. Meets both user criteria
(scores reconcile to ≤420; per-event distributed proportionally).

PRODUCTION-FAITHFUL VALIDATION — FAILED (2026-06-13). The both-sides result used
REAL lineups. The production split must use PREDICTED lineups (fair_us/fair_opp =
both v5-predicted lineups head-to-head). On the lite sample, v5's lineup-
prediction noise (~52% Jaccard) injected MORE error than the mis-split it
corrected: full recon MAE 21.3→24.0 (p90 40→52); every blend neutral-to-worse;
the per-meet value-add version cancels the split back to baseline. DO NOT SHIP.
The conservation law is real but NOT exploitable until opponent-lineup
prediction improves (the v5 ceiling is ~52%, absence-limited — V5_CEILING_FINDINGS).
Same failure mode as the opp-division correction (§0.013): great in-sample /
on real lineups, killed by the noise of production-knowable inputs. Lesson
logged: validate every display correction on PRODUCTION-KNOWABLE inputs, not the
idealized backtest. (Full 488-side run skipped — lite is the favorable case for
recon, lopsided meets where mis-split is largest, and it already failed.)

## 0.008 PARTICIPATION-AWARE SHRINK — fixes div 17 (2026-06-15, SHIPPED)

Diagnosed the §0.009 div-17 problem: low-participation teams (Pinewood 0.24,
Edsall 0.41) field ~40-76% of their lanes, but the optimizer fields a full
lineup → it credits phantom no-show swimmers. Value-add fantasy scales with
emptiness: VA = 98.7 − 66.7·participation (r=−0.48); div 17 VA≈64 vs league 39.
The flat per-week shrink removed only the league-average 39, leaving div 17 +15.
FIX: participation-aware shrink — VA_est = b0 + b1·participation (prior-year
fielded-swims/120, computed inline from history; stable r=0.96, leakage-free),
replacing the flat total_adj. Combined with the strength-split + reanchor:
**MAE 19.84→19.33, division spread 4.50→2.20, div 17 +15.3→+4.5, weeks flat.**
CROSS-VALIDATED (fit on train half, eval on test half): beats the flat version
on held-out MAE AND divspread in BOTH folds; VA-fit slope stable (−63/−82, same
sign/magnitude — not the opp-division 15-vs-3 swing). Wired: app._team_participation
helper + _va_fit constants. END-TO-END validated through the shipped app helpers.

## 0.009 END-TO-END VALIDATION — two honest corrections (2026-06-15)

Validating the SHIPPED app.py path (not the analysis scripts) found two things:

1. **RELAY/FULL-TOTAL BUG (fixed).** The calibration block subtracted constants
   fit on the FULL meet score (individual + relay) from `mc_total`, which is
   INDIVIDUAL-ONLY (relay added separately for display). The strength-split then
   blended a full-meet score against an individual-only total — unit mismatch.
   Fixed: calibrate `full = mc_total + relay_exp_pts`, carry the delta on
   mc_total + margin/median. Constants' reanchor recomputed on this basis.

2. **METHODOLOGY: all prior heatmaps were OPTIMISTIC by ~2 MAE.** They used a
   MULTIPLICATIVE shrink anchored to `pred_actual` (the coach's ACTUAL lineup
   score) — which DOES NOT EXIST at predict time (the meet hasn't happened). The
   app correctly uses the FLAT shrink (`pred − const`), production-honest but
   higher-variance. PRODUCTION-HONEST numbers (flat shrink + strength-split,
   full-total): **MAE 19.84** (not 17.6), divspread 4.5 (not 2.0), bias 0,
   weeks flat. Campaign start (raw pred) was 23.4, so the real gain is ~15%.
   The strength-split still helps on the honest basis (20.89→19.84, flattens
   weeks) — MORE than on the optimistic one, since flat shrink has more variance.

3. **NEW honest problem: div 17 over-predicted +15.** The flat shrink can't
   remove the weak-team participation fantasy (the multiplicative one did, via
   low pred_actual). No split weighting/power fixes it (the flat-shrink term is
   55% of the result). div 16-17 participation issue is BACK on the honest basis.

PATH TO ~17 MAE + div-17 FIX IN PRODUCTION: predict OUR team's coach lineup
(v5/coach_predictor already predict lineups) and score it as a per-meet
`pred_actual` ESTIMATE, then use the MULTIPLICATIVE shrink. This recovers the
optimistic accuracy AND removes the participation fantasy per-meet, using only
predict-time data. Biggest remaining improvement; needs its own validation.

## 0.011 420 RESCUED via DEMONSTRATED-STRENGTH split (2026-06-15)

Re-diagnosed the 420 failure: the production "fair split" used ONE head-to-head
sim of predicted lineups, whose two totals are COMPLEMENTARY (sum=420) — no
independent 2nd estimate, nothing cancels. The cancellation needs two
INDEPENDENT strength estimates. Fix: estimate each team's strength from
DEMONSTRATED results (prior weeks' actual scores — lineup-free, sidesteps v5
noise), split 420 by that ratio + value-add, per-week reanchor.
Causal (prior-weeks-only, W2-5; W1 left as-is since prior-YEAR is too weak):
45% blend → division spread 3.37→2.17, div 1-2 +6.7→+3.8, WEEKS PERFECTLY FLAT,
MAE 17.10→17.55 (+0.45 cost). Production-honest, NO per-team params (CV MAE
stable). A real bias/variance CHOICE: flatter divisions+weeks for ~0.45 MAE.
NOT yet wired — offered to user. Needs prior-week scores at predict time (the
app would read posted in-season results) + a full production-faithful run.

## 0.013 W1-2 / div-1-2 forensics (2026-06-13) — why they're still worst

Examined the worst meets directly. Findings, in order:
- **Scoring-cap hypothesis REFUTED**: reconstructing actual scores from places
  (5-3-1, no per-team cap) is flat across divisions; div 1-2 sweep LESS than
  low divisions (6.2% vs 7.6%). No missing NVSL scoring rule.
- **Not a data bug**: all worst div-1-2 meets have 100% lineup-vs-leaders
  overlap (swap repair holds).
- **Root cause = opponent under-modeling on TWO axes of the same mechanism**:
  (a) division axis — strong opponents (div 1-2) imputed toward league mean =
  too weak, so we over-predict OUR score against them (calib +8.2 vs div-1-2
  opponents → −3.4 vs div-12-17); (b) week axis — W1-2 opponents have no current
  season data (stale/imputed), so the same effect peaks early (calib W1 +3.1 →
  W4-5 −1.6). The worst meets are W1 blowout LOSSES (e.g. Donaldson 114 vs
  Tuckahoe 306): when the opponent has a big day, our side is shut out of places
  more than any model predicts — variance, not correctable bias.
- **Opponent-DIVISION display correction TESTED AND REJECTED**: full-data it
  looked great (div 1-2 +6.7→0.0, divspread 3.37→2.14, MAE neutral) BUT
  team-holdout CV exposed it as OVERFIT — tier-1 offset 15.3 (fold 0) vs 2.7
  (fold 1), and out-of-sample it makes held-out div 1-2 WORSE (+2.7→−12.6).
  The div-1-2 mean is driven by a few teams (Kent Gardens n=2; Donaldson Run
  decaying 47→−2 = staleness; one Overlee +73 meet), not a stable law. DO NOT
  ship a per-opp-division offset.
- **Per-week displayed-bias reanchor TESTED AND REJECTED**: zeroes week bias by
  construction but MAE 17.6→21.2 — the inflation is PROPORTIONAL (per-meet
  value-add), so only the multiplicative shrink is correct; a flat per-week
  offset over-corrects calm meets. W1-2 +3 warmth is calibration leak through
  the value-add anchor and is NOT cleanly removable.

**Verdict**: W1-2 / div-1-2 residual is irreducible opponent-modeling variance,
largest exactly where opponents are strong and data is stale (W1, no current-
season data exists for anyone). The one PRINCIPLED untested lever is
DIVISION-conditioned opponent IMPUTATION (anchor imputed opp swimmer times to
division-typical strength, per-swimmer — not a per-meet display fudge), which
might generalize where the display correction didn't. Speculative; not done.

## 0.02 REMAINING FUTURE WORK (specced, not done — both bigger than tuning)

1. **Improver-bias model fix**: prior-year-anchored seeds under-predict teams
   that jumped (Mansion House −23, Vienna Aquatic −23, Stratford −23; bias =
   0.4 − 0.21×ppg-improvement, r=−0.59). A model-side improvement factor (we
   have the within/across-season improvement gradients already). The remaining
   persistent per-team tail is entirely this class — no longer data corruption.
2. **Live absence / roster-upload UX**: the oracle showed perfect lineup
   knowledge is worth −4.4 MAE — the only lever that touches per-meet VARIANCE.
   This is product work (the `absent` input + SwimTopia rosters), not modeling.
3. **Scraper fix** (`scrape_history.py` _assign_codes_to_teams): repair fixed
   the DATA; the scraper will re-corrupt on next scrape. Use a league-wide
   modal-code→team map + a lineup-vs-leaders overlap assert (clean teams 99%+,
   corrupted 51-62% — zero-false-positive detector).

---

# Calibration State — 2026-06-10 (FINAL: measurement campaign complete)

## 0.1 FINAL CONFIG & SCOREBOARD (evening session)

Validated jointly (final basis runs): **relay std ×0.5 + event universe +
B-meet v4 ladders** (v3 recentered ×0.9753, June-9 entries dropped — they
leaked a 2.5% W1/W2 seed boost), + per-week value-add shrink + (pending user
OK) the option-2 opponent-strength display term (removes the residual
+3.03/10 slope; −2.2 MAE).

Measured end state (spliced v4 W1-2 + v3 W3-5, with option 2):
**league MAE 14.89, medAE 12.43** (campaign start: 23.35/17.3 → −36%).
Weeks vs the +7 earned target: W1 −0.7, W2 −3.2, W3 −4.0, W4 −6.1, W5 −1.0 —
all within or near week floors; W3/W4 keep a mild shared negative lean (the
unsynthesizable B-meet residue: kids with zero data anywhere). Sign splits:
W1 9+/8−, W2 8+/9− (textbook); W3/W4 2+/15− (honest residual).
Remaining known blemishes, documented not chased: div 1 row ≈ +6 over target
(elite-meet structural residual, only partly the linear slope); ~4 boxed
cells at chance rate; staircase floor ≈ +3.0 raw / ≈0 after option 2.

REJECTED THIS SESSION (tested, do not re-chase): opponent-presence MC
discounting (broke W2 +12 via thin-pool backfill — prerequisite: W2
pool-coverage fix; slope value was nil beyond relay anyway); B-meet v2
un-recentered (+2.5% slow synth times × recency weighting DRAGGED profiles
−12..−16 — per-entry validation passes ≠ profile-level pass).

WIRING STATUS: everything still flags/harness/analysis-layer EXCEPT the W2-5
win-prob probit (committed, needs refit on final margins). Wiring pass
designed (one commit per piece) — awaiting user calls on (a) option-2
strength term, (b) win-prob intercept-vs-origin.

(updated late PM: lite ablation + oracle)

## 0.5 Lite ablation results (44-meet stratified sample, paired vs baseline)

| config | staircase slope/10 | centered MAE | verdict |
|---|---|---|---|
| baseline | +3.27 | 24.08 | |
| event-universe | +3.21 | 24.27 | tiny, as predicted (4%) |
| relay std×0.5 | +2.87 | 23.04 | works; ×0.25 is WORSE (non-monotone) |
| opp presence (team-rate MC) | +2.95 | 23.01 | works; bias shift +4.9 is mostly LEGIT (see oracle) |
| combo (all 3) | +3.01 | 23.22 | sample too noisy to rank (slope SE ≈ ±0.5) |
| **ORACLE (true opp lineups)** | **+2.55** | **19.52** | upper bound of a perfect v5 |

Key reads: (1) measured fix effects are ~1/3 of the decomposition-predicted
shares — real, right sign, smaller; (2) even PERFECT opponent composition
leaves slope ≈ +2.55 — the rest is structural rank/MC compression, so the
honest end-state slope is ~+2.2–2.5 without engine surgery; (3) the oracle's
own bias shift (+5.0) shows v5 over-fields opponents league-wide — presence-
induced upward bias shifts are truth-ward and get absorbed by the anchor refit;
(4) perfect composition is worth −4.4 MAE (−18%) — mostly per-meet variance
only live absence info can capture → strongest case for the absent-input UX.
Full 488-side run of combo (relay 0.5 + events + presence shift .04) →
mock_fixes_full.jsonl. B-meet layer build delegated (mock_ladders_v2/).

The single source of truth for where calibration stands, what's proven, what's
rejected, and what's left. Supersedes the per-experiment narrative in
CALIBRATION_INVESTIGATION.md (kept for history). Read this first.

## 0. The two targets (do not confuse them)

- **pred_actual − truth → 0** ("calibration"): the coach's ACTUAL lineup scored
  by the model vs what it really scored. Pure model accuracy. Currently ≈ 0
  league-wide on the production basis.
- **displayed − truth → +7** ("recommended bias"): we predict the OPTIMIZED
  lineup; backtest truth comes from the coach's worse lineup. The optimizer's
  real improvement is +6.95 (beat-coach on actual times), so a calibrated
  display SHOULD beat backtest truth by ~+7. Zero here would mean the optimizer
  adds nothing. If a user follows our lineup, the +7 materializes in their
  score and displayed − their_truth → 0.

## 1. The measurement foundation (production basis)

Backtests now mimic production: every evaluated side gets an uploaded ladder
(synthesized "mock ladder"), opponent stays stale. Asymmetric by design.

- `build_mock_ladders.py` — synthesizes the time-trial layer for all 101 teams
  (SHBR-fit ratios; same-band returners ×0.98, 8U→9-10 ×1.98, newcomers ×1.14
  of first race). A-meet times already flow through leaders_cache (date-gated).
- Validated: per-swimmer (returners median −0.2% vs SHBR's real TT) and
  prediction-level (`shbr_mock_ab.py`: mock within 5.1 pts of real-ladder
  predictions vs 13.0 with none; W1 2.6).
- `mock_baseline_eval.py` → `mock_baseline_results.jsonl` (488 sides, 2025
  W1–W5, zero failures). Knobs: OPP_AGEUP, WEEKS, RESULTS_FILE, and
  TEAM_COND_IMPUTE (app.py, default off). `mock_baseline_report.py` reports.
- KNOWN GAP: mock ladders lack B-meet times → evaluated side under-credited
  late season (see §4, W3–5 drift).

## 2. Raw production-basis baseline (uncorrected)

Bias +30.9 / MAE 33.7 overall; W1 +55 → W5 +17; div 16–17 worst (+38/+50).
Decomposition: calibration −1.6 (model honest!), value-add claim +30 (W1 +45)
vs real +7 → the over-prediction is ~all optimizer winner's curse.
Old stale-seed basis for comparison: bias +8.4 / MAE 23.35 — that +8.4 was two
errors cancelling (−15 calibration + +23.5 inflated value-add).

## 3. Statistical rulebook (bias_mdb_findings.md)

Minimum detectable bias (clustered bootstrap; sides of a meet are NEGATIVELY
correlated r=−0.35): league ±1.7, week ±1.4–4.8, division ±2.8–10.7 (median
~6), opp-strength bucket ~±4, division×week cell ~±15 (66/85 cells sit below
their own floor — NEVER chase individual cells). FDR-corrected survivors on the
corrected data: the week-level drift, division 1, and above all the
opponent-strength staircase. Diagnosis fingerprints: shared offset → sign
test/aggregation; conditional bias → trend test vs covariate (aggregate hides
it); isolated cells → noise unless they survive FDR.

## 4. The three real remaining miscalibrations

1. **Opponent-strength staircase** (dominant): corrected error runs −21 vs weak
   opponents (<170) to +17 vs elite (≥230); slope +3.32/10 opp-pts, p=0.0001.
   Event-level attribution (`staircase_decomp_findings.md`, 96% reconciled):
   - 41% relay expected-points compression (MC win-probs never predict sweeps:
     weak opp actual 45.5 relay pts vs 35.1 predicted; strong 17.1 vs 25.3)
   - 34% opponent composition (weak teams' predicted entries no-show/DQ ~30%,
     handing us unpredicted sweeps; DQ'd kids are simply absent from results)
   - 10% individual-event MC rank-compression (same disease, milder)
   - 4% event-universe truncation (blowout events missing from the event union
     score as 0 — e.g. 41 real pts never scored in one meet)
   - 4% time error — REJECTED as driver (kids' modeled speeds are fine)
2. **W3–5 shared under-credit** vs the +7 target: −10.5/−13.3/−10.1, cell signs
   1+/16−, 0+/17−, 0+/17− (a shared offset, unmistakable by sign test despite
   every cell being individually sub-floor). Cause: mock ladders stop
   refreshing mid-season (no B-meet layer). Mostly a BASIS artifact — real
   weekly uploads bring B-meet times for free.
3. **Win-prob / display inconsistency**: scores shown raw (inflated), win prob
   de-biased via intercept — a +30 margin can display as <50%. Resolution
   sequence in §6 (shrink first, then origin-forced refit).

## 5. Corrected + projected results

Per-week value-add shrink alone (k_w anchored so mean displayed VA = +7;
c_w ≈ 0.13/0.17/0.20/0.22/0.26 W1→W5): league bias +0.1, MAE 17.7.
Participation hinge NOT needed on this basis (results-derived rosters can't
field no-shows — the mock basis self-applies pool-gating).
Projected after the three staircase fixes (removing 79% of the slope):
**MAE ~14.7, slope +0.7/10, every division within ±6.3 except div 1 (+8.2),
div 16 at −0.9/MAE 10.9**. W1/W2 cells split 8+/9− and 7+/10− around +7
(calibrated); W3–5 await the B-meet layer.

## 6. Change list

WIRED: W2–5 win-prob intercept probit Φ(−0.2737+0.01122·m) (`_w25_winprob`,
commit 6a72a69) — superseded later by the origin refit below.

READY TO WIRE: (a) per-week value-add shrink at the display choke point
(app.py ~2609–2680; shrink displayed total, medians, margin together; live
meets have no pred_actual → use the constants table, or later a coach-predictor
estimate); (b) THEN refit win prob through the ORIGIN on shrunken margins —
restores "higher median ⇒ ≥50%"; intercept should collapse ≈0; if it doesn't,
the shrink constants are wrong (fix them, not the probit).

TO BUILD (staircase, in payoff order): relay expectation sharpening (41%);
opponent presence discounting (34%; use the CALIBRATED per-swimmer
`presence_model.pkl` from the v5 ceiling investigation — AUC 0.79, see
V5_CEILING_FINDINGS.md — to discount expected points of predicted opponent
entries; per-team rates from participation_rates.json as fallback. NOTE from
that investigation: discount points, NEVER hard-gate the pool — gating tested
strictly worse; and presence modeling cannot improve lineup-identity (Jaccard),
only expected points); event-universe fix — always score all 40
events (4%, trivial). Then B-MEET LAYER for W3–5 (synthesize Monday entries by
walking each swimmer's last known time down a within-season improvement curve
fit league-wide from A-meet repeats by band×percentile; validate vs SHBR's real
B-meet entries; success = W3–5 within ±3 of +7 and mixed cell signs).

DEFERRED: MC rank-compression residual (~10% of staircase); participation
pool-gating for REAL uploaded rosters (they contain never-swim kids; mock
basis self-corrects, production path doesn't); per-meet VA estimate via
coach_predictor.

REJECTED (do not re-derive): uniform opponent age-up (league A/B: calibration
was already ~0; 0.995 made every week worse ~6-8 pts per 0.005 — the SHBR
5-meet "validation" was the staircase in disguise); star-weighted age-up
(improvement gradient is INVERTED: top-decile returners improve ~0.8%, bottom
quartile ~8%; W1 lineups select the stars whose stale seeds are already
accurate — selection self-corrects); team-conditioned imputation anchoring
(TEAM_COND_IMPUTE in app.py, default off: slope only 3.32→2.97, MAE worse);
participation-hinge display scaling (old-basis artifact).

## 7. Key measured facts worth remembering

- Improvement is inversely related to ability: slow kids ~8% faster YoY, stars
  ~1%. Coaches field stars first (W1 median pct 0.465 vs 0.618 later debuts).
- Roster depth/presence — not swimmer speed — is where prediction error lives
  (participation, no-shows, relay sweeps; time error = 4% of the staircase).
- Participation: league mean 0.89, Annandale 0.613, Pinewood Lake 0.245;
  y-o-y r=0.964 → `participation_prior_2025.json` (2024-based, leakage-free).
- Two sides of one meet anti-correlate (r=−0.35).
- `time_trials/annandale.json` was SHBR data mislabeled (renamed
  .mislabeled_shbr_copy); venv lacks sklearn — ALWAYS run harnesses with
  system python3; profile stroke keys are '50-free' style (use parse_event).

## 8. Artifact map (this session)

| file | what |
|---|---|
| mock_ladders/, build_mock_ladders.py, validate_mock_ladders.py | synthesizer + validation |
| shbr_mock_ab.py | mock-vs-real ladder prediction A/B |
| mock_baseline_eval.py / _results.jsonl / _report.py | production-basis harness + baseline |
| mock_ageup_995.jsonl / mock_teamz_results.jsonl | rejected-fix A/B runs |
| bias_mdb_analysis.py / bias_mdb_findings.md | detectability rulebook |
| staircase_decomp.py / _findings.md / _rows.jsonl | staircase attribution |
| participation_*.{py,json,md}, participation_prior_2025.json | participation + prior |
| participation_shrink_proto.py / _findings.md | hinge prototype (superseded) |
| mock_baseline_chart*.png / _trends*.png | heatmaps + trend charts |
