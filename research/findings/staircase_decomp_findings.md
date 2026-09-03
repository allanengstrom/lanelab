# Staircase decomposition — mechanism identification

**Question:** why do score predictions run too LOW vs weak opponents and too HIGH vs
strong ones (slope ≈ +3.3 error pts per +10 opponent pts)?
**Basis:** `overnight_cache.jsonl` (488 sides, deduped from 514 lines; old no-ladder
run where calibration bias `pred_actual − truth` is −42.5 vs weak opponents (<170)
and +2.7 vs strong (≥230); slope +3.78/10 in this dataset).
**Tooling:** `staircase_decomp.py` (re-runnable; `--sample` for the 50-side probe);
per-side rows in `staircase_decomp_rows.jsonl`; full log in `staircase_decomp_full.log`.

## Method

Per side, per individual event, our expected points are scored along an exact chain
(profiles/predicted times from `overnight_opt_cache.jsonl`, actual times/places from
`nvsl_meet_history.json`, predicted opp composition = `opp_pred_lineup`):

- **Af** MC (production-faithful: lognormal + 8U DQ finish rates), our profile-backed
  actual finishers @ predicted times vs predicted opp composition @ predicted times
  — mirrors what cached `pred_actual` scored. Reconciles vs `pred_actual − relay` (**r1**).
- **A** = Af + our no-profile finishers at actual times → **usMiss** = Af − A.
- **A2** = plain-normal MC → **dq_ln** = A − A2 (modeled DQ/lognormal effect),
  **H1** = A2 − B (pure MC-vs-deterministic rank compression).
- **B** deterministic rank of predicted means, same composition.
- **C** same predicted opp composition, actual times for anyone who actually swam
  that event → **H3** = B − C (time error).
- **D** reality (actual opp finishers @ actual times) → **H2** = C − D (composition);
  D reconciles vs official place-points (**r2**), remainder closes through the relay
  residual (**relay_resid** = predicted relay pts − actual relay pts).
- **evMiss**: events we actually scored in that were entirely absent from the cached
  run's profile-derived event universe (predicted as 0 by omission).

Identity (exact, verified to ±0.01 on all 488 sides):
`pred_actual − truth = r1 + usMiss + evMiss + dq_ln + H1 + H3 + H2 + r2 + relay_resid`

## Reconciliation quality

- Identity check: max |error| 0.01 across 488 sides (exact by construction).
- r1 (cached `pred_actual − relay` vs my Af recomputation): mean +2.0, MAE 2.35 —
  MC-noise level (cached used n=10 000, this run n=4 000), and nearly flat vs
  opponent strength (slope +0.11/10). The cached prediction is faithfully reproduced.
- r2 (time-rank vs official places): mean −0.13 — negligible.
- relay_resid MAE 9.1/side — relays are real error, quantified below but
  **unattributed by design** (excluded from the event decomposition).
- Sanity gate (sample and full): PASS — attributable components = **96%** of the
  individual-events staircase gap.

## Attribution table (full 488 sides)

Calibration error E = `pred_actual − truth`, bucketed by opponent's actual score:

| bucket          |   n |     E |   r1 | usMiss | evMiss | dq_ln |   H1 |    H3 |   H2 |  relay |
|-----------------|----:|------:|-----:|-------:|-------:|------:|-----:|------:|-----:|-------:|
| weak (<170)     |  74 | −42.5 | +1.4 |   −4.0 |   −2.1 |  −1.8 | −3.1 | −13.3 | −9.1 |  −10.4 |
| mid             | 275 | −16.7 | +1.9 |   −3.2 |   −0.2 |  −0.8 | −0.5 | −15.0 | +1.8 |   −0.5 |
| strong (≥230)   | 139 |  +2.7 | +2.5 |   −3.3 |   −0.2 |  −0.1 | +1.2 | −11.6 | +6.1 |   +8.1 |
| **GAP (s − w)** |     | **+45.2** | +1.2 | +0.7 | +1.9 | +1.7 | **+4.4** | +1.7 | **+15.2** | **+18.5** |

Share of the +45.2 staircase gap:

| mechanism                                            |  gap | share |
|------------------------------------------------------|-----:|------:|
| Relay expected-points compression (see below)         | +18.5 |  41% |
| **H2 — opponent composition (phantoms/surprises)**    | +15.2 |  34% |
| H1 — MC rank-compression, individual events           |  +4.4 |  10% |
| evMiss — event-universe truncation (blowouts only)    |  +1.9 |   4% |
| dq_ln — modeled 8U DQ/lognormal                       |  +1.7 |   4% |
| H3 — time error                                       |  +1.7 |   4% |
| usMiss — our unprofiled scorers                       |  +0.7 |   2% |
| reconciliation residuals (r1 + r2)                    |  +1.2 |   3% |

OLS slope per +10 opponent points (sums to E's +3.78): H2 +1.06, relay +1.55,
H3 +0.33, H1 +0.31, evMiss +0.18, dq_ln +0.15, usMiss +0.09, r1 +0.11.

## Phantom / surprise rates vs opponent strength

Predicted opp entries vs actual opp finishers, per event (full run):

| bucket        | pred entries | actual | matched | phantom-absent* | phantom-elsewhere† | div-avg | surprise‡ |
|---------------|----:|----:|------:|------:|------:|-----:|------:|
| weak (<170)   | 7 785 | 7 037 | 51.1% | 29.5% | 17.1% | 2.3% | 43.5% |
| mid           | 31 145 | 29 878 | 55.8% | 24.0% | 17.7% | 2.4% | 41.8% |
| strong (≥230) | 15 755 | 15 220 | 56.4% | 22.5% | 18.7% | 2.4% | 41.7% |

\* predicted swimmer appears nowhere in the opponent's actual meet results (no-show
or DQ — DQs are absent from results). † swam, but in different events.
‡ actual finisher not predicted for that event.

In the extreme sample (opp <160 vs >240) the asymmetry is starker: match 39% vs 54%,
phantom-absent 37% vs 23%; weak opponents were predicted to field 91.7 entries/side
but actually fielded 75.3 (−18%), while strong opponents fielded 105.6 of a
predicted 109.4 (−3%). **Weak teams' predicted entries vanish; we get unpredicted
sweeps. Strong teams materialize almost fully.** Net H2 swing: reality hands us
+9.1 pts vs weak opponents and takes −6.1 pts vs strong ones, relative to the
predicted composition.

## The relay component is the same compression disease

Across all 488 sides (no MC needed; `relay_resid = relay_pred − (truth − Σband_actual)`):

| bucket | relay predicted | relay actual | residual |
|--------|----:|----:|------:|
| weak   | 35.1 | 45.5 | −10.4 |
| mid    | 31.0 | 31.5 |  −0.5 |
| strong | 25.3 | 17.1 |  +8.1 |

Slope +1.55 per +10 opp pts. The relay expectation is a sum of bounded MC win
probabilities; vs weak teams the model never predicts the near-certain relay sweep
(p capped well below 1 by time noise), and vs strong teams never predicts the
near-certain wipeout. Structurally this is H1 (rank/win-prob compression) operating
on relays, where all-or-nothing points make the compression ~4x larger per event
than in individual events.

## Per-band notes (weak | strong means)

- H2 staircase lives in the older bands: 9-10 −1.4|+2.0, 11-12 −1.0|+1.5,
  13-14 −0.9|+2.2, 15-18 −2.9|+1.3. 8U H2 is negative in both buckets (−2.8|−0.9):
  the 8U div-avg fill over-credits every opponent slightly.
- usMiss (−3 to −4/side, flat) and dq_ln are almost entirely 8U: real 8U scorers the
  model has no profile for, and the DQ discount taking ~1.8 pts vs weak opponents.
- evMiss is concentrated in the 90–120 bucket (−9.8/side there): in total-blowout
  meets the profile-derived event union drops whole events (e.g. Broyhill Crest vs
  Edsall Park W2: 6 events worth 41 actual points never scored — was a −45 r1
  outlier until modeled explicitly).

## Verdicts

- **H2 — CONFIRMED, primary individual-event mechanism.** +15.2 of the +26.7
  individual-events gap (57%); driven by phantom no-shows on weak teams
  (29.5% vs 22.5% of predicted entries absent from results entirely) and weak
  teams fielding 18% fewer lanes than predicted in the extreme tail.
- **H1 — CONFIRMED but small in individual events** (+4.4, 10% of total gap)…
  **unless relays are counted as the same mechanism**, in which case
  compression-type effects total +22.9 (51% of the gap). The single biggest
  lever overall is the relay expectation, not individual-event MC.
- **H3 — REJECTED as a staircase driver** (gap +1.7, 4%). It is, however, the
  dominant *constant* bias: at actual times we score ~13–15 pts/side more than at
  predicted times, uniformly across opponent strength. (Caveat: C updates all our
  finishers' times but only the ~55% matched opp entries, so part of this constant
  is an asymmetric-update artifact; either way it cancels out of the staircase.)
- New mechanisms surfaced: **event-universe truncation** (evMiss) and **unprofiled
  8U scorers** (usMiss) — small for the staircase but real bias sources, the former
  exclusively in blowouts vs the weakest teams.

## What doesn't fully reconcile

- r1 carries a small +2.0 constant (likely MC n=4 000 vs 10 000 plus minor profile
  drift between the two overnight runs) — flat vs opponent strength, so it does not
  affect the attribution.
- The prompt's headline numbers (−21/+17 corrected bias) are from the newer ladder
  basis; this decomposition uses the old basis (−42.5/+2.7) where the staircase is
  steeper but the same shape (slope +3.78 vs ≈+3.3). Mechanism shares should carry
  over; magnitudes will be ~25–40% smaller on the new basis.
