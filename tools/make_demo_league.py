#!/usr/bin/env python3
"""Generate the synthetic demo league LaneLab ships with.

Creates nvsl_meet_history.json and nvsl_divisions_by_year.json at the repo
root: 12 fictional teams in 2 divisions, seasons 2023-2026, 5 weeks each
(within-division round robin), 40 standard individual events per meet.
Swimmers are fabricated (name pools below), persist across seasons, age up
through bands, and eventually age out; every meet is actually swum — times
drawn per event around league-realistic centers, placed 5-3-1, scores summed.

Real league data is deliberately NOT included in this repository (rosters and
results identify minors). Point the app at your own league's scraped data, or
run on this demo. Deterministic: python tools/make_demo_league.py [seed]
"""
import json, os, random, sys

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20250601
R = random.Random(SEED)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIVISIONS = {
    "1": ["Cedar Hollow", "Foxglove", "Kingfisher Bay", "Juniper Ridge", "Stonebridge", "Owl Creek"],
    "2": ["Bramblewood", "Larkspur", "Pinebrook", "Quarry Lane", "Thistledown", "Marlin Cove"],
}
SEASONS = [2023, 2024, 2025, 2026]
WEEK_DATES = {y: [f"{y}-06-{d:02d}" for d in (14, 21, 28)] + [f"{y}-07-{d:02d}" for d in (5, 12)] for y in SEASONS}

BANDS = [("8U", 25, (5, 8)), ("9-10", 50, (9, 10)), ("11-12", 50, (11, 12)),
         ("13-14", 50, (13, 14)), ("15-18", 50, (15, 18))]
STROKES = ["free", "back", "breast", "fly"]
# (mean, std) seconds per band x stroke — league-realistic centers
TIME_STATS = {
    ("8U", "free"): (25.0, 6.0),  ("8U", "back"): (30.0, 7.0),
    ("8U", "breast"): (33.0, 7.0), ("8U", "fly"): (29.0, 7.5),
    ("9-10", "free"): (42.0, 7.0), ("9-10", "back"): (50.0, 8.0),
    ("9-10", "breast"): (55.0, 8.5), ("9-10", "fly"): (50.0, 9.0),
    ("11-12", "free"): (35.0, 5.5), ("11-12", "back"): (42.0, 6.5),
    ("11-12", "breast"): (46.0, 7.0), ("11-12", "fly"): (40.0, 7.0),
    ("13-14", "free"): (31.0, 4.5), ("13-14", "back"): (37.0, 5.5),
    ("13-14", "breast"): (41.0, 6.0), ("13-14", "fly"): (35.0, 5.5),
    ("15-18", "free"): (28.5, 3.5), ("15-18", "back"): (34.0, 4.5),
    ("15-18", "breast"): (38.0, 5.0), ("15-18", "fly"): (31.5, 4.5),
}

FIRST_BOYS = ["Aiden", "Bennett", "Cassius", "Dorian", "Emmett", "Flynn", "Grady", "Holden",
              "Ignatius", "Jasper", "Kellan", "Lachlan", "Merritt", "Nico", "Oberon", "Percy",
              "Quentin", "Rowan", "Soren", "Thaddeus", "Ulysses", "Vaughn", "Wilder", "Xavier",
              "York", "Zebediah", "Alaric", "Bram", "Corwin", "Dashiell"]
FIRST_GIRLS = ["Amara", "Blythe", "Calliope", "Delphine", "Elowen", "Fern", "Greta", "Halcyon",
               "Ines", "Juniper", "Kestrel", "Liora", "Marisol", "Nell", "Ophelia", "Petra",
               "Quinby", "Romilly", "Saskia", "Tamsin", "Una", "Verity", "Winnow", "Xanthe",
               "Yara", "Zinnia", "Averil", "Briar", "Clemence", "Damaris"]
LAST = ["Ashworth", "Birchall", "Coppersmith", "Dunmore", "Ellery", "Fairbanks", "Glenholme",
        "Hartwell", "Ironwood", "Jessup", "Kingsley", "Loxley", "Mabbott", "Netherfield",
        "Oakhurst", "Pemberton", "Quill", "Ravenscroft", "Silverton", "Thorneycroft",
        "Umberly", "Vandermeer", "Wexford", "Yarrow", "Zellwood", "Ambrose", "Bellweather",
        "Crowhurst", "Dovetail", "Everhart", "Foxwell", "Gildersleeve", "Hollowell"]


def top_up_rosters(league, used, year):
    """Real leagues get new young swimmers every season; without inflow the 8U
    bands drain out as the original cohort ages up. Before each season, add
    rookies to any band/gender that has fallen below target size."""
    for t, obj in league.items():
        for gender, firsts in (("Boys", FIRST_BOYS), ("Girls", FIRST_GIRLS)):
            for band, _d, (lo, hi) in BANDS:
                have = sum(1 for sw in obj["roster"] if sw["gender"] == gender
                           and band_of(sw["age2023"] + (year - 2023)) == band)
                _combos = [["back", "breast"], ["back", "fly"],
                           ["breast", "fly"], ["back", "breast", "fly"]]
                for _i in range(max(0, 8 - have)):
                    while True:
                        nm = f"{R.choice(firsts)} {R.choice(LAST)}"
                        if nm not in used:
                            used.add(nm); break
                    obj["roster"].append({"name": nm, "gender": gender,
                                          "age2023": R.randint(lo, hi) - (year - 2023),
                                          "reps": ["free"] + _combos[_i % len(_combos)],
                                          "z": R.gauss(obj["mu"], 1.0)})


def make_league():
    """Persistent rosters: swimmer = (name, gender, birth-ish age in 2023, skill z)."""
    league = {}
    used = set()
    for div, teams in DIVISIONS.items():
        for t in teams:
            # division 1 teams are a bit stronger, and teams get a persistent identity
            team_mu = (-0.55 if div == "1" else 0.35) + R.uniform(-0.35, 0.35)
            roster = []
            for gender, firsts in (("Boys", FIRST_BOYS), ("Girls", FIRST_GIRLS)):
                for band, _dist, (lo, hi) in BANDS:
                    # Rotate pet-stroke combos through the group so every stroke
                    # gets entries in every band (random draws left gaps).
                    _combos = [["back", "breast"], ["back", "fly"],
                               ["breast", "fly"], ["back", "breast", "fly"]]
                    for _i in range(R.randint(8, 10)):
                        while True:
                            nm = f"{R.choice(firsts)} {R.choice(LAST)}"
                            if nm not in used:
                                used.add(nm); break
                        # everyone swims free, plus rotating pet strokes
                        reps = ["free"] + _combos[_i % len(_combos)]
                        roster.append({"name": nm, "gender": gender,
                                       "age2023": R.randint(lo, hi),
                                       "reps": reps,
                                       "z": R.gauss(team_mu, 1.0)})
            league[t] = {"division": div, "mu": team_mu, "roster": roster}
    return league, used


def band_of(age):
    for band, _d, (lo, hi) in BANDS:
        if lo <= age <= hi:
            return band
    return None


def swim_time(band, stroke, z):
    mu, sd = TIME_STATS[(band, stroke)]
    return max(mu * 0.55, mu + z * sd * 0.55 + R.gauss(0, sd * 0.18))


def run_meet(league, a, b, year, date, mid):
    sides = {}
    for tname in (a, b):
        entries = {}
        for sw in league[tname]["roster"]:
            band = band_of(sw["age2023"] + (year - 2023))
            if band is None:
                continue
            dist = next(d for bd, d, _ in BANDS if bd == band)
            if R.random() < 0.12:      # a no-show week
                continue
            strokes = R.sample(sw["reps"], 2)   # two individual events, from their repertoire
            for st in strokes:
                ev = f"{band} {sw['gender']} {dist}-{st}"
                entries.setdefault(ev, []).append((swim_time(band, st, sw["z"]), sw["name"]))
        sides[tname] = entries
    scores = {a: 0, b: 0}
    lineups = {a: {}, b: {}}
    for band, dist, _ in BANDS:
        for gender in ("Boys", "Girls"):
            for st in STROKES:
                ev = f"{band} {gender} {dist}-{st}"
                field = []
                for tname in (a, b):
                    top3 = sorted(sides[tname].get(ev, []))[:3]
                    field += [(t, nm, tname) for t, nm in top3]
                    if top3:
                        lineups[tname][ev] = {"swimmers": []}
                field.sort()
                for place, (t, nm, tname) in enumerate(field, 1):
                    if place <= 3:
                        scores[tname] += (5, 3, 1)[place - 1]
                    lineups[tname].setdefault(ev, {"swimmers": []})
                    lineups[tname][ev]["swimmers"].append(
                        {"name": nm, "place": place, "time_str": f"{t:.2f}", "time_sec": round(t, 2)})
    def teamrec(tname):
        n_swims = sum(len(v["swimmers"]) for v in lineups[tname].values())
        return {"code": "".join(w[0] for w in tname.split()), "name": tname,
                "score": float(scores[tname]), "lineup": lineups[tname],
                "n_events": 40, "n_swims": n_swims}
    return {"team_a": teamrec(a), "team_b": teamrec(b),
            "winner": a if scores[a] >= scores[b] else b,
            "match_reason": "demo round-robin", "date": date, "meet_id": mid}


def main():
    league, used = make_league()
    history, mid = {}, 90001
    for year in SEASONS:
        top_up_rosters(league, used, year)
        history[str(year)] = {}
        for wk in range(1, 6):
            wl = f"Week {wk}"
            history[str(year)][wl] = {}
            for div, teams in DIVISIONS.items():
                rot = teams[:1] + teams[1:][wk - 1:] + teams[1:][:wk - 1]   # round robin
                pairs = [(rot[i], rot[-(i + 1)]) for i in range(3)]
                for a, b in pairs:
                    m = run_meet(league, a, b, year, WEEK_DATES[year][wk - 1], mid)
                    history[str(year)][wl][str(mid)] = m
                    mid += 1
    json.dump(history, open(os.path.join(ROOT, "nvsl_meet_history.json"), "w"))
    json.dump({str(y): DIVISIONS for y in SEASONS},
              open(os.path.join(ROOT, "nvsl_divisions_by_year.json"), "w"), indent=1)
    n = sum(len(w) for y in history.values() for w in y.values())
    print(f"demo league written: {len(league)} teams, {len(SEASONS)} seasons, {n} meets, seed {SEED}")


if __name__ == "__main__":
    main()
