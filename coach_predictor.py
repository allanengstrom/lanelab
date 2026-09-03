"""
Coach lineup predictor (v5).

Replaces the LP-based `self_optimal(opp_profiles)` predictor used by the
robust optimizer's mixture-scenario builder. The legacy predictor
over-spreads top swimmers across events; this one learns from historical
lineups and matches coach behavior much better.

Test results (390 team-weeks of 2025 dual meets, 15,181 events):
  self_optimal (legacy)  Jaccard 38.4%   ExactMatch 10.1%
  coach_predictor v5     Jaccard 53.0%   ExactMatch 22.6%

Largest win is on 50-free (33.5% → 51.2%), where real coaches concentrate
their top swimmers and self_optimal over-spread them.

API
---
    coach_predictor.predict_opp_lineup(
        team_name, year, week, profiles, events, history=None
    )  -> {event: {"swimmers": [...]}}

Pickled model is stored at MODEL_PATH and rebuilt with
`python3 train_coach_predictor.py`.

Internals — the v5 system pipeline is:
  1. Build per-team state from history (race counts, last-week, placements,
     career wins, distinct events, weeks-active timeline)
  2. Compute league baselines for z-score features
  3. For each (swimmer, event) candidate, generate 20-dim feature vector
  4. Score with HistGradientBoostingClassifier  → P(swimmer races event)
  5. Joint ILP assembly (PuLP/CBC) — maximize sum(P) subject to NVSL constraints
     (max 3/event, max 2/swimmer, max 1 stroke/swimmer)
  6. Fill any empty slots greedy by speed
"""

import json, os, math, pickle
import numpy as np
from collections import defaultdict, Counter

from Optimizer import (parse_event, is_eligible, normalize_name,
                       MAX_EVENTS, MAX_PER_EVENT)
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, PULP_CBC_CMD, value


BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "coach_predictor_model.pkl")
HISTORY_PATH = os.path.join(BASE_DIR, "nvsl_meet_history.json")
STYLES_PATH  = os.path.join(BASE_DIR, "team_styles.json")


# ─────────────────────────────────────────────────────────────────────────────
# Cached loaders
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_CACHE   = {}
_HISTORY_CACHE = {}
_STYLES_CACHE  = {}
_BASELINES_CACHE  = {}   # (year, max_week) -> baselines dict
_TEAMSTATE_CACHE  = {}   # (team, year, max_week) -> (by_se, by_s)
_PREDICTION_CACHE = {}   # (team, year, week) -> lineup dict


def _load_model():
    if "model" in _MODEL_CACHE:
        return _MODEL_CACHE["model"]
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Coach predictor model not found at {MODEL_PATH}. "
            f"Run `python3 train_coach_predictor.py` to build it.")
    with open(MODEL_PATH, "rb") as f:
        payload = pickle.load(f)

    # Warn if feature-computation code has changed since training — silent
    # train/inference drift previously caused a ~5pp Jaccard regression.
    if isinstance(payload, dict) and "trained_at" in payload:
        from datetime import datetime
        trained_ts = datetime.fromisoformat(payload["trained_at"]).timestamp()
        here = os.path.dirname(os.path.abspath(__file__))
        for dep in ("Optimizer.py", "coach_predictor.py"):
            p = os.path.join(here, dep)
            if os.path.exists(p) and os.path.getmtime(p) > trained_ts:
                print(f"[coach_predictor] WARNING: {dep} modified after model trained "
                      f"({payload['trained_at']}). Consider retraining.", flush=True)

    # Train script saves a dict; extract the model. Backward-compatible with a
    # bare-classifier pickle.
    m = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
    _MODEL_CACHE["model"] = m
    return m


def _load_history():
    if "data" in _HISTORY_CACHE:
        return _HISTORY_CACHE["data"]
    with open(HISTORY_PATH) as f:
        d = json.load(f)
    _HISTORY_CACHE["data"] = d
    return d


def _load_styles():
    if "data" in _STYLES_CACHE:
        return _STYLES_CACHE["data"]
    if not os.path.exists(STYLES_PATH):
        _STYLES_CACHE["data"] = None
        return None
    with open(STYLES_PATH) as f:
        d = json.load(f)
    _STYLES_CACHE["data"] = d
    return d


def clear_caches():
    """Forget cached predictions (call after history is updated)."""
    _BASELINES_CACHE.clear()
    _TEAMSTATE_CACHE.clear()
    _PREDICTION_CACHE.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Team consistency (leakage-safe: only uses years strictly before `year`)
# ─────────────────────────────────────────────────────────────────────────────

def team_consistency_z(team, year):
    styles = _load_styles()
    if not styles:
        return 0.0
    meta = styles.get("metadata", {})
    league_avg = meta.get("league_avg", 0.4635)
    league_std = meta.get("league_stdev", 0.1264)
    td = styles.get("teams", {}).get(team)
    if not td:
        return 0.0
    by_year = td.get("by_year", {})
    cs, ws = [], []
    for y_str, d in by_year.items():
        if int(y_str) >= year: continue
        cs.append(d.get("consistency", 0.0))
        ws.append(d.get("weight", 1.0))
    if not cs:
        return 0.0
    weighted_mean = sum(c*w for c, w in zip(cs, ws)) / sum(ws)
    return (weighted_mean - league_avg) / max(league_std, 1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# League baselines (per-event mean/std times) — cached per (year, max_week)
# ─────────────────────────────────────────────────────────────────────────────

def league_baselines(year, max_week, history=None):
    key = (year, max_week)
    if key in _BASELINES_CACHE:
        return _BASELINES_CACHE[key]
    history = history or _load_history()
    times = defaultdict(list)
    for y_str, weeks in history.items():
        y = int(y_str)
        if y > year: continue
        for wl, meets in weeks.items():
            if "Week" not in wl: continue
            wk = int(wl.replace("Week ", ""))
            if y == year and wk >= max_week:
                continue
            for m in meets.values():
                for side in ("team_a", "team_b"):
                    for ev, d in m[side].get("lineup", {}).items():
                        for s in d.get("swimmers", []):
                            t = s.get("time_sec")
                            if t and 5 < t < 600:
                                times[ev].append(t)
    base = {}
    for ev, ts in times.items():
        if len(ts) >= 5:
            base[ev] = {"mean": float(np.mean(ts)), "std": float(np.std(ts))}
    _BASELINES_CACHE[key] = base
    return base


def profile_z_in_event(profile, event, baselines):
    age, gender, stroke = parse_event(event)
    s = profile.get("strokes", {}).get(stroke)
    if not s or s.get("mean") is None:
        return None
    base = baselines.get(event)
    if not base or base.get("std", 0) <= 0:
        return None
    return (s["mean"] - base["mean"]) / base["std"]


# ─────────────────────────────────────────────────────────────────────────────
# Team-state extraction (race history per swimmer per event)
# ─────────────────────────────────────────────────────────────────────────────

def build_team_state(team, year, max_week, history=None):
    """{(sw_norm, ev): {n_races, last_week (synthetic global wk), last_place,
                         weeks_raced [], career_wins}},
       {sw_norm: {last_active_week, weeks_active [], total_races, distinct_events}}"""
    key = (team, year, max_week)
    if key in _TEAMSTATE_CACHE:
        return _TEAMSTATE_CACHE[key]
    history = history or _load_history()
    by_se = defaultdict(lambda: {"n_races": 0, "last_week": 0, "last_place": 0,
                                   "weeks_raced": [], "career_wins": 0})
    by_s  = defaultdict(lambda: {"last_active_week": 0, "weeks_active": [],
                                  "total_races": 0, "distinct_events": set()})
    for year_str, weeks in history.items():
        y = int(year_str)
        if y > year: continue
        for wl in sorted(weeks.keys(),
                          key=lambda x: int(x.split()[-1]) if "Week" in x else 0):
            if "Week" not in wl: continue
            wk = int(wl.replace("Week ", ""))
            if y == year and wk >= max_week:
                continue
            global_wk = (y - year) * 100 + wk
            for m in weeks[wl].values():
                for side in ("team_a", "team_b"):
                    if m[side].get("name") != team: continue
                    raced_this_week = set()
                    for ev, d in m[side].get("lineup", {}).items():
                        for s in d.get("swimmers", []):
                            t = s.get("time_sec")
                            if not (t and 5 < t < 600): continue
                            sw_norm = normalize_name(s["name"])
                            place = s.get("place") or 0
                            st = by_se[(sw_norm, ev)]
                            st["n_races"] += 1
                            if global_wk > st["last_week"]:
                                st["last_week"] = global_wk
                                st["last_place"] = place
                            st["weeks_raced"].append(global_wk)
                            if place == 1:
                                st["career_wins"] += 1
                            ss = by_s[sw_norm]
                            ss["total_races"] += 1
                            ss["distinct_events"].add(ev)
                            raced_this_week.add(sw_norm)
                    for sw_norm in raced_this_week:
                        ss = by_s[sw_norm]
                        if not ss["weeks_active"] or ss["weeks_active"][-1] != global_wk:
                            ss["weeks_active"].append(global_wk)
                            if global_wk > ss["last_active_week"]:
                                ss["last_active_week"] = global_wk
    result = (by_se, by_s)
    _TEAMSTATE_CACHE[key] = result
    return result


def same_event_streak(weeks_raced_in_event, current_global_wk):
    if not weeks_raced_in_event:
        return 0
    expected = current_global_wk - 1
    streak = 0
    for w in sorted(set(weeks_raced_in_event), reverse=True):
        if w == expected:
            streak += 1
            expected -= 1
        elif w < expected:
            break
    return streak


def weeks_active_in_window(weeks_active, current_global_wk, window=3):
    if not weeks_active: return 0
    target = set(range(current_global_wk - window, current_global_wk))
    return sum(1 for w in weeks_active if w in target)


# ─────────────────────────────────────────────────────────────────────────────
# Feature row (v5 = 20 features)
# ─────────────────────────────────────────────────────────────────────────────

def feature_row(team_se, team_s, sw_norm, ev, current_global_wk,
                profile_event_z, profile_min_z,
                team_consistency_z_score, event_crowding):
    st = team_se.get((sw_norm, ev), {"n_races": 0, "last_week": 0, "last_place": 0,
                                       "weeks_raced": [], "career_wins": 0})
    ss = team_s.get(sw_norm, {"last_active_week": 0, "weeks_active": [],
                                "total_races": 0, "distinct_events": set()})

    if st["last_week"] > 0:
        weeks_since = current_global_wk - st["last_week"]
        recency_in_event = 1.0 / (1.0 + weeks_since)
    else:
        weeks_since = 999
        recency_in_event = 0.0
    raced_last_week     = 1.0 if weeks_since == 1 else 0.0
    raced_two_weeks_ago = 1.0 if weeks_since == 2 else 0.0

    if ss["last_active_week"] > 0:
        weeks_since_active = current_global_wk - ss["last_active_week"]
    else:
        weeks_since_active = 999
    absent_last_week = 1.0 if weeks_since_active >= 2 else 0.0

    n_races = st["n_races"]
    total_races = ss["total_races"]
    frac_in_event = n_races / max(total_races, 1)

    last_place = st["last_place"]
    placed_top3_last  = 1.0 if last_place in (1, 2, 3) else 0.0
    placed_first_last = 1.0 if last_place == 1 else 0.0

    z = profile_event_z if profile_event_z is not None else 2.0
    z_relative = (z - profile_min_z) if profile_min_z is not None else 0.0

    weeks_active_3 = weeks_active_in_window(ss["weeks_active"], current_global_wk, 3)
    was_absent_2wk = 1.0 if weeks_since_active >= 3 else 0.0
    consecutive_absences = min(weeks_since_active, 99) if weeks_since_active < 999 else 99

    n_distinct_events = len(ss["distinct_events"])
    se_streak = same_event_streak(st["weeks_raced"], current_global_wk)

    career_wins_event = st["career_wins"]

    eligible_in_event = event_crowding.get(ev, [])
    n_eligible = len(eligible_in_event)
    speed_rank = 99
    for i, (e_sw, _t) in enumerate(eligible_in_event):
        if e_sw == sw_norm:
            speed_rank = i + 1
            break

    return [
        math.log1p(n_races),
        frac_in_event,
        math.log1p(total_races),
        recency_in_event,
        raced_last_week,
        raced_two_weeks_ago,
        absent_last_week,
        placed_top3_last,
        placed_first_last,
        z,
        z_relative,
        float(weeks_active_3),
        was_absent_2wk,
        math.log1p(consecutive_absences),
        math.log1p(n_distinct_events),
        float(se_streak),
        team_consistency_z_score,
        math.log1p(career_wins_event),
        math.log1p(n_eligible),
        float(speed_rank),
        1.0 / speed_rank if speed_rank > 0 else 0.0,
    ]

FEATURE_NAMES = [
    "log_n_races", "frac_in_event", "log_total_races",
    "recency_in_event", "raced_last_week", "raced_two_weeks_ago",
    "absent_last_week",
    "placed_top3_last", "placed_first_last",
    "z_in_event", "z_relative",
    "weeks_active_last_3", "was_absent_2wk", "log_consecutive_absences",
    "log_n_distinct_events", "same_event_streak",
    "team_consistency_z",
    "log_career_wins_event",
    "log_n_eligible_event", "speed_rank", "inv_speed_rank",
]


def compute_event_eligibility_stats(profiles, events):
    """For each event, list of (sw_norm, mean_time) sorted asc by mean."""
    out = {}
    for ev in events:
        age, gender, stroke = parse_event(ev)
        candidates = []
        for sw_raw, p in profiles.items():
            if not is_eligible(p, age, gender, stroke): continue
            mean = p.get("strokes", {}).get(stroke, {}).get("mean")
            if mean is None: continue
            candidates.append((normalize_name(sw_raw), mean))
        candidates.sort(key=lambda x: x[1])
        out[ev] = candidates
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Joint ILP assembly
# ─────────────────────────────────────────────────────────────────────────────

def _safe_var(s):
    return "".join(c if c.isalnum() else "_" for c in s)


def _assemble_ilp(candidates, events):
    """candidates: [(prob, sw_raw, event)] — return {event: {"swimmers": [...]}}."""
    if not candidates:
        return {ev: {"swimmers": []} for ev in events}
    best = {}
    for p, sw, ev in candidates:
        if (sw, ev) not in best or p > best[(sw, ev)]:
            best[(sw, ev)] = p
    swimmers = sorted({sw for (sw, _) in best})
    sw_idx = {sw: i for i, sw in enumerate(swimmers)}
    prob = LpProblem("lineup", LpMaximize)
    x = {}
    for (sw, ev), p in best.items():
        if ev not in events: continue
        x[(sw, ev)] = LpVariable(f"x_{sw_idx[sw]}_{_safe_var(ev)}", cat="Binary")
    if not x:
        return {ev: {"swimmers": []} for ev in events}
    prob += lpSum(best[(sw, ev)] * v for (sw, ev), v in x.items())
    for ev in events:
        evs = [v for (s, e), v in x.items() if e == ev]
        if evs: prob += lpSum(evs) <= MAX_PER_EVENT
    for sw in swimmers:
        sws = [v for (s, e), v in x.items() if s == sw]
        if sws: prob += lpSum(sws) <= MAX_EVENTS
    strokes = defaultdict(lambda: defaultdict(list))
    for (sw, ev), v in x.items():
        _, _, st = parse_event(ev)
        strokes[sw][st].append(v)
    for sw, m in strokes.items():
        for st, vs in m.items():
            if len(vs) > 1:
                prob += lpSum(vs) <= 1
    try:
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=10))
    except Exception:
        # Fallback to greedy
        return _greedy_assemble(candidates, events)
    out = {ev: [] for ev in events}
    for (sw, ev), v in x.items():
        val = value(v)
        if val is not None and val > 0.5:
            out[ev].append(sw)
    return {ev: {"swimmers": sws} for ev, sws in out.items()}


def _habit_by_stroke(team_se, sw_norm):
    """Recency-weighted habit score per STROKE for one swimmer, aggregated across
    age bands. Used ONLY at Week 1: with no current-season races the model's
    recency features are all blank, so predict_proba collapses into near-random
    tiny values that can bury a swimmer's real specialty (it scored a 5-year flyer
    BELOW her own rarely-swum backstroke). Career race counts + a win bonus,
    decayed by seasons-ago, recover 'what is this swimmer's event' — which is what
    a coach actually plans the W1 lineup around."""
    out = Counter()
    for (sw, ev), st in team_se.items():
        if sw != sw_norm:
            continue
        try:
            stk = parse_event(ev)[2].split("-")[-1]
        except Exception:
            continue
        # global_wk = (y-year)*100+wk, so prior seasons are negative; map the most
        # recent appearance to seasons-ago and decay (this season=1.0, last=0.6, ...).
        gmax = max(st.get("weeks_raced", [0]) or [0])
        seasons_back = 0 if gmax >= 0 else (abs(gmax) // 100) + (1 if abs(gmax) % 100 else 0)
        out[stk] += (st["n_races"] + 2.0 * st["career_wins"]) * (0.6 ** seasons_back)
    return out


def _greedy_assemble(candidates, events):
    cand = sorted(candidates, key=lambda t: -t[0])
    lineup = {ev: [] for ev in events}
    eu = Counter(); su = defaultdict(set)
    for _, sw, ev in cand:
        if ev not in events: continue
        if eu[sw] >= MAX_EVENTS: continue
        _, _, st = parse_event(ev)
        if st in su[sw]: continue
        if len(lineup[ev]) >= MAX_PER_EVENT: continue
        lineup[ev].append(sw); eu[sw] += 1; su[sw].add(st)
    return {ev: {"swimmers": sws} for ev, sws in lineup.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Main API
# ─────────────────────────────────────────────────────────────────────────────

def predict_opp_lineup(team_name, year, week, profiles, events, history=None,
                       return_candidates=False):
    """Predict what team_name's coach will assign for this week's lineup.
       profiles: built from team's data through W-1 (recency-weighted).
       events:   list of event labels we want a lineup for.
       Returns:  {event: {"swimmers": [raw_name, ...]}}"""
    cache_key = (team_name, year, week, tuple(events))
    if cache_key in _PREDICTION_CACHE and not return_candidates:
        return _PREDICTION_CACHE[cache_key]

    history   = history or _load_history()
    model     = _load_model()
    baselines = league_baselines(year, week, history)
    team_se, team_s = build_team_state(team_name, year, week, history)
    tcz = team_consistency_z(team_name, year)

    raw_for_norm = {normalize_name(sw): sw for sw in profiles.keys()}

    # min_z per swimmer (their best event z-score)
    min_z_by_sw = {}
    for sw_raw, p in profiles.items():
        sw_norm = normalize_name(sw_raw)
        zs = []
        ag = p.get("home_age_group"); g = p.get("gender")
        if ag and g:
            for st in p.get("strokes", {}):
                z = profile_z_in_event(p, f"{ag} {g} {st}", baselines)
                if z is not None: zs.append(z)
        min_z_by_sw[sw_norm] = min(zs) if zs else None

    event_crowding = compute_event_eligibility_stats(
        profiles, set(events) | {e for _sw, e in team_se.keys()})

    # At Week 1 there are no current-season races, so the model's recency features
    # are all blank and predict_proba collapses into noise that can bury known
    # specialists (see _habit_by_stroke). When there's no in-season signal at all,
    # rank candidates by career habit-by-stroke instead; the trained model is kept
    # untouched whenever real current-season data exists (W2+ in the normal case).
    has_current = any(gwk > 0 for st in team_se.values()
                      for gwk in st.get("weeks_raced", []))
    habit_cache = {}
    rows, keys, candidates = [], [], []
    for (sw_norm, ev), st in team_se.items():
        if ev not in events: continue
        if st["n_races"] == 0: continue
        sw_raw = raw_for_norm.get(sw_norm)
        if not sw_raw: continue
        age, gender, stroke = parse_event(ev)
        p = profiles.get(sw_raw)
        if not p or not is_eligible(p, age, gender, stroke): continue
        if has_current:
            z = profile_z_in_event(p, ev, baselines)
            feat = feature_row(team_se, team_s, sw_norm, ev, week, z,
                                min_z_by_sw.get(sw_norm), tcz, event_crowding)
            rows.append(feat); keys.append((sw_raw, ev))
        else:
            if sw_norm not in habit_cache:
                habit_cache[sw_norm] = _habit_by_stroke(team_se, sw_norm)
            score = habit_cache[sw_norm].get(stroke.split("-")[-1], 0.0)
            if score > 0:
                candidates.append((score, sw_raw, ev))

    if rows:
        probs = model.predict_proba(np.array(rows))[:, 1]
        candidates = [(float(p), k[0], k[1]) for p, k in zip(probs, keys)]

    lineup = _assemble_ilp(candidates, events)

    # Fill empty slots by speed (catches new swimmers w/ no history)
    # SKIP IMPUTED-source strokes: those swimmers have never raced this event;
    # a real coach wouldn't slot them ahead of someone with actual history.
    # (Imputation is still valuable for the OPTIMIZER's mixture scenarios — it
    # gives every roster swimmer a profile so the optimizer can explore them —
    # but for PREDICTING what opp will actually do, imputed strokes are noise.)
    _fill_lineup(lineup, events, profiles)

    _PREDICTION_CACHE[cache_key] = lineup
    if return_candidates:
        return lineup, candidates
    return lineup


def _fill_lineup(lineup, events, profiles):
    """Fill empty slots by speed (catches swimmers with no model history). Skips
    imputed-source strokes (a real coach wouldn't slot a never-raced phantom ahead
    of someone with real history). Two passes so a swimmer lands in their HOME band
    before being swum up. Mutates lineup in place."""
    eu = Counter(); su = defaultdict(set)
    for ev, d in lineup.items():
        for sw in d["swimmers"]:
            eu[sw] += 1
            _, _, st = parse_event(ev)
            su[sw].add(st)
    def _fill(home_only):
        for ev in events:
            if len(lineup[ev]["swimmers"]) >= MAX_PER_EVENT: continue
            age, gender, stroke = parse_event(ev)
            more = []
            for sw, p in profiles.items():
                if sw in lineup[ev]["swimmers"]: continue
                if eu[sw] >= MAX_EVENTS: continue
                if stroke in su[sw]: continue
                if not is_eligible(p, age, gender, stroke): continue
                if home_only and p.get("home_age_group") != age:
                    continue   # pass 1: only a swimmer's own band, never a swim-up
                stroke_data = p.get("strokes", {}).get(stroke, {})
                source = stroke_data.get("source", "race_data")
                if source.startswith("league_avg"):
                    continue   # skip imputed phantoms in predictor fallback
                mean = stroke_data.get("mean", 9999)
                more.append((mean, sw))
            more.sort()
            needed = MAX_PER_EVENT - len(lineup[ev]["swimmers"])
            for _, sw in more[:needed]:
                lineup[ev]["swimmers"].append(sw)
                eu[sw] += 1
                su[sw].add(stroke)
    _fill(home_only=True)
    _fill(home_only=False)


def _lineup_key(lineup):
    """Hashable signature of a lineup for dedup."""
    return frozenset((ev, sw) for ev, d in lineup.items()
                     for sw in d.get("swimmers", []))


def sample_opp_lineups(team_name, year, week, profiles, events,
                       k=5, seed=0, noise=0.40, history=None):
    """K DISTINCT plausible opp lineups sampled from the coach-predictor's
    per-(swimmer, event) probabilities: the MAP lineup plus perturbed re-assemblies
    (multiplicative log-normal noise on each candidate prob, so confident picks stay
    put and only the uncertain spots shuffle). Lets the optimizer hedge over the
    predictor's UNCERTAINTY, not just its single best guess. Returns >=1 lineup;
    fewer than k when the predictor is confident (samples collapse) — self-scaling."""
    import numpy as _np
    map_lineup, candidates = predict_opp_lineup(
        team_name, year, week, profiles, events, history=history, return_candidates=True)
    out = [map_lineup]
    if not candidates or k <= 1:
        return out
    rng = _np.random.default_rng(seed)
    seen = {_lineup_key(map_lineup)}
    tries = 0
    while len(out) < k and tries < k * 8:
        tries += 1
        pert = [(float(p) * float(_np.exp(noise * rng.standard_normal())), sw, ev)
                for (p, sw, ev) in candidates]
        lu = _assemble_ilp(pert, events)
        _fill_lineup(lu, events, profiles)
        key = _lineup_key(lu)
        if key in seen:
            continue
        seen.add(key); out.append(lu)
    return out


def sample_opp_lineups_strategic(team_name, year, week, profiles, events,
                                 k=5, seed=0, history=None, n_stars=4):
    """K DISTINCT plausible opp lineups generated by STRATEGIC STAR REDEPLOYMENT.

    Unlike sample_opp_lineups (which only multiplies each candidate's probability by
    log-normal noise — leaving the opponent's confident stars nailed to one event, so
    ~90% of the variation is the same swimmers reshuffled between events our lineup
    barely cares about), this varies the dimension our own response is actually
    sensitive to: WHERE the opponent deploys its best swimmers. It takes the MAP
    lineup, then builds variants that move a reliably-fielded swimmer to a DIFFERENT
    stroke they've actually raced and re-solves the ILP around that move (so the
    vacated event gets re-filled optimally). Returns >=1 lineup (MAP first), fewer
    than k when there are few redeployable stars (self-scaling)."""
    import numpy as _np
    map_lineup, candidates = predict_opp_lineup(
        team_name, year, week, profiles, events, history=history, return_candidates=True)
    out = [map_lineup]
    if not candidates or k <= 1:
        return out

    # best prob per (sw, ev) within our event set, and each swimmer's candidate strokes
    best = {}
    for p, sw, ev in candidates:
        if ev not in events:
            continue
        if float(p) > best.get((sw, ev), -1.0):
            best[(sw, ev)] = float(p)
    sw_events = defaultdict(list)          # sw -> [(prob, ev, stroke)]
    for (sw, ev), p in best.items():
        try:
            _, _, stroke = parse_event(ev)
        except Exception:
            continue
        sw_events[sw].append((p, ev, stroke))

    # who the MAP actually fields, and in which events
    map_place = defaultdict(list)          # sw -> [ev]
    for ev, d in map_lineup.items():
        for sw in d.get("swimmers", []):
            map_place[sw].append(ev)

    # Stars = MAP-fielded swimmers with >=2 distinct candidate strokes (i.e. genuinely
    # redeployable), ranked by how confidently the predictor places them (their
    # strongest MAP-event prob) — the swimmers a coach most reliably builds around.
    stars = []
    for sw, evs in map_place.items():
        if len({st for (_p, _e, st) in sw_events.get(sw, [])}) < 2:
            continue
        strength = max((best.get((sw, e), 0.0) for e in evs), default=0.0)
        stars.append((strength, sw))
    stars.sort(key=lambda t: -t[0])
    star_set = {sw for _s, sw in stars[:n_stars]}
    if not star_set:
        return out

    # Redeployment menu: (alt_prob, star, alt_event) for each different-stroke event a
    # star could move to (one they're NOT already swimming under the MAP). Sorted by
    # alt_prob desc so the most PLAUSIBLE redeployments become the first variants.
    moves = []
    for sw in star_set:
        map_strokes = set()
        for e in map_place.get(sw, []):
            try: map_strokes.add(parse_event(e)[2])
            except Exception: pass
        for (p, e, st) in sw_events.get(sw, []):
            if st not in map_strokes:
                moves.append((p, sw, e))
    moves.sort(key=lambda t: -t[0])
    if not moves:
        return out

    def _forced(move_set):
        """Re-solve the ILP forcing each (star -> alt_event), freeing their MAP events."""
        forced_pairs = {(sw, ev) for _p, sw, ev in move_set}
        forced_sw = {sw for _p, sw, ev in move_set}
        pert = []
        for p, sw, ev in candidates:
            if (sw, ev) in forced_pairs:
                pert.append((float(p) + 100.0, sw, ev))   # dominate: force into alt event
            elif sw in forced_sw:
                pert.append((float(p) * 1e-6, sw, ev))     # suppress their other events
            else:
                pert.append((float(p), sw, ev))
        lu = _assemble_ilp(pert, events)
        _fill_lineup(lu, events, profiles)
        return lu

    seen = {_lineup_key(map_lineup)}
    # 1) single-star moves, most plausible first (the cleanest strategic variants)
    for mv in moves:
        if len(out) >= k:
            break
        lu = _forced([mv])
        key = _lineup_key(lu)
        if key in seen:
            continue
        seen.add(key); out.append(lu)

    # 2) if still short, combine two moves from DIFFERENT stars (deeper redeployment)
    if len(out) < k and len(moves) > 1:
        rng = _np.random.default_rng(seed)
        tries = 0
        while len(out) < k and tries < k * 12:
            tries += 1
            a = int(rng.integers(0, len(moves))); b = int(rng.integers(0, len(moves)))
            if a == b or moves[a][1] == moves[b][1]:
                continue
            lu = _forced([moves[a], moves[b]])
            key = _lineup_key(lu)
            if key in seen:
                continue
            seen.add(key); out.append(lu)
    return out
