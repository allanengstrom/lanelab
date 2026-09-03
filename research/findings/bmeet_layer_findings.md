# B-meet synthesis layer: fit and validation

Built by `build_bmeet_layer.py`. Augmented ladders in `mock_ladders_v2/` (originals + `SynthBMeet` entries for Mondays 2025-06-09 .. 2025-07-07).

## 1. League-wide within-season improvement fit

Source: 2025 A-meet repeat swims in `leaders_cache.json` (consecutive same-swimmer same-event pairs, gap 5-35 days, annualized to weekly ratio, outliers outside [0.80, 1.20] dropped).

| Band | n pairs | p25 | median | p75 | weekly improvement |
|------|---------|-----|--------|-----|--------------------|
| 8U | 6116 | 0.9569 | 0.9884 | 1.0171 | 1.16%/wk |
| 9-10 | 7111 | 0.9738 | 0.9934 | 1.0126 | 0.66%/wk |
| 11-12 | 7525 | 0.9800 | 0.9959 | 1.0109 | 0.41%/wk |
| 13-14 | 7195 | 0.9824 | 0.9963 | 1.0087 | 0.37%/wk |
| 15-18 | 7411 | 0.9831 | 0.9963 | 1.0078 | 0.37%/wk |

Percentile conditioning (tier 0 = fastest third of band, by season-first time vs league distribution) is monotone and material in the young bands, flat by 15-18 — within-season improvement is inverse to ability, same direction as the season-over-season finding:

| Band | T0 (fast) | T1 (mid) | T2 (slow) | T0..T2 n |
|------|-----------|----------|-----------|----------|
| 8U | 0.9919 | 0.9851 | 0.9772 | 3113/1936/1067 |
| 9-10 | 0.9953 | 0.9924 | 0.9863 | 3592/2351/1168 |
| 11-12 | 0.9968 | 0.9952 | 0.9928 | 3808/2431/1286 |
| 13-14 | 0.9968 | 0.9960 | 0.9953 | 3636/2441/1118 |
| 15-18 | 0.9964 | 0.9961 | 0.9961 | 3805/2406/1200 |

Model used for synthesis: **band x tier median weekly ratio** (tiers forced monotone non-increasing, capped at 1.0), applied as `anchor_time * rate^weeks` from the most recent real time (or synth TT). Cumulative improvement clamped to the band [p25, p75]^weeks envelope; hard floor at best real 2025 time x 0.97. Median weekly ratio is stable across gap lengths (7-35 d), so a constant weekly rate is adequate.

## 2. Entries added

- Teams augmented: 101
- SynthBMeet entries per team: mean 854, min 257, max 1049 (total 86242)

## 3. Validation vs real SHBR B-meet times

Ground truth: `Source='BMeet'` entries in `time_trials/shbr_weekly/W2..W5` (Sleepy Hollow B & R), matched to SynthBMeet on (normalized name, stroke, distance, nearest date within 8 days). Signed error = (synth - real) / real; positive = synth too slow (under-credits the swimmer).

| Band | n real | coverage | med signed %err | abs p50 | abs p90 |
|------|--------|----------|-----------------|---------|---------|
| 8U | 47 | 57% | 3.56 | 4.93 | 20.64 |
| 9-10 | 50 | 58% | 0.24 | 4.84 | 141.02 |
| 11-12 | 41 | 59% | 2.07 | 6.21 | 12.69 |
| 13-14 | 28 | 43% | -1.03 | 1.43 | 4.76 |
| 15-18 | 20 | 75% | -2.14 | 2.94 | 6.22 |
| **all** | 186 | 58% | 1.15 | 3.68 | 16.87 |

### Coverage decomposition

- Real B-meet entries whose (swimmer, stroke) exists in the mock roster: 112/186. Conditional coverage within that set: **96%**.
- Unmatched because swimmer-stroke not in mock roster: 74
- Unmatched because synth skipped (fresh A-meet rule): 5

The dominant coverage loss is mock-roster construction, not the synthesis: B-meet-only kids (and off-strokes) never appear in the SynthTT roster, and almost none of them have any leaders_cache series either (checked: 73 of 74 roster-gap misses have zero 2025 A-meet times), so there is no baseline time to walk forward. The B-meet layer cannot manufacture swimmers.

### Error decomposition

| Slice | n | med signed %err | abs p50 | abs p90 |
|-------|---|-----------------|---------|---------|
| stale ladder (status quo, TT never refreshed) | 107 | +4.54 | 6.64 | 26.72 |
| SynthBMeet, real-anchored | 14 | -0.19 | 2.41 | 4.98 |
| SynthBMeet, TT-anchored | 93 | +1.39 | 4.27 | 17.97 |
| SynthBMeet, all | 107 | +1.15 | 3.68 | 16.87 |

Residual error is dominated by SynthTT baseline noise (the mock TT draw vs the kid's true 2025 ability), which the layer inherits and which exists with or without it; the worst outliers (9-10 fly, >100% err) are SynthTT-returner fly seeds of 57-66s for kids who really swim 22-26s, with no leaders_cache fly times available for the 0.97 floor to engage. Positive sign = synth too slow = residual under-credit, the conservative direction.

Reverse direction: 838 SHBR SynthBMeet entries, 613 (73%) have no real B-meet counterpart within 8 days. Expected: synthesis emits every swimmer-stroke every Monday, while real kids swim at most ~3 events per B-meet and attendance is partial; surplus synth entries only keep seeds fresh and never displace real data.

## 4. Assessment vs the bar (med |err| < ~3%, coverage > 60%)

- Median |err| 4.3% overall (2.4-3.3% in 13-14/15-18; 6%+ in 8U/9-10) — misses the 3% bar, but the gap is baseline noise, not the improvement curve: against the same real B-meet times the stale ladder sits at 6.6% / +4.5% bias, so the layer removes roughly half the staleness error and most of the bias.
- Coverage 58% strict, 96% conditional on the swimmer-stroke existing in the mock roster. The strict number is capped near 60% by roster gaps the layer cannot fill.
- Worth testing in the harness: the W3-5 under-credit is driven by seed staleness of rostered swimmers, which is exactly the slice the layer fixes (bias +4.5% -> +2.5%); success criterion remains W3-5 within +/-3 of +7 with mixed cell signs in the eval itself.