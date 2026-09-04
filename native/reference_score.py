#!/usr/bin/env python3
"""Pure-Python reference for mc_score.c — same model, same CSV.
Usage: python3 reference_score.py meet.csv 10000 [seed]"""
import csv, random, sys, time, collections

path, sims = sys.argv[1], int(sys.argv[2])
random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 42)

by_event = collections.defaultdict(list)
n = 0
for row in csv.reader(open(path)):
    team, name, event, mean, std = int(row[0]), row[1], row[2], float(row[3]), float(row[4])
    by_event[event].append((team, mean, std))
    n += 1

t0 = time.time()
pts = [0.0, 0.0]
for _ in range(sims):
    for entries in by_event.values():
        drawn = sorted((random.gauss(m, s), team) for team, m, s in entries)
        for place, award in enumerate((5, 3, 1)):
            if place < len(drawn):
                pts[drawn[place][1]] += award
secs = time.time() - t0
print(f"entries: {n}  events: {len(by_event)}  sims: {sims}")
print(f"expected points  team A: {pts[0]/sims:.2f}   team B: {pts[1]/sims:.2f}")
print(f"time: {secs:.3f}s  ({sims/max(secs,1e-9):.0f} sims/sec)")
