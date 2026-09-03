# v5 Jaccard ceiling investigation (2026-06-10)

## Executive summary (plain English)

v5 predicts opposing coaches' lineups at ~51.5% Jaccard, and the question was
whether that can go higher — with absences as the suspected ceiling. The answer:
the ceiling is real, it is absences, and v5 is already sitting almost on top
of it.

If v5 magically knew exactly which kids would show up each Saturday, its
Jaccard would rise from 51.6 to 59.5 — perfect attendance knowledge is worth
about 8 points, and today v5 fields a swimmer who turns out to be absent 23%
of the time. The natural fix was to predict attendance: a presence model was
trained and it is genuinely good (AUC 0.79, well calibrated, far better than
any heuristic). But wired into v5 three different ways — score multiplier,
full retrain with presence features, hard pool gating — it moved nothing
(+0.1pp, ±0.0pp, and strictly negative, respectively). The explanation: v5's
existing recency/attendance features already capture everything *predictable*
about presence. The presence model's accuracy comes from separating regular
kids from sporadic kids — which v5 already knows — not from predicting WHICH
regular kid skips this particular Saturday. The 8-point gap is vacations,
illness, and day-of life: information, not modeling.

Two anchors size the remaining gap: a coach's lineup only matches their own
previous week at 0.488 (v5 already out-predicts copying the coach), and the
set of kids who swim turns over ~35% every week. Beyond the oracle's 59.5,
it's mostly genuine randomness.

What actually came out as actionable:

1. **The `absent` input is the whole ballgame** — worth up to the full 8
   points, and it's information a human can actually have. Invest in its UX
   and roster uploads.
2. **W2 has a separate, fixable problem:** 25% of swimmers in actual W2
   lineups have no week-1 history, so they aren't in v5's candidate pool at
   all — invisible, not mispredicted. Adding prior-year-roster kids as W2
   candidates is the one unexplored model-side lever (plausibly +1–3pp at W2).
3. **Reassurances:** the Optimizer.py staleness warning is currently benign
   (a retrain on current code exactly matched production), and the July-4th
   absence dip is real but only ~1 point, with participation otherwise rising
   steadily (~0.80 W1 → 0.91 W5, every year since 2021).

Recommendation: declare v5's model done at ~51.5 — it's near the
information-theoretic edge — and redirect effort to the absent-input UX and,
if week 2 matters, the pool-coverage fallback.

---

**Question:** v5 coach-lineup predictor sits at ~51.5% Jaccard. Can it go higher,
and is the ceiling absences?

**Answer:** The ceiling is real and it IS absences — but the predictable part of
absence is already inside v5. Every model-based attack on it was tested and
refuted. v5 is within ~8pp of a hard information ceiling; the only thing that
moves it materially is *live* absence knowledge (the `absent` input), plus a
separate W2 pool-coverage fix.

All scripts/checkpoints in repo: `jaccard_decompose.py/.jsonl`,
`presence_model.py/.pkl`, `two_stage_eval.py/.jsonl`, `train_v5p.py`,
`coach_predictor_v5p.pkl`, `eval_v5p.py/.jsonl`, `pool_gate_eval.py/.jsonl`.
Production files untouched.

---

## 1. Harness validity

Standalone harness (history-only profiles, decay 0.7, meet-program events,
per-event Jaccard averaged — same definition as `overnight_report.py`)
reproduces the established baseline EXACTLY: W2 48.2 / W3 49.9 / W4 52.5 /
W5 55.3, mean 51.55 (n=387 sides, 2025 W2–W5). Comparisons below are paired,
same sides.

## 2. Oracle decomposition (jaccard_decompose.jsonl)

| cell | W2 | W3 | W4 | W5 | ALL |
|---|---|---|---|---|---|
| BASE (v5 as-is) | .482 | .499 | .525 | .553 | **.516** |
| ORACLE (pool = kids who actually swam) | .529 | .576 | .630 | .644 | **.595** |

- **Perfect presence knowledge is worth +8.0pp.** v5 fields an absent swimmer
  22.7% of the time (consistent with the ~30% W1 absence finding — base rate of
  presence among candidates is 69%).
- **W2 has a second, distinct problem: pool coverage.** 24.8% of actual W2
  swimmers have no week-1 swims → not in the candidate pool at all (→ 15% W3,
  7% W4, 5% W5). The W2 oracle is depressed by the same gap, so the true W2
  ceiling is higher than .529.
- Even the oracle stops at ~.60: the rest is event-assignment error
  (model + coach randomness).

## 3. Coach randomness anchor

- Copy-the-coach's-own-last-week lineup: Jaccard **.488** (2025). v5 (.516)
  already beats it.
- The actual swimmer SET turns over week-to-week at swimmer-set Jaccard .647 —
  ~35% of the kids change every week. The process itself is that noisy.

## 4. Presence model (presence_model.py)

P(swimmer present at week w | history < w), trained 2021–2024, tested 2025
(n=30,459): **AUC 0.794**, Brier .161 (vs .216 const / .222 raced-last-week),
well calibrated. Top features: n_distinct_events, prior-year weeks attended,
total races, team participation prior. Holiday and consec-absent are minor.

Calendar facts: league participation rises monotonically within season
(~.80 W1 → .91 W5 every year 2021–2025). July-4-adjacent meets show a ~1pp
dip (2025 W4, July 5, is the only week in 5 years that breaks the monotone
rise). Real but small.

## 5. Integration attempts — ALL REFUTED (don't re-chase)

| approach | result (paired vs BASE, n=387) |
|---|---|
| Multiply candidate score by P(present)^α, α=0.5/1/2 (+fill gate 0.5) | **+0.14pp best** (α=.5+gate); α=2 −0.3pp |
| **v5p**: retrain on current Optimizer.py + 5 presence features (prior-yr attendance, prior-roster, team prior/current rate, holiday) | **−0.06pp ± 0.08** (exactly nothing) |
| Hard pool gate: drop P(present)<t before ILP, t=.3/.45/.6 | **−0.24 / −0.81 / −2.72pp** (strictly worse) |

**Why:** v5's existing features (recency, weeks-active, consecutive-absences,
frac-in-event) already internalize the *predictable* component of presence.
AUC 0.794 mostly separates "regular kids vs sporadic kids" — which v5 already
ranks correctly — not WHICH regular kid skips this Saturday. The 8pp oracle gap
is the unpredictable-from-history residue: vacations, illness, day-of stuff.
No backtest feature can buy it.

**Side-finding:** v5p retrained on the post-carry-forward Optimizer.py exactly
matches production v5 (51.55) → the `_load_model()` staleness warning is
currently benign; the 2026-06-03 profile-builder change did NOT regress
inference. (Warning stays useful; no action needed now.)

## 6. What WOULD move the number

1. **Live absence info** (the existing `absent` input / SwimTopia rosters).
   The oracle says day-of presence knowledge is worth up to +8pp on opponent
   lineup prediction — and it's knowledge a user can actually have for their
   own team, sometimes for the opponent (social info, B-meet patterns).
2. **W2 pool-coverage fix** (new, unexplored): add prior-year-roster swimmers
   to the W2 candidate pool (with prior-year times). A quarter of actual W2
   swimmers are currently invisible to v5. They can't enter via the ML path
   (no current-season team_se rows) — needs a fallback scoring path. Bounded
   by W2's gap; plausibly +1–3pp at W2, less later.
3. Assignment modeling: v5 (.516) sits between copy-coach (.488) and oracle
   (.595); the residual is substantially coach randomness. Expect grinding,
   not breakthroughs.

## 7. Verdict

51.5% is not a bug — it's near the information-theoretic edge of what history
can know. Mean Jaccard ~52 vs an absence-limited ceiling of ~60, with the
remaining ~40pp largely irreducible coach/turnout noise. Recommend: stop
optimizing v5's model; invest in (a) the `absent` input UX / roster uploads
and (b) the W2 pool-coverage fallback if W2 matters.
