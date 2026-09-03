# Week 1 — START HERE (handoff for the W1 agent)

**You own Week 1.** Issues #1 (W2–W5 score bias), #2 (headline win-prob shrinkage),
and #3 (beat-coach "collapse") are **resolved and shipped** as of commit `4069d2f`.
Everything that's left is W1. This doc is the detailed brief: the measured state, the
architecture, everything we tried (what helped, what didn't), the traps, and a ranked
experiment plan.

> **Build on `4069d2f` or later.** `git log --oneline -1` should show the shrinkage
> commit. If your `app.py` predates it, you're on a stale tree — pull first. Don't
> re-wire issue #2; it's done.

Companion docs: `improvements.md` (full issue tracker), `PROGRESS_AND_IDEAS.md`
(session-wide findings + methodology). This file is the W1-specific superset.

---

## 0. THE GOAL

W1 is the hardest week: **no current-season race data** exists yet, so we predict off
2024 profiles + ladder/roster uploads. Two distinct W1 problems remain:

1. **Thin/empty-profile blowouts** — a handful of teams get a near-empty W1 profile →
   the opponent sweeps → ±150–250 pt errors. **Mostly addressed by yesterday's
   thin-leaders guard, but NOT yet re-measured.** (See §2, §3.)
2. **Residual systematic over-prediction on the clean cases** — once the blowouts are
   removed, we still over-field (ghosts + absences + polish inflation). Magnitude TBD
   after a clean re-run (see §2 for why the headline mean is misleading).

**Definition of done:** W1 MAE in the ~30s with **0–2 blowouts**, and the clean-case
bias within a few points of zero — *measured the right way* (§5 traps).

---

## 1. HOW W1 WORKS IN PRODUCTION (read this before changing anything)

The W1 path through `app.py::_run_and_cache` → `_build_opp_mixture`:

**Profile build (per team)** — `api_load_setup` / `prod_eval.build_profiles`:
1. Source 1: `_build_team_dated_from_leaders` (leaders_cache.json, current pre-season).
2. **Thin-leaders guard** (shipped 2026-06-05, `app.py` ~1247, 1323/1330): if a team's
   leaders coverage `< LEADERS_MIN_SWIMMERS (20)`, merge `_history_baseline` (prior-year
   record) underneath via `_merge_dated`. **Applies to BOTH your_dated and opp_dated.**
   This is the fix for the blowouts in §2.
3. Source 2/3 fallback: `_build_team_dated_from_history` (current year, then 2024).
4. Ladder merge (`_merge_ladder_into_dated`) → sets `has_current` if it added times.
5. `build_profiles_recency_weighted(decay=0.7)` → age-up correction → imputation.
   `coverage_blend` is **W≥2 only** — it does NOT run at W1.

**Opp lineup prediction** — `_build_opp_mixture` (`app.py` ~2810), W1 override at
`week == 1` (~2849), via `w1_predictor.py` (**v4Rt**, tier-aware):
- **`has_our_current_data == True`** (we uploaded SwimTopia/ladder, opp didn't) →
  ASYMMETRIC: `W1.predict_w1_lineup_mixture(..., picker="self_optimal", n_rotations=4)`.
  - Top-tier opps (**D1–D6**): raw 2024, **no phantoms** (rosters already complete).
  - Mid/bot-tier opps (**D7–D17**): add per-tier phantom rookies (v4R), calibrated from
    2022–2024 transitions in `w1_v4_params.json` + `nvsl_divisions_by_year.json`.
  - Validated: W1 2025 bias −0.8 / MAE 31.4; W1 2024 held-out bias −0.06 / MAE 38.2.
- **`has_our_current_data == False`** (no upload — most teams) → SYMMETRIC fallback:
  raw 2024 `self_optimal` for both sides. Empirical bias +1.5 to +1.9 on this mode.

**8U hybrid** — `_hybrid_fill_opp_8u` keeps opp's real 8U swimmers, fills empty slots
with division-typical synthetic depth from `w1_8u_div_pcts.json`. Validated ~−2 bias.

**Polish** — `_polish_swim_ups` (accept_threshold=0.5) then `_polish_within_band_swaps`
(accept_threshold=0.1). These optimize the MODEL score → they INFLATE the predicted
total. See §4 (didn't-fully-work) and §5 (trap).

**Score** = `mc_total + relay_exp_pts` (relays ~3 pts/win).

---

## 2. CURRENT MEASURED STATE (and why the headline number lies)

**`prod_eval_summary.txt` is STALE** — dated 2026-06-04, *before* the thin-leaders
guard. Re-run is step 1 (§6). Here's what it shows, with the right interpretation:

```
week    n     bias      MAE   medAE  blow  MAE<100
   1   24    -8.28   107.99  120.72    13    36.92    <- STALE (pre-guard)
   2   24    +0.26    16.99   ...        0           <- shipped, good
   3   24    +3.02    17.24   ...        0
   4   24    +4.32    16.72   ...        0
   5   24    +5.34    14.07   ...        0
```

**Why W1 mean bias reads −8.3 but the real problem is over-prediction:** the 13
blowouts are **symmetric pairs** (~6–7 meets seen from both sides). The near-empty-profile
team gets a huge NEGATIVE error; its opponent gets a huge POSITIVE error. They **cancel
in the mean** (−8.3) but stack in MAE (108). Examples (pre-fix):

```
Tuckahoe   vs Donaldson Run   pred  48  truth 306  err -258   <- near-empty profile
Donaldson  vs Tuckahoe        pred 331  truth 114  err +217   <- its mirror
Vienna Aq  vs Vienna Woods    pred  34  truth 245  err -211
Fair Oaks  vs Little Hunting  pred  45  truth 246  err -201
Old K.Mill vs Overlee         pred  48  truth 228  err -180
...13 total, all with one side pred 34-70 (= almost no swimmers scored)
```

**The signature `pred 34–70` = a near-empty profile** (barely any swimmers resolved →
opponent sweeps every event). This is the thin-leaders bug, and these specific teams
(Tuckahoe, Vienna Aquatic, Fair Oaks, Old Keene Mill, Hamlet, Kent Gardens, Highlands,
Wakefield Chapel) are your validation set. **The guard should rescue exactly these.**

**Beat-coach W1 (honest, actual-times + same-day-form):** `old 56% → new 81%`,
net **+18.56 pts/team** (n=16). W1 is actually our *best* beat-coach week — coaches have
the least info at W1 too, so a good model helps most. Don't break this.

**Where did "+29" come from?** Older notes cite a +29 W1 over-prediction. That was a
different slice (clean/present-roster cases, or a pre-fix measurement). **Don't trust
+29 as gospel** — re-derive it after the re-run (§6). The honest framing: there's a
*real* over-prediction on clean cases (ghosts + absences + polish), but its magnitude is
currently unmeasured on the post-guard tree.

---

## 2.6 UPDATE (2026-06-05, later session) — W1 DECOMPOSITION MEASURED

We ran experiment #1 (present-roster) and part of #2 (polish on/off) and the
ghost-vs-absence split. **Results overturn two assumptions in §3/§7 — read this
before following the ranked plan.** Harness: `/tmp/w1_decompose.py` and
`/tmp/w1_ghost_absence.py` (checkpointed jsonl; n_sim=1500; W1; n≈30 records/15 meets;
production-faithful via `prod_eval.build_profiles` + union events).

**The +29 splits like this (no-polish full roster = +25.5 at n=30):**

| Component | Contribution | Confidence |
|---|---|---|
| **Polish inflation** (FULL − NOPOLISH) | **~+1.8** | firm, stable across n=14/28 |
| **Ghosts** (FULL − RETURNED-in-2025) | **~0** | firm-ish (settled +10.9→+0.6→−1.0 as n grew) |
| **Absences** (RETURNED − PRESENT) | **~+18** | dominant, but UPPER BOUND (see caveat) |
| **Model optimism** (PRESENT residual) | **~+8** | LOWER BOUND (see caveat) |

**Two big corrections to this doc's plan:**

1. **Polish is NOT "~half" the bias — it's ~+1.8.** §7 #2 (polish-threshold sweep) and
   the §4 "polish inflation" framing overstate it. Raising polish thresholds will buy
   ~2 points of bias at most. **Deprioritize #2.** (Polish still helps the *recommended
   lineup* — keep it on; it just barely moves the predicted *score*.)

2. **Ghosts contribute ~0 to the bias — the obvious cheap fix DOESN'T work.** 24% of the
   W1 profile are ghosts *by headcount* (full 117 → returned 90), but removing them leaves
   bias UNCHANGED (+25.5 → +26.4). Why: the optimizer fields the *fastest* swimmers, and
   ghosts are mostly the kids who graduated/quit — they were never being fielded.
   **This downgrades §7 #3 (presence-weighting/ghost-removal) and #6 (roster uploads) as
   *bias* fixes** — a SwimTopia roster drops ghosts, but ghosts aren't what's inflating the
   score. (Roster uploads still help via the `absent` input for absences — see below.)

**What actually drives the +29: ABSENCES (~+18) + model optimism (~+8).** Pool attrition:
full 117 → returned-in-2025 90 (24% ghosts) → present-that-day 61 (**~30% of returners
miss any given meet**). Absences are random across the roster, so they hit your *fast,
fielded* swimmers — fielding a star who isn't there is the inflation. That's why removing
absences drops bias ~18 while removing ghosts does nothing.

**CAVEAT — the absence/optimism split isn't clean yet (don't quote exact numbers):**
present-only restricts the pool to ~61 swimmers, which is too thin to fill every event →
the optimizer under-fields → PRESENT cell scores artificially LOW. So **absence ~+18 is an
upper bound and model-optimism ~+8 is a lower bound.** To get a trustworthy split, patch
the present cell to **backfill thinned events with imputation/division-fill** (keep
coverage complete; only remove the *absent* swimmers) and run to n≈100. Until then, the
defensible claims are: **polish ≈ +2 (settled), ghosts ≈ 0 (settled), absences+optimism =
the rest (~+24), absence-dominant.**

**Implication for the roadmap:** the highest-value W1 lever is **absence handling**, not
ghost removal. Either (a) lean on the existing `absent` input (coach marks who's out
pre-meet — lineups lock in advance in NVSL, so this is realistic), or (b) build an
**expected-absence model** (down-weight each swimmer by a presence probability; ~30% of
returners miss a meet). (b) is general (helps every team, no upload needed) and directly
attacks the ~+18. Model-optimism (~+8) is a secondary profile-calibration tweak.

---

## 2.7 UPDATE (2026-06-05) — TWO PRODUCTION FLAGS in the shipped win-prob (issue #2)

A review of `4069d2f` found the shrinkage win-prob wiring is mechanically correct (erf-based
Φ, fixes all intact, no crashes) but has **two calibration problems — one is W1-specific:**

1. **W1 IS NOT WEEK-GATED — it gets the W2–W5 shrinkage constants (W1-relevant!).**
   `analytical_winp = _shrunk_winprob(mstats["margin"])` runs for every week with
   `WINP_SHRINK_K=0.455, WINP_MARGIN_SIGMA=64`. But W1 margins behave completely
   differently — measured W1 margin bias +42 (vs +12), σ≈192 (vs 64), W1-specific k≈0.07
   (vs 0.455). **The W1 headline win-prob is miscalibrated/overconfident.** When you work
   W1, either week-gate the headline (suppress or flag "W1 — low confidence") or fit W1's
   own (k, σ) once W1 bias is fixed. Coordinate with the issue-#2 owner before changing
   `_shrunk_winprob`.

2. **k/σ were fit on the wrong margin definition (affects all weeks incl. W1).** They were
   fit on `pure_greedy + race_points` margins (`test_shrinkage.py`), but production feeds
   them `strategy_robust + simulate_match (MC)` margins. Those differ — measured ratio
   across 4 meets: 0.39 / 0.42 / 1.54 / 0.25 (inconsistent; MC usually *smaller* because it
   softens blowouts). Net: the headline is directionally de-biased but likely **over-shrunk
   (too timid)**. Fix: re-fit k and σ on production `simulate_match` margins vs actual
   outcomes. (Not strictly a W1 task, but if you re-fit, do W1 separately per flag #1.)

---

## 3. WHAT WE'VE TRIED — what helped, what didn't

### ✅ SHIPPED & VALIDATED (helped — keep these)
| Change | Effect | Where |
|---|---|---|
| **Thin-leaders source guard** | Targets the §2 blowouts. Notes claim blowouts 13→5, MAE 108→38 — **NEEDS RE-CONFIRM** (the jsonl predates it) | `app.py` ~1247/1323/1330; mirrored in `prod_eval.build_profiles` |
| **v4Rt tier-aware augmentation** | bias −14 → −0.8 (2025), −14 → −0.06 (2024 held-out) | `w1_predictor.augment_v4r_tier_aware`, `_build_opp_mixture` |
| **4-rotation phantom mixture** | MAE −0.12 to −0.34 vs single-offset v4Rt; bot-tier bias tightens | `W1.predict_w1_lineup_mixture(n_rotations=4)` |
| **8U per-division hybrid fill** | 8U bias ~−2; cut SHB-vs-SHR 8U sweep 7/8 → 4/8 | `_hybrid_fill_opp_8u`, `w1_8u_div_pcts.json` |
| **Prior-band carry-forward** | Fixes age-up cases (e.g. 13-14 → 15-18 50-breast scaled, not dropped/imputed) | `build_profiles_recency_weighted` |
| **Within-band CRN polish** | +1.0 pt cross-stroke 2-opt the optimizer missed (validated SHB W1) | `_polish_within_band_swaps` |

### 🟡 PROMISING — measurement insights, not yet productized
| Insight | What it showed | Status |
|---|---|---|
| **Present-roster restriction** | Restricting the pool to swimmers who actually competed removes phantom-absence points. On W2–W5 it cut bias toward 0. **Hypothesis: a big chunk of W1 over-prediction is absences, not model error.** | **UNMEASURED for W1** — this is experiment #1 (§7). Live analog: the `absent` input in `/api/run` already exists. |
| **Same-day-form scaling** | For moved swimmers, scale stale profile by `mean(actual/profile)` over events they swam. Lifted beat-coach W1 56→81%. | In `beat_coach_v2.py` (measurement only). |

### ❌ TRIED & REJECTED (don't re-derive these)
| Approach | Why it failed |
|---|---|
| **Returner upgrade modeling** (multipliers on existing 2024 times) | **Catastrophic, −76 bias.** The ghost-roster problem: ~24% of 2024 swimmers don't return, and upgrading ghosts inflates the opp massively. This is why v4Rt adds *phantom rookies* instead of upgrading returners. |
| **Synthetic-percentile imputation at event median** | Drove bias to **−51.** Median phantoms are too competitive and flood every event. Real prior-year times are self-calibrating; that's why coverage_blend uses real 2024 times, not percentiles. |
| **Per-swimmer tapering trend** | 24% WORSE MAE — noise dominates any real slope. |
| **Uniform population taper multiplier** | 0.00 effect on placement-based scoring (everyone shifts equally → places unchanged). |
| **Multiplicative per-week correction** | A band-aid that fit away our own prediction drift. Reality is flat (~208/team every week); the "week slope" was a prediction artifact. Don't reintroduce week-factors. |
| **W2 thin-profile shrinkage** | Wash (0/10 flips, bias/MAE unchanged). The W2 gap is *missing current info*, not noise — shrinkage can't manufacture information. (Not a W1 fix, but same lesson: regularization ≠ information.) |

---

## 4. THE +29 / over-prediction — the shared root cause

The clean-case over-prediction and the (now-debunked) circular-100%-beat-coach are the
**same mechanism**: the optimizer fields swimmers that look great in the model but don't
perform in reality —
- **Ghosts**: 2024 swimmers who won't return (~24%).
- **Absences**: present roster, but out that specific day.
- **Polish inflation**: `_polish_*` bank MC-noise gains on the model score.
- **Coverage-blend stale times** (W2+, not W1).

In-model they score; on actual times they don't. **Fix the root → both bias and
beat-coach improve together.** This is why "decouple displayed score from optimizer-max"
(§7 #4) is structurally appealing — the score we *show* shouldn't be the optimizer's own
inflated self-assessment.

---

## 5. METHODOLOGY TRAPS — read before you measure ANYTHING

These cost us days. Do not re-hit them.

1. **Union events.** The 8U hybrid (and scoring) only fills events in the `events` list
   it's handed. Production passes the **UNION** of both teams' events
   (`sorted(set(your_dated) | set(opp_dated))`). A harness that passes opponent-only
   events leaves teams with no pre-meet races in a band fielding NOBODY → phantom
   blowouts. **The entire "D1 +19.8" panic was this harness bug, not production.** Always
   pass union events.
2. **Model times vs actual times.** Scoring beat-coach on MODEL/profile times is
   **circular** — the optimizer maximizes exactly that, so it "wins" ~100% by
   construction. Proof: same meets, MODEL 100% vs ACTUAL 55%. The old "95.7% → 28% W5
   collapse" was this artifact. **Always score on actual times.**
3. **Stale-profile penalty.** When your lineup moves a swimmer to an event they didn't
   swim, the stale profile under-credits them (esp. W2+). Use same-day-form scaling.
4. **Present roster.** Full-roster optimization fields absent swimmers → phantom points
   inflate BOTH bias and beat-coach. Restrict to present for honest measurement.
5. **Polish inflation.** `_polish_*` optimize the MODEL score → inflate the predicted
   total. Separate "what lineup we recommend" from "what score we predict."
6. **Symmetric blowouts hide in the mean.** As in §2, a near-empty-profile error and its
   mirror cancel. **Always look at MAE + blowout count, never just mean bias, at W1.**

---

## 6. STEP 1 — RE-RUN THE EVAL ON THE FIXED TREE (do this first)

The W1 numbers in `prod_eval_summary.txt` predate the thin-leaders guard. Before any new
work, get a clean post-`4069d2f` baseline:

```bash
# Full production-faithful score bias/MAE, all weeks (resume-safe jsonl).
# Delete the stale W1 rows first so they re-predict on the fixed tree:
python3 - <<'PY'
import json
rows=[json.loads(l) for l in open("prod_eval_results.jsonl") if l.strip()]
keep=[r for r in rows if r.get("week")!=1]
open("prod_eval_results.jsonl","w").writelines(json.dumps(r)+"\n" for r in keep)
print(f"dropped {len(rows)-len(keep)} W1 rows; {len(keep)} kept")
PY
caffeinate -i python3 prod_eval.py        # writes prod_eval_results.jsonl + _summary.txt
```

**Success check:** W1 blowouts should drop from 13 toward ~0–5, MAE from 108 toward ~30s.
If the §2 teams (Tuckahoe, Vienna Aquatic, Fair Oaks, …) still read `pred 34–70`, the
guard isn't firing for them — debug `_history_baseline` / `LEADERS_MIN_SWIMMERS` for
those specific teams (maybe they have no usable 2024 history *either* → need a
division-average fallback floor).

Then re-derive the **clean-case bias** (exclude |err|≥100) to get the true over-prediction
magnitude — *that's* your real target, not the −8.3 mean.

---

## 7. RANKED EXPERIMENT PLAN (after the re-run)

**#1 — Measure W1 present-roster bias (highest value, lowest effort). [PARTIALLY DONE — see §2.6]**
Done at n=30: present-roster bias ≈ +8 (down from +25), confirming the hypothesis —
**most of the over-prediction is absences, not core model.** Remaining work: patch the
present-cell under-fielding artifact (backfill thinned events) and run to n≈100 for a
clean absence-vs-optimism split. Then the fix is the `absent` input + presence prior.

**#2 — Polish-threshold sweep. [LARGELY ANSWERED — see §2.6: polish ≈ +1.8, not "~half". DEPRIORITIZE]**
Polish on/off measured at ~+1.8 bias contribution (stable across n). The "~half"
hypothesis is refuted. Raising thresholds buys ≤2 points; not worth the beat-coach cost.

**#3 — Presence-weighting / ghost removal [RE-SCOPED — see §2.6: ghost removal ≈ 0 bias effect].**
**Ghost *removal* does NOT reduce bias** (ghosts aren't fielded — settled at n=30). The
valuable half of this idea is the **absence** side, not ghosts. Reframe as an
**expected-absence / presence-probability model** (down-weight each swimmer by P(present);
~30% of returners miss a meet) — that attacks the dominant ~+18 absence component. Skip the
ghost-dropping; keep the returns-prior *only* insofar as it estimates per-swimmer presence.

**#4 — Decouple displayed score from optimizer-max.** Show a calibrated baseline score,
recommend the polished lineup. Clean structural fix for "whoever runs the optimizer wins."

**#5 — The remaining blowouts (after re-run).** Whatever survives the guard is likely
teams with no usable 2024 history (expansion/realign/rename). Add a division-average
fallback floor so a team never fields an empty band.

**#6 — More SwimTopia roster uploads** (data play, not modeling). A current roster +
`absent` eliminates ghosts AND absences outright. Only B&R has one today. Worth as much as
any model change.

---

## 8. FILES & HARNESSES (with correct invocations)

**Production (don't fork — edit in place, you own `app.py` for W1):**
- `app.py` — `_run_and_cache`, `_build_opp_mixture` (W1 override ~2849), thin-leaders
  guard (~1247/1323), `_hybrid_fill_opp_8u`, polish passes.
- `w1_predictor.py` — v4Rt augmentation, `predict_w1_lineup_mixture`, transition data.
- `w1_v4_params.json`, `nvsl_divisions_by_year.json`, `w1_8u_div_pcts.json`,
  `v3_params_by_division.json` — calibration data (regenerate via `build_8u_div_fill.py`
  etc. if you change the basis).

**Harnesses (mirror production — keep them in sync if you edit the pipeline):**
- `prod_eval.py` — production-faithful score bias/MAE, all weeks. Env: `EVAL_MAX_SIDES`
  (cap), `SHRINK_K` (profile shrinkage, leave 0). Outputs `prod_eval_results.jsonl` +
  `_summary.txt`. Resume-safe. **`build_profiles` already has the thin-leaders guard.**
- `beat_coach_v2.py` — honest beat-coach (actual times + same-day-form + present-roster).
  Env: `WEEKS=1`, `MEETS_PER_WEEK`, `PRESENT_ONLY=1`. Outputs `beat_coach_v2_w1.jsonl`.
- `build_8u_div_fill.py` → regenerates `w1_8u_div_pcts.json` from 2021–2024.
- `reconcile_beat_coach.py` — the model-vs-actual circular proof (reference).
- `/tmp/w1_decompose.py` — the §2.6 polish/roster/model-optimism ablation (4 cells:
  polish on/off × full/present roster). Checkpoint `/tmp/w1_decompose.jsonl`. **Move to
  repo if you keep iterating.**
- `/tmp/w1_ghost_absence.py` — the §2.6 ghost-vs-absence split (3 roster cells:
  full / returned-in-2025 / present-that-day). Checkpoint `/tmp/w1_ghost_absence.jsonl`.
  **Has the present-cell under-fielding artifact — patch it (backfill thinned events)
  before trusting the absence/optimism split.**
- `/tmp/test_shrinkage.py` — issue-#2 k/σ fit (note §2.7 flag: fit on pure_greedy+race_points
  margins; re-fit on production `simulate_match` margins if you touch the headline).

**Note:** `*.jsonl`, `*_summary.txt`, and caches are now gitignored (regenerable). The
result files in your tree may be stale — regenerate, don't trust timestamps.

**Coordination:** the other agent (me) shipped issues #1–#3. If you touch the win-prob
path (`_shrunk_winprob`, `analytical_winp` in `_run_and_cache`) or the W2–W5 cure
(`coverage_blend`), flag it — those are validated and shouldn't move without a reason.

---

## 9. TL;DR for the impatient
1. You're on W1. Everything else is shipped (build on `4069d2f`).
2. The W1 eval is **stale** — re-run `prod_eval.py` first (§6), look at **MAE + blowouts**, not mean bias.
3. The blowouts are near-empty profiles (`pred 34–70`); the guard should fix most — confirm.
4. **The residual over-prediction is mostly ABSENCES (~+18), not ghosts (~0) or polish (~+2)** — measured §2.6.
   The W1 fix is **absence handling** (the `absent` input / an expected-absence model), NOT ghost removal or roster uploads.
5. Don't re-try: returner upgrades (−76), median imputation (−51), week multipliers, tapering (§3); ghost-dropping for bias (~0 effect, §2.6); polish-threshold tuning for bias (~+2 only, §2.6).
6. Don't measure on model times or opponent-only events. (§5)
7. Heads-up: the shipped win-prob isn't week-gated → **W1 headline win% is currently miscalibrated** (§2.7). Week-gate it when you work W1.
