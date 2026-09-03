# Display Rules

User-specified rules for how the **scoresheet (points)** and the **win probability**
are displayed to the coach. These govern *presentation*, not the model's bias
correction — which is a SEPARATE concern (see the overarching principle below).

Quotes marked *(user)* are the user's direct words; items marked *(derived)*
follow from them. Read this before changing anything in the display path.

---

## Scoresheet (points)

1. **Totals conserve to the points actually awarded — NOT a hard 420.**
   The two team totals sum to the meet pool, which is *at most* 420. When there
   aren't enough entries to fill every scoring place (e.g. low-participation teams
   like division 17, or any uncontested event), the unfilled places award nothing
   and the pool is correspondingly lower. **Never inflate a short meet up to 420.**
   *(user: "they should add to 420" + "if there are not enough entries to score
   420 points, it shouldn't be to 420. (division 17)")*

2. **Per-event points sum to the total.**
   Each event's points add up to what's actually awarded there (9 for a full
   event: 5-3-1; less when a place goes unfilled), and those per-event values sum
   to the team totals. The scoresheet adds up the way a real meet sheet does.
   *(user: "the per event sum should equal the total points")*

3. **Per-event points must be realistic — no compression.**
   An event one side sweeps awards essentially all of its points to that side
   (~9 to ~0). Points must NOT cluster around the midpoint (the "everything's
   3–5 points" / "a sweep for them still yields 3 for us" failure). A uniform
   shrink toward 4.5 is forbidden — it destroys per-event meaning.
   *(user: "points seem to be wrong... they're always within 3-5 points, which is
   unrealistic, and some of the events that look like a sweep for them still yield
   like 3 points for us")*

4. **Do not display the opponent's per-event score.**
   The per-event view shows only our points. (The opponent's total may still
   appear in the headline matchup line; only the per-event opponent breakdown is
   suppressed.)
   *(user: "we dont need to display their score")*

---

## Win probability

5. **Accurate as a function of margin and outcome spread, decoupled from bias.**
   The win % is driven by the predicted margin and the irreducible outcome spread
   — not by any bias term.
   *(user: "make it so that win probabilities are accurate without concern for the
   bias")*

6. **Win % = Φ(margin / σ).**
   A roughly one-standard-deviation edge reads as ~68%, scaling up from there.
   σ ≈ 30 points for the margin (per-side outcome SD ≈ 18, combined across the two
   anti-correlated sides of a meet). σ is tunable via
   `calibration_constants.json["_winprob_sigma_margin"]`.
   *(user: "MAE 15... within 1 standard dev... win percentage should be ~68%")*

7. **Origin-forced: 50% at a tie, no intercept.** *(derived from rule 8.)*
   A correctly-centered prediction at a tied margin is a genuine coin flip, so
   nothing may pull the win % below 50% for a non-negative margin.

---

## Overarching bias principle

8. **Don't correct bias inside the display.**
   Assume the bias is fixed to ~0 by the separate calibration work, and build the
   points and win % to be correct *given an unbiased prediction*.
   *(user: "for now, we dont care about bias, because if we get it to close to 0,
   then it will be correct")*

9. **Honesty/de-inflation lives in the bias correction and the win %, NOT smeared
   across per-event points.** *(derived from rule 3.)*
   The fix for an inflated prediction is to correct the margin/total upstream and
   let the win % reflect the corrected margin — never to compress per-event points.

---

## Current state & known tension

- Rules 1–3 currently display the **genuine** (still-biased) margin, while the
  win % (rule 5) uses the **bias-corrected** margin. So the points and the win %
  don't yet tell the same story (points look like a bigger blowout than the win %
  implies). Per rule 8, this resolves itself once the bias correction lands — both
  will then be driven by the same unbiased margin.

## Where implemented (app.py `_run_and_cache`)

- Rules 1–3: the "CONSERVING SCORESHEET" block — per-event points stay genuine,
  `opp_pts = points_awarded − our_pts` (rule 2), totals = raw conserved medians
  (rule 1; `_event_alloc` counts finishers so short events award < 9).
- Rule 4: `_build_event_payload` carries `opp_pts` but `templates/_lineup_body.html`
  renders only our points.
- Rules 5–7: the win-prob block — `analytical_winp = Φ(margin / σ)`, origin-forced,
  σ from `calibration_constants.json`.
