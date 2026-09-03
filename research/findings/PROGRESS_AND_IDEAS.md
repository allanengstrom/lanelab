# Lane Lab — Progress & Ideas (handoff, 2026-06)

Context for the other agent (esp. picking up **Week 1**). This captures the
session's findings, what shipped, the honest state of the metrics, the
methodology traps we hit, and ideas for betterment.

---

## TL;DR — the honest state

| Metric | Value | Confidence |
|---|---|---|
| W2–W5 score bias | **~+3** (over-predict), MAE ~16 | firm (prod_eval, full path) |
| W1 score bias | **+29** (over-predict), MAE 38, 5 blowouts | firm (today, source-fixed) |
| Beat-coach W2–W5 (honest) | **74%** (+6.95/team) | firm (n=120, present-roster + same-day-form) |
| Beat-coach (circular) | ~95–100% | **meaningless — do not use** |

**Final beat-coach (present-roster + same-day-form, the fully honest metric):**
```
W2 50%   W3 83%   W4 83%   W5 80%   |   ALL 74%, +6.95 pts/team
Outcome flips: 8 GOOD (loss->win), 0 BAD. Downside-free.
```
**No championship-week collapse.** The old "W2 95.7% -> W5 28.0%" (issue #3) was the
CIRCULAR metric. The honest shape is the *opposite*: a ramp from the W2 floor to a
stable ~82% plateau — we get *better* vs coaches as current-season data accumulates.

**W2 = 50% is an information/staleness gap, not a fixable bug.** At W2 we have 1 noisy
current week; profiles are mostly stale 2024; the coach knows current form. Shrinkage
(regularizing toward 2024) was tested and is a WASH (0/10 flips, bias/MAE unchanged) —
because the problem is missing current info, not noise. Only more data (W3+) or external
current-form signal (roster uploads, taper info) closes it; neither is a knob.

**The big reframe this session:** several "great" numbers were circular or
inflated. After fixing the measurement, the tool's real edge is **modest but
real** — beats coaches ~80% on points (mostly in close meets), over-predicts
scores because the model rose-tints our own swimmers. Two genuine product wins
landed (coverage_blend cure, W1 source fix); the rest was de-fogging the metrics.

---

## What SHIPPED to production (app.py + data)

1. **coverage_blend NameError fix** — the validated W2–W5 cure (`apply_coverage_blend`)
   was silently disabled by a `week` NameError swallowed as "SKIPPED". Now fires
   for W≥2. This is most of why W2–W5 bias is ~+3 (was historically −22).
2. **8U opponent fill** (`_hybrid_fill_opp_8u`): keep opp's real 8U swimmers, fill
   empty slots with division-typical synthetic swimmers. Fixes the v5-under-fielded-8U
   sweep. Calibration in `w1_8u_div_pcts.json` (built by `build_8u_div_fill.py` from
   2021–2024): per-division `[p_fast, p_med, p_slow, fill_n]`, with turnout-aware
   fill count and a bottom-tier slowness offset. 8U validated to ~−2 bias.
3. **W1 thin-leaders source-selection guard** (`api_load_setup`): a team with a
   single stray pre-season leaders entry was getting a 1-swimmer profile that
   SUPPRESSED its full 2024 record → near-empty profile → ±200 blowouts. Guard:
   if leaders coverage < `LEADERS_MIN_SWIMMERS` (20), merge the prior-year baseline
   underneath. **Result: W1 blowouts 13→5, MAE 108→38.** Mirrored in `prod_eval.py`.

---

## Major findings

### 1. The "95.7% beat-coach" was CIRCULAR
Scoring our optimizer's lineup vs the coach using **model/profile times** → we win
~100% **by construction** (the optimizer maximizes exactly that score). Proof
(same meets, both ways): **MODEL-times 100% vs ACTUAL-times 55%.** The logged
95.7% / 62.5% were the model-times version. **Always score beat-coach on ACTUAL
times.**

### 2. Same-day-form scoring (operator's fix) — the honest number is ~81%
When our lineup moves a swimmer to an event they didn't swim, don't use their
stale profile time — scale their profile by their **same-day form**
(`actual_time / profile_time` averaged over events they DID swim). This is real
out-of-sample data, not circular. Lift: **W1 56→81%, W2 31→81%** (both converge,
confirming the old 31% was a stale-profile artifact). Implemented in
`beat_coach_v2.py`.

### 3. Absences (operator's fix) — we were fielding swimmers who weren't there
We optimize over the FULL roster, but real meets have absences. Fielding absent
swimmers → phantom points → inflates BOTH the +29 bias AND beat-coach. Fix for
**measurement**: restrict the optimizer pool to swimmers who actually competed
that day (`PRESENT_ONLY` in `beat_coach_v2.py`). It's symmetric/fair (a fully-benched
present kid is excluded from both sides). Fix for **live use**: the `absent` input
in `/api/run` already exists — coach marks who's out.

### 4. The shared root cause
The +29 over-prediction and the circular-100% are the **same bug**: the optimizer
fields swimmers that look great in the model but don't perform in reality —
**ghosts** (won't-return), **absences** (out that day), **coverage-blend** stale
times, and **polish** banking MC-noise gains. In-model they score; on actual
times they don't. Fix the root → both numbers improve together.

---

## METHODOLOGY TRAPS (read before measuring anything)

- **Union events.** The 8U hybrid only fills events in the `events` list it's
  handed. Production passes the **union** of both teams' events. A harness that
  passes opponent-only events leaves teams with no pre-meet 8U races fielding
  NOBODY → phantom blowouts. The "D1 +19.8" panic was *entirely* this bug, not a
  production problem. **Validation MUST pass union events.**
- **Model vs actual times.** Beat-coach on model times = circular (see Finding 1).
- **Stale-profile penalty.** Profile fallback for moved swimmers under-credits us
  (esp. W2+ where profile = slow 2024 coverage-blend). Use same-day form.
- **Present roster.** Full-roster optimization fields absent swimmers. Restrict to
  present for honest measurement.
- **Polish inflation.** `_polish_*` optimize the MODEL score → inflate the predicted
  total. Separate "what lineup we recommend" from "what score we predict."

---

## OPEN / QUEUED (this session's task list)

- Present-roster beat-coach W2–W5 (running) — honest equal-roster number.
- **#7** W1 bias present-only — quantify how much of +29 is absences vs model.
- **#5** Polish-threshold tuning (0.1→~1.0) — likely ~half the +29 is polish.
- **#4** Presence-weighting / ghost removal — drop 2024 won't-return swimmers.

---

## IDEAS FOR BETTERMENT — Week 1 focus (for the other agent)

W1 is the hardest week: **no current-season race data**, so we predict off 2024 +
ladder/roster. Everything below is about taming roster uncertainty.

1. **The 5 remaining W1 blowouts.** Source fix cut 13→5. The 5 are likely teams
   with no usable 2024 history *either* (expansion/realigned teams, name changes).
   Investigate: which teams, and is there *any* prior signal (division-average
   fallback?).
2. **The +29 over-prediction — decompose it.** Best estimate of components:
   - **Polish inflation** (~half?): test raising thresholds.
   - **Ghosts**: 2024 swimmers who won't return (~24% per old notes). Presence-prior
     by band/participation; SwimTopia roster is authoritative where present.
   - **Absences**: model an expected absence rate, or lean on the `absent` input.
   - Run W1 with polish OFF vs ON + our-side vs opp-side to split it cleanly.
3. **Presence-weighting** is the highest-value structural W1 fix — it attacks
   ghosts AND feeds the absence story. Returns-prior from 2021→2024 transitions
   (by band: 15–18 seniors graduate → low return; younger → high).
4. **Decouple displayed score from optimizer-max.** The score we *show* shouldn't
   be the optimizer's inflated self-assessment. Predict from a calibrated baseline;
   recommend the polished lineup. This is the clean fix for "whoever runs the
   optimizer wins."
5. **More SwimTopia roster uploads.** A current roster *eliminates* both the ghost
   and (with `absent`) the absence problem outright. Only B&R has one today —
   getting more is a data play worth as much as any model change.
6. **W1 uses the symmetric (no-upload) branch for most teams** — bias +1.5 per
   notes, but our deterministic check showed +6 and production +29. The gap is
   polish + ghosts + absences stacking. Worth re-validating the W1 architecture
   numbers with the present-roster + actual-times methodology (the old numbers
   may have used inflated scoring).

### How to measure W1 correctly (so you don't re-hit our traps)
- Build profiles via `prod_eval.build_profiles` (has the source fix + thin-leaders guard).
- Pass **union events** to `_hybrid_fill_opp_8u`.
- For bias: predicted total = `mc_total + relay_exp_pts` from the production path.
- For beat-coach: **actual times + same-day-form + present-roster** (see `beat_coach_v2.py`).
- Resume-safe runs: write per-meet jsonl, skip done keys (kills happen ~1h in).

---

## Key files
- `app.py` — `_run_and_cache`, `_hybrid_fill_opp_8u`, `api_load_setup` (source guard),
  `_build_opp_mixture` (W1 v4Rt / symmetric branch).
- `prod_eval.py` — production-faithful score-bias harness (mirrors `_run_and_cache`'s
  total sequence; skips win%-only sims).
- `beat_coach_v2.py` — honest beat-coach (same-day-form + present-roster).
- `build_8u_div_fill.py` → `w1_8u_div_pcts.json` — 8U per-division calibration.
- `improvements.md` — longer-form issue tracking (issue #1 W1 cure, #3 beat-coach).
