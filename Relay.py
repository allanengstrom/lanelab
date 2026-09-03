import json
import statistics

import numpy as np

from pulp import LpProblem, LpMinimize, LpVariable, lpSum, value, PULP_CBC_CMD

AGE_GROUP_ORDER = ["8U", "9-10", "11-12", "13-14", "15-18"]
MEDLEY_LEGS     = ["back", "breast", "fly", "free"]
MC_TRIALS       = 10000
RELAY_WIN_PTS   = 5


def normalize_name(name):
    """Drop middle initials: 'Theodore R Whitfield' -> 'Theodore Whitfield'."""
    parts = name.split()
    if len(parts) <= 2:
        return name
    filtered = [parts[0]]
    for p in parts[1:-1]:
        if not (len(p.rstrip(".")) == 1 and p[0].isupper()):
            filtered.append(p)
    filtered.append(parts[-1])
    return " ".join(filtered)


def build_profiles(team_results):
    raw = {}
    for event_label, swimmers in team_results.items():
        parts = event_label.split(" ")
        age_group, gender, stroke = parts[0], parts[1], parts[2]
        for name, times in swimmers.items():
            key = normalize_name(name)
            if key not in raw:
                raw[key] = {"home_age_group": age_group, "gender": gender, "strokes": {}}
            else:
                cur_idx = AGE_GROUP_ORDER.index(raw[key]["home_age_group"])
                new_idx = AGE_GROUP_ORDER.index(age_group)
                if new_idx < cur_idx:
                    raw[key]["home_age_group"] = age_group
            raw[key]["strokes"].setdefault(stroke, []).extend(times)

    profiles = {}
    for name, data in raw.items():
        profiles[name] = {
            "home_age_group": data["home_age_group"],
            "gender": data["gender"],
            "strokes": {
                stroke: {
                    "mean": statistics.mean(times),
                    "std":  statistics.stdev(times) if len(times) > 1 else statistics.mean(times) * 0.05,
                }
                for stroke, times in data["strokes"].items()
            },
        }
    return profiles


def relay_leg_time(profile, stroke, distance_m):
    """
    Return (mean, std) for a relay leg.
    Estimates 25m from 50m by halving (and vice versa) if exact distance not available.
    """
    direct = f"{distance_m}-{stroke}"
    if direct in profile["strokes"]:
        s = profile["strokes"][direct]
        return s["mean"], s["std"]

    other_dist = 50 if distance_m == 25 else 25
    other_key  = f"{other_dist}-{stroke}"
    if other_key in profile["strokes"]:
        s      = profile["strokes"][other_key]
        factor = distance_m / other_dist
        return s["mean"] * factor, s["std"] * factor

    return None, None


def age_eligible(profile, relay_age_group, gender, swim_up):
    if profile["gender"] != gender:
        return False
    home_idx  = AGE_GROUP_ORDER.index(profile["home_age_group"])
    relay_idx = AGE_GROUP_ORDER.index(relay_age_group)
    return 0 <= relay_idx - home_idx <= 1 if swim_up else home_idx == relay_idx


# ── Relay definitions ──────────────────────────────────────────────────────────

AGE_RELAY_DEFS = {
    "8U Free":      {"age_group": "8U",    "legs": [("free", 25)] * 4,            "swim_up": False},
    "9-10 Medley":  {"age_group": "9-10",  "legs": [(s, 25) for s in MEDLEY_LEGS],"swim_up": True},
    "11-12 Medley": {"age_group": "11-12", "legs": [(s, 25) for s in MEDLEY_LEGS],"swim_up": True},
    "13-14 Medley": {"age_group": "13-14", "legs": [(s, 25) for s in MEDLEY_LEGS],"swim_up": True},
    "15-18 Medley": {"age_group": "15-18", "legs": [(s, 50) for s in MEDLEY_LEGS],"swim_up": True},
}

MIXED_SLOTS = ["9-10", "11-12", "13-14", "15-18"]


# ── Optimizers ─────────────────────────────────────────────────────────────────

def optimize_age_relays(profiles, gender):
    """
    Jointly optimize all age group relay teams for one gender.
    Each swimmer may appear in at most one age group relay leg.
    Returns {relay_name: [{"stroke", "distance", "swimmer", "mean", "std"}, ...]}
    """
    prob = LpProblem(f"age_relays_{gender}", LpMinimize)

    eligible = {
        relay_name: {
            leg_idx: {
                name: relay_leg_time(prof, stroke, dist)
                for name, prof in profiles.items()
                if age_eligible(prof, rdef["age_group"], gender, rdef["swim_up"])
                and relay_leg_time(prof, stroke, dist)[0] is not None
            }
            for leg_idx, (stroke, dist) in enumerate(rdef["legs"])
        }
        for relay_name, rdef in AGE_RELAY_DEFS.items()
    }

    x = {
        relay_name: {
            leg_idx: {
                name: LpVariable(
                    f"r_{relay_name}_{leg_idx}_{name}"
                    .replace(" ", "_").replace("-", "_").replace("&", ""),
                    cat="Binary"
                )
                for name in leg_eligible
            }
            for leg_idx, leg_eligible in legs.items()
        }
        for relay_name, legs in eligible.items()
    }

    # Each leg: at most 1 swimmer. (Not "exactly": a thin roster can have fewer
    # eligible swimmers than legs, and forcing == 1 makes the program infeasible —
    # CBC then returns garbage values that put the same swimmer on several legs.)
    for relay_name, legs in x.items():
        for leg_idx, swimmers in legs.items():
            if swimmers:
                prob += lpSum(swimmers.values()) <= 1

    # Each swimmer: at most 1 age group relay leg total
    for swimmer in profiles:
        vars_ = [
            x[relay_name][leg_idx][swimmer]
            for relay_name, legs in x.items()
            for leg_idx, swimmers in legs.items()
            if swimmer in swimmers
        ]
        if vars_:
            prob += lpSum(vars_) <= 1

    # Fill as many legs as possible, then minimize total relay time (each
    # selected leg earns a bonus far larger than any leg time, so the solver
    # only leaves a leg empty when no distinct eligible swimmer remains).
    _FILL_BONUS = 10000
    prob += lpSum(
        x[relay_name][leg_idx][name] * (t - _FILL_BONUS)
        for relay_name, legs in eligible.items()
        for leg_idx, swimmers in legs.items()
        for name, (t, s) in swimmers.items()
    )

    prob.solve(PULP_CBC_CMD(msg=0))
    _solved = prob.status == 1

    result = {}
    for relay_name, rdef in AGE_RELAY_DEFS.items():
        legs = []
        for leg_idx, (stroke, dist) in enumerate(rdef["legs"]):
            assigned = next(
                (name for name, var in x[relay_name][leg_idx].items()
                 if value(var) and value(var) > 0.5),
                None
            ) if _solved else None
            t, s = eligible[relay_name][leg_idx].get(assigned, (None, None))
            legs.append({"stroke": stroke, "distance": dist, "swimmer": assigned, "mean": t, "std": s})
        result[relay_name] = legs
    return result


def optimize_mixed_relay(profiles, gender):
    """
    Mixed age relay: one swimmer per age group slot (no swim-up), 4x50 free.
    Independent of age group relay constraint.
    Returns {slot: {"swimmer", "mean", "std"}}
    """
    prob = LpProblem(f"mixed_{gender}", LpMinimize)

    eligible = {
        slot: {
            name: relay_leg_time(prof, "free", 50)
            for name, prof in profiles.items()
            if age_eligible(prof, slot, gender, swim_up=False)
            and relay_leg_time(prof, "free", 50)[0] is not None
        }
        for slot in MIXED_SLOTS
    }

    x = {
        slot: {
            name: LpVariable(
                f"mx_{slot}_{name}".replace(" ", "_").replace("-", "_"),
                cat="Binary"
            )
            for name in swimmers
        }
        for slot, swimmers in eligible.items()
    }

    for slot, swimmers in x.items():
        if swimmers:
            prob += lpSum(swimmers.values()) <= 1

    # One slot per swimmer (belt-and-braces: slot eligibility is same-band only,
    # so this should never bind, but it makes duplicates impossible by contract)
    _names = {n for sw in x.values() for n in sw}
    for _n in _names:
        _vars = [x[slot][_n] for slot in x if _n in x[slot]]
        if len(_vars) > 1:
            prob += lpSum(_vars) <= 1

    _FILL_BONUS = 10000
    prob += lpSum(
        x[slot][name] * (t - _FILL_BONUS)
        for slot, swimmers in eligible.items()
        for name, (t, s) in swimmers.items()
    )

    prob.solve(PULP_CBC_CMD(msg=0))
    _solved = prob.status == 1

    result = {}
    for slot in MIXED_SLOTS:
        assigned = (next(
            (name for name, var in x[slot].items() if value(var) and value(var) > 0.5),
            None
        ) if _solved else None)
        t, s = eligible[slot].get(assigned, (None, None))
        result[slot] = {"swimmer": assigned, "mean": t, "std": s}
    return result


# ── Monte Carlo ────────────────────────────────────────────────────────────────

def monte_carlo_relay(your_legs, opp_legs, n=MC_TRIALS):
    """
    your_legs / opp_legs: list of (mean, std).
    Returns (win_probability, expected_points).
    """
    if not your_legs:
        return 0.0, 0.0
    your_means = np.array([m for m, _ in your_legs])
    your_stds  = np.array([s for _, s in your_legs])
    opp_means  = np.array([m for m, _ in opp_legs]) if opp_legs else np.array([0.0])
    opp_stds   = np.array([s for _, s in opp_legs]) if opp_legs else np.array([0.0])

    your_times = np.random.normal(your_means, your_stds, (n, len(your_legs))).sum(axis=1)
    opp_times  = np.random.normal(opp_means,  opp_stds,  (n, len(opp_legs))).sum(axis=1) if opp_legs else np.full(n, np.inf)

    win_prob = float((your_times < opp_times).mean())
    return win_prob, win_prob * RELAY_WIN_PTS


# ── Display ────────────────────────────────────────────────────────────────────

def display_relay(relay_name, your_legs_data, opp_legs_data, is_free_relay=False):
    your_legs = [(l["mean"], l["std"]) for l in your_legs_data if l["mean"]]
    opp_legs  = [(l["mean"], l["std"]) for l in opp_legs_data  if l["mean"]]
    win_prob, exp_pts = monte_carlo_relay(your_legs, opp_legs)

    total_time = sum(l["mean"] for l in your_legs_data if l["mean"])
    print(f"\n  {relay_name}")
    print(f"  {'Leg':<6} {'Stroke':<8} {'Swimmer':<30} {'Est.':>8}")
    for i, leg in enumerate(your_legs_data, 1):
        label  = "free" if is_free_relay else leg["stroke"]
        est    = f"{leg['mean']:.2f}s" if leg["mean"] else "N/A"
        name   = leg["swimmer"] or "— no entry —"
        print(f"  {i:<6} {label:<8} {name:<30} {est:>8}")
    print(f"  Total: {total_time:.2f}s  |  Win%: {win_prob*100:.1f}%  |  Exp pts: {exp_pts:.2f}")
    return exp_pts


def display_mixed(your_mixed, opp_mixed):
    your_legs = [(your_mixed[s]["mean"], your_mixed[s]["std"]) for s in MIXED_SLOTS if your_mixed[s]["mean"]]
    opp_legs  = [(opp_mixed[s]["mean"],  opp_mixed[s]["std"])  for s in MIXED_SLOTS if opp_mixed[s]["mean"]]
    win_prob, exp_pts = monte_carlo_relay(your_legs, opp_legs)

    total_time = sum(your_mixed[s]["mean"] for s in MIXED_SLOTS if your_mixed[s]["mean"])
    print(f"\n  Mixed Age (4x50 Free)")
    print(f"  {'Slot':<8} {'Swimmer':<30} {'Est.':>8}")
    for slot in MIXED_SLOTS:
        data = your_mixed[slot]
        est  = f"{data['mean']:.2f}s" if data["mean"] else "N/A"
        print(f"  {slot:<8} {data['swimmer'] or '— no entry —':<30} {est:>8}")
    print(f"  Total: {total_time:.2f}s  |  Win%: {win_prob*100:.1f}%  |  Exp pts: {exp_pts:.2f}")
    return exp_pts


if __name__ == "__main__":
    with open("results.json") as f:
        results = json.load(f)

    teams         = list(results.keys())
    your_profiles = build_profiles(results[teams[0]])
    opp_profiles  = build_profiles(results[teams[1]])

    grand_total = 0.0
    for gender in ["Boys", "Girls"]:
        print(f"\n{'='*60}")
        print(f"{gender} Relays — {teams[0]} vs {teams[1]}")
        print(f"{'='*60}")

        your_age   = optimize_age_relays(your_profiles, gender)
        opp_age    = optimize_age_relays(opp_profiles,  gender)
        your_mixed = optimize_mixed_relay(your_profiles, gender)
        opp_mixed  = optimize_mixed_relay(opp_profiles,  gender)

        gender_total = 0.0
        for relay_name, rdef in AGE_RELAY_DEFS.items():
            is_free = rdef["legs"][0][0] == "free" and len(set(s for s, _ in rdef["legs"])) == 1
            gender_total += display_relay(relay_name, your_age[relay_name], opp_age[relay_name], is_free)

        gender_total += display_mixed(your_mixed, opp_mixed)
        print(f"\n  {gender} relay total — Exp pts: {gender_total:.2f}")
        grand_total += gender_total

    print(f"\n{'='*60}")
    print(f"Grand total expected relay points: {grand_total:.2f}")
