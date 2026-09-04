#!/usr/bin/env python3
"""Export a demo-league matchup as meet.csv for the C scorer.
Usage: python3 export_meet_csv.py [teamA] [teamB] [week]  (run from native/)
Rows: team,swimmer,event,mean,std — top 3 per event per team by mean time.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import app
from Optimizer import build_profiles_recency_weighted, parse_event

team_a = sys.argv[1] if len(sys.argv) > 1 else "Cedar Hollow"
team_b = sys.argv[2] if len(sys.argv) > 2 else "Owl Creek"
week = int(sys.argv[3]) if len(sys.argv) > 3 else 3

rows = []
events = set()
profs = {}
for ti, team in enumerate((team_a, team_b)):
    dated, _ = app._build_team_dated_from_history(team, 2026, max_week=week)
    if dated is None:
        dated, _ = app._build_team_dated_from_history(team, 2025, max_week=None)
    profs[ti] = build_profiles_recency_weighted(dated, cur_year=2026)
    events |= set(dated.keys())

for ev in sorted(events):
    band, gender, stroke = parse_event(ev)
    for ti in (0, 1):
        cands = []
        for name, p in profs[ti].items():
            if p.get("gender") != gender or p.get("home_age_group") != band:
                continue
            st = p.get("strokes", {}).get(stroke)
            if st and st.get("mean"):
                cands.append((st["mean"], st.get("std") or st["mean"] * 0.05, name))
        for mean, std, name in sorted(cands)[:3]:
            rows.append(f'{ti},{name},{ev},{mean:.3f},{std:.3f}')

out = os.path.join("native", "meet.csv")
open(out, "w").write("\n".join(rows) + "\n")
print(f"wrote {out}: {len(rows)} entries, {len(events)} events ({team_a} vs {team_b}, W{week})")
