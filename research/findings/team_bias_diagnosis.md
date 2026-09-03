# Team bias diagnosis: persistent under-prediction of 6 teams

**Date:** 2026-06-10 · **Inputs:** `mock_final_v4_full.jsonl` (pred_actual − truth), `nvsl_meet_history.json`, `leaders_cache.json`, `mock_ladders_v4/`, `nvsl_divisions_by_year.json` · **Helper:** `team_bias_helper.py` (read-only)

## TL;DR

**5 of the 6 teams (Commonwealth, Cottontail, Camelot, Country Club Hills, Parliament — plus a 6th you didn't flag, Lincolnia Park) are victims of a single corrupted meet record each: `nvsl_meet_history.json` has the two team NAMES attached to the wrong sides of the meet.** Codes, scores, and lineups stay internally consistent with each other; only the names are crossed. Verified by lineup ownership: **0%** of the named side's swimmers appear in that team's `leaders_cache`, **100%** appear in the opponent's. The bug is the per-meet letter-set heuristic `_assign_codes_to_teams` in `scrape_history.py` (line ~131), which is provably ambiguous for exactly these rival pairs.

**Mansion House: no data anomaly found.** It is a genuinely improved team (+38.8 ppg 2024→2025, 92nd percentile) and sits on the league-wide "improvers get under-predicted" model trend, not off it.

## 1. The corrupted 2025 meets (the smoking gun)

Scan rule: a side whose recorded `code` ≠ that team-name's modal code across the season. Five 2025 meets hit, every one a name swap:

| Week | meet_id | Recorded as | Actually is (by code + lineup) | Lineup match: own / opp leaders |
|---|---|---|---|---|
| 1 | 27687 | Cottontail 238 – Camelot 182 | **Camelot 238 – Cottontail 182** | 0/64 vs 64/64 (and 0/64 vs 64/64) |
| 2 | 27738 | Commonwealth 245 – Country Club Hills 170 | **CCH 245 – Commonwealth 170** | 0/66 vs 66/66; 0/59 vs 59/59 |
| 2 | 27792 | Parliament 227 – Lincolnia Park 193 | **Lincolnia Park 227 – Parliament 193** | 0/67 vs 67/67; 0/69 vs 69/69 |
| 3 | 27843 | Long Branch 259 – Broyhill Crest 160 | **Broyhill Crest 259 – Long Branch 160** | 0/60 vs 60/60; 0/53 vs 53/53 |
| 3 | 27845 | Springfield 225 – Edsall Park 161 | **Edsall Park 225 – Springfield 161** | 0/34 vs 34/34; 0/40 vs 40/40 |

10 affected team-sides. Six are in the backtest (the 5 flagged teams + Lincolnia Park); the other four (Broyhill Crest, Long Branch, Springfield, Edsall Park) are **Division 17** and not in the 95-team eval set, which is why they never showed up in the bias table.

### How one swapped meet produces the observed bias

Per-meet error decomposition (pred_actual − truth), swapped week vs the other 4:

| Team | bias @ swapped wk | mean bias other 4 wks | truth corruption (real − recorded) |
|---|---|---|---|
| Commonwealth | **−145.4** | −19.2 | −75 |
| Cottontail | **−131.1** | +2.2 | −56 |
| Parliament | **−130.7** | −16.5 | −34 |
| Lincolnia Park | **−100.9** | +10.9 | +34 |
| Camelot | **−98.6** | +8.5 | +56 |
| Country Club Hills | **−97.5** | −11.8 | +75 |

Two stacked effects in the swapped meet, which is why BOTH sides (winner and loser of the swap) go hugely negative, not antisymmetric:

1. **Wrong truth**: the recorded score belongs to the opponent (±34–75 pts).
2. **pred_actual collapse**: the "actual lineup" recorded for the team is 53–69 of the *opponent's* swimmers, none of whom exist in the team's profiles, so the predicted score of the "actual" lineup craters (e.g., Commonwealth W2: pred_actual ≈ 99.6 vs truth 245).

The residual −10 to −20 in the other weeks for Commonwealth/CCH/Parliament is consistent with the league-wide model trend (see §3) — clean-team residual SD is 8.3, so these are ≤ ~1.5–2.7σ, and Cottontail/Camelot/Lincolnia Park are actually *positive* outside the swapped week. The "5/5 negative" appearance comes from one catastrophic meet dragging means plus the global trend; once the swapped meet is fixed, these teams are expected to be unremarkable.

### Secondary contamination from the same swap

The swapped meet also pollutes every history-derived per-team aggregate:

- **2025 "history roster" inflated ~75%**: e.g., Commonwealth shows 146 distinct 2025 swimmers in meet history vs 81 in leaders_cache; the 66 extras are CCH swimmers each with *exactly 2 races* (one meet's worth). Controls: Daventry 81/81, Lakeview 79/79, Hayfield Farm 96/96.
- **leaders_cache swimmer coverage drops to 55–60%** for the 6 teams vs **99–100% for all other 95 evaluated teams** (binary signature, no in-between). This is the cleanest detection metric: r = +0.56 between coverage and team bias.
- **Mock-ladder "coverage" looks bad (55–60%)** for the same reason, but the ladders themselves are FINE — they're built from leaders_cache (clean source). Ladder-only names: 0–5 per team.
- **Returner fraction looks 37–45% vs ~73–78% for controls** — again denominator pollution, not real newcomer inflation.
- Anything built off meet history league-wide (participation priors, presence model, freshness) inherits ~60 phantom one-meet swimmers per affected team.

## 2. The scraper bug (root mechanism)

`scrape_history.py` gets names in schedule order and codes from the results page, then maps codes→names via `_assign_codes_to_teams` using letter-set compatibility ("every letter of the code appears in the team name"). For exactly these pairs the test is non-discriminating:

| Code pair | Compatibility matrix |
|---|---|
| CT / CCC (Camelot, Cottontail) | all 4 combinations True → ambiguous |
| PAR / LP (Parliament, Lincolnia Park) | all 4 True → ambiguous |
| LBR / BC (Long Branch, Broyhill Crest) | all 4 True → ambiguous |
| S / EP (Springfield, Edsall Park) | all 4 True → ambiguous |
| CCH / CSC (Commonwealth, Country Club Hills) | CSC incompatible with Commonwealth (no 'S' in the name — the code is from "Commonwealth **S**wim **C**lub") → heuristic confidently picks the WRONG assignment |

Because the ambiguity is a property of the team-name pair, **the same rivals get swapped every season they meet**:

- 2021: 12 sides (incl. Parliament↔Parklawn, Springfield↔Edsall Park, McLean↔Hamlet, Hollin Hills↔Herndon, Great Falls/Fairfax Station↔Arlington Forest)
- 2022: 24 sides (incl. Commonwealth↔Broyhill Crest, Parliament↔Lincolnia Park, CCH↔Sleepy Hollow Rec, **Mansion House↔Holmes Run Acres**, Truro↔Poplar Tree, Springfield↔Edsall Park ×3)
- 2023: 8 sides (Springfield↔Edsall Park, Hamlet↔Cardinal Hill, Long Branch↔Broyhill Crest, Hollin Hills↔Herndon)
- 2024: 2 sides (Springfield↔Edsall Park W4 — corrupts `build_prior` for those two only; both div 17, outside the eval)
- 2025: 10 sides (the table above)

Springfield↔Edsall Park is swapped in **all five seasons**.

## 3. Mansion House — no data anomaly

Checked everything the other teams failed, all clean:

- leaders_cache: exact key, 607 entries all 2025-dated, 96 swimmers, pool codes per date match the meet venue every week, codes = {MHC} all season.
- 100% of 2025 history swimmers in leaders_cache; mock ladder covers 94/96 (98%); returner overlap 74/96 (77%) — control-level.
- 2024 present under the same name (5 meets, 100 swimmers, code MHC). Division 9→10 (demoted after a 1–4 2024).
- No 2025 name/code mismatch. (It WAS swap-corrupted in 2022 vs Holmes Run Acres, but 2022 feeds nothing in this pipeline.)
- Only name quirk found: 2024 "Sofia a Vasquez" (lowercase middle initial survives `normalize_name`, breaking one returner link) — a 1-swimmer nit, not a −26 bias.

The real story: Mansion House went 1–4 (avg 189) in 2024 to 4–1 (avg 228) in 2025 after demotion to Div 10. Across 87 clean evaluated teams, **bias = 0.4 − 0.211 × (2025−2024 ppg improvement), r = −0.59**: the model systematically under-predicts improvers because seeds anchor on prior-year times (returner TT = 2024 best × SHBR-fit ratio). Mansion House's +38.8 ppg (92nd pct) predicts ≈ −8 bias from the trend; its −26 observed is ~2σ — at the unlucky edge but on the same model-side trend that also produces Vienna Aquatic −23.3, Stratford −22.8, Brandywine −20.7 (all with 100% data coverage). This is a *model* limitation (improvement/age-up rate), not a data-pipeline defect.

## 4. Targets vs controls, all checks (2025 unless noted)

| Metric | CW | CT | CAM | CCH | PAR | MH | Daventry | Lakeview | Hayfield F |
|---|---|---|---|---|---|---|---|---|---|
| mean bias (pred_actual) | −44.4 | −24.4 | −12.9 | −28.9 | −39.3 | −26.2 | −4.5 | +1.5 | −3.9 |
| leaders key exact | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| leaders 2025 entries | 544 | 603 | 582 | 585 | 625 | 607 | 533 | 572 | 626 |
| pool-code/date consistency | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| hist swimmers in leaders | **55%** | **58%** | **59%** | **60%** | **56%** | 100% | 100% | 100% | 100% |
| mock ladder entries | 728 | 897 | 1049 | 895 | 749 | 886 | 915 | 897 | 1020 |
| hist swimmers in ladder | **55%** | **58%** | **59%** | **60%** | **56%** | 98% | 100% | 99% | 100% |
| 2024 same name / meets | ✓/5 | ✓/5 | ✓/5 | ✓/4 | ✓/5 | ✓/5 | ✓/5 | ✓/5 | ✓/5 |
| returner overlap | **41%** | **37%** | **43%** | **43%** | **42%** | 77% | 72% | 78% | 73% |
| division 2024→2025 | 14→11 | 8→8 | 9→8 | 10→11 | 14→14 | 9→10 | 11→11 | 9→8 | 14→14 |

Other checks: leaders_cache key matches meet-history name **exactly for all 101 teams** (no case/punctuation/'Pool'/'Club' drift); no roster file exists for any of these teams (`roster/` contains only SHBR, all `roster_excludes/*.json` are empty — the "dropped swimmers" path never fires); entry counts and lc-entries-per-meet are indistinguishable from controls (the leaders cache itself is healthy for all 9 teams). The bold rows are pure denominator pollution from the swapped meet. Swimmer spot checks confirm: every "missing from leaders cache" swimmer has exactly 2 races and belongs to the swap opponent (e.g., Commonwealth's "Asher Voss", "Declan Rourke" are CCH kids; no nickname/middle-initial pattern found).

## 5. Fix recommendation

1. **Repair the data (one-off script, ~30 lines):** for every meet side where `code` ≠ the team-name's season-modal code, swap the two `name` fields (codes, scores, lineups are already mutually consistent). Apply to all years; 2025 (5 meets) and 2024 (1 meet) are the ones feeding this pipeline. Validate post-fix: every evaluated team's history-swimmer-in-leaders coverage should go to ~100%.
2. **Fix the scraper:** replace per-meet letter-heuristic assignment with a league-wide code→team map built from the unambiguous majority of meets (each code's modal team name across the season), and only fall back to the heuristic for codes never seen elsewhere. Add an assert: each side's lineup swimmers must overlap that team's leaders_cache names (>50%) or the meet is flagged.
3. **Add the detection metric to CI/validation:** "fraction of a team's meet-history swimmers present in its leaders_cache" — it is binary (99–100% clean vs 51–62% corrupted) and caught all 10 affected teams with zero false positives.
4. **Rebuild downstream artifacts after the repair:** mock ladders (returner/newcomer splits shift), participation priors, presence model, freshness cache — anything reading meet history.
5. **Expected effect on the backtest:** the six teams' catastrophic meets (−97..−145) disappear and their truth labels correct by ±34–75; remaining bias should land on the league trend. Mansion House (and Vienna Aquatic/Stratford/Brandywine) need a *model*-side answer — a stronger team-level improvement factor or division-change feature — not a data fix.
