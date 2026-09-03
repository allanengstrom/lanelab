# NVSL Per-Team Participation Rates

Participation ratio = fielded individual swims / 120 lanes (40 individual events x 3 lanes; relays excluded). Season rate = mean of per-meet ratios.

## Denominator and schema checks

- Max individual swims fielded by any team in any meet: **120** (confirms 120 = 40 events x 3 lanes is the true ceiling).
- Events listing >3 swimmers (capped at 3): 2.
- Relay events found in `lineup` (skipped): 0 (lineup holds individual events only).
- No swimmer entries with missing name/place/time were found in any year; DQ/NS entries do not appear in the data, so 'fielded swims' means recorded finishes.
- 'Sully Station II' (Div 15 in 2025) appears in the divisions file but has no meets at all in nvsl_meet_history.json (only 'Sully Station', Div 10, is present). Its Div-15 opponents therefore have one fewer meet.

## 2025 league distribution of season participation rates

Teams: 101. Mean: **0.890**, median: **0.922**, min: 0.245, max: 0.993.

```
0.20-0.25  # 1
0.25-0.30   0
0.30-0.35   0
0.35-0.40   0
0.40-0.45  # 1
0.45-0.50   0
0.50-0.55   0
0.55-0.60   0
0.60-0.65  ## 2
0.65-0.70   0
0.70-0.75  ###### 6
0.75-0.80  ##### 5
0.80-0.85  ####### 7
0.85-0.90  ################# 17
0.90-0.95  ########################### 27
0.95-1.00  ################################### 35
```

## Bottom 15 teams, 2025

| Rank | Team | Division | Season rate | Mean distinct swimmers |
|---|---|---|---|---|
| 1 | Pinewood Lake | 17 | 0.245 | 16.8 |
| 2 | Edsall Park | 17 | 0.412 | 29.4 |
| 3 | Annandale | 16 | 0.613 | 39.4 |
| 4 | Springfield | 17 | 0.630 | 44.0 |
| 5 | North Springfield | 17 | 0.720 | 49.6 |
| 6 | Village West | 16 | 0.720 | 49.4 |
| 7 | Hollin Hills | 15 | 0.733 | 47.5 |
| 8 | Rolling Valley | 12 | 0.733 | 46.2 |
| 9 | Fox Mill Estates | 15 | 0.738 | 49.5 |
| 10 | Brandywine | 16 | 0.743 | 49.0 |
| 11 | Ilda Community | 16 | 0.752 | 49.2 |
| 12 | Broyhill Crest | 17 | 0.770 | 56.6 |
| 13 | Walden Glen | 11 | 0.785 | 52.0 |
| 14 | Somerset-Olde Creek | 14 | 0.788 | 52.2 |
| 15 | Rutherford | 15 | 0.796 | 55.0 |

## Top 5 teams, 2025

| Rank | Team | Division | Season rate | Mean distinct swimmers |
|---|---|---|---|---|
| 1 | Chesterbrook | 1 | 0.993 | 72.8 |
| 2 | Tuckahoe | 1 | 0.990 | 68.0 |
| 3 | Fox Hunt | 6 | 0.988 | 69.6 |
| 4 | Overlee | 1 | 0.985 | 70.6 |
| 5 | Wakefield Chapel | 2 | 0.983 | 68.2 |

## Mean 2025 participation by division

| Division | Mean rate | Min | Teams <0.80 |
|---|---|---|---|
| 1 | 0.984 | 0.973 | 0 |
| 2 | 0.961 | 0.935 | 0 |
| 3 | 0.964 | 0.950 | 0 |
| 4 | 0.950 | 0.903 | 0 |
| 5 | 0.934 | 0.888 | 0 |
| 6 | 0.960 | 0.938 | 0 |
| 7 | 0.937 | 0.885 | 0 |
| 8 | 0.921 | 0.868 | 0 |
| 9 | 0.927 | 0.825 | 0 |
| 10 | 0.908 | 0.873 | 0 |
| 11 | 0.880 | 0.785 | 1 |
| 12 | 0.847 | 0.733 | 1 |
| 13 | 0.894 | 0.869 | 0 |
| 14 | 0.896 | 0.788 | 1 |
| 15 | 0.800 | 0.733 | 3 |
| 16 | 0.764 | 0.613 | 4 |
| 17 | 0.596 | 0.245 | 5 |

Teams below 0.80 in 2025: 15; of those, 13 are in divisions 14-17.

## Sanity anchors

- Annandale 2025 season rate: **0.613** (expected ~0.6 from CALIBRATION_INVESTIGATION.md section 8). Per-meet swims: W1=72, W2=68, W3=78, W4=76, W5=74.
- Divisions 1-10 (n=60): mean 0.945; 59/60 teams in the 0.85-1.0 band (min 0.825).
- Divisions 16-17 (n=12): mean 0.680; teams: Pinewood Lake 0.24, Edsall Park 0.41, Annandale 0.61, Springfield 0.63, North Springfield 0.72, Village West 0.72, Brandywine 0.74, Ilda Community 0.75, Broyhill Crest 0.77, Long Branch 0.80, Lake Braddock 0.86, Herndon 0.90.

## Year-over-year stability

| Year pair | n teams | Pearson r |
|---|---|---|
| 2023 -> 2024 | 101 | 0.949 |
| 2024 -> 2025 | 101 | 0.964 |
| 2022 -> 2023 | 101 | 0.946 |

## Week-to-week stability within 2025

- Per-team std of per-meet ratio (teams with >=4 meets, n=99): mean **0.026**, median 0.023, 90th pct 0.048.
- League mean ratio by week, 2025: W1=0.875, W2=0.882, W3=0.895, W4=0.889, W5=0.910.
- Mean (W1 ratio - rest-of-season mean) per team: **-0.019** (n=98).

