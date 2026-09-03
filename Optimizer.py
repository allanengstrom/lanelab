import os
import json
import statistics
import numpy as np
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, value, PULP_CBC_CMD

AGE_GROUP_ORDER = ["8U", "9-10", "11-12", "13-14", "15-18"]
POINTS          = {1: 5, 2: 3, 3: 1, 4: 0, 5: 0, 6: 0}
MAX_EVENTS      = 2
MAX_PER_EVENT   = 3
FILL_BONUS      = 0.001
MC_N            = 5000    # trials for pre-computation
MC_DISPLAY_N    = 10000   # trials for final display
MC_TOP_N        = 6       # max swimmers per event considered for MC
TARGET_SCORE    = 210     # individual-event point target for risky mode

# ── Per-swim spread control (gated; identity by default) ─────────────────────────
# The per-swimmer time spread used by the MC. By default swimmers keep the std the
# profile builder assigned (real weighted stdev for multi-swim swimmers; a flat 5%
# of mean for single-swim/imputed ones). That flat 5% is ~2-3x too wide for a 50
# and makes the MC treat clear favorites/underdogs as near coin-flips (a 32 beats a
# 30.2 ~40% of the time), which both over-states per-event odds and feeds phantom
# upsets into the predicted total. These knobs let the spread be tightened without
# editing the builders; both unset → behavior is byte-identical to before.
#   SIM_CV_SET=<cv>  force every swim's std to mean*cv (uniform spread)
#   SIM_CV_CAP=<cv>  cap each std at mean*cv (only tighten the over-wide ones)
_CV_SET = os.environ.get("SIM_CV_SET")
_CV_CAP = os.environ.get("SIM_CV_CAP")
_CV_SET = float(_CV_SET) if _CV_SET not in (None, "") else None
_CV_CAP = float(_CV_CAP) if _CV_CAP not in (None, "") else None


def _spread_adjust(means, stds):
    """Apply the gated spread control. Identity when neither knob is set."""
    if _CV_SET is not None:
        return means * _CV_SET
    if _CV_CAP is not None:
        return np.minimum(stds, means * _CV_CAP)
    return stds


# Age-graduated single-swim spread (gated). Single-swim/imputed swimmers get a flat
# 5%-of-time CV by default — roughly right for 8U but ~2-3x too wide for teens (a 32
# "beats" a 30.2 ~40% of the time). With SIM_CV_AGEGRAD set, the single-swim CV is
# derived from the per-age/gender trim bands (_TRIM_BAND, below): 8U stays wide
# (~6.5%), teens tighten to ~2%. factor 0.4 puts 13-14 (band .05) at 2%. Identity
# (flat 0.05) when off, so default behavior is byte-identical.
_CV_AGEGRAD = os.environ.get("SIM_CV_AGEGRAD", "1") == "1"   # shipped on 2026-06: age-graded per-swim spread (8U wide, teens ~2%); fixes per-event overconfidence. SIM_CV_AGEGRAD=0 to revert.
_CV_AGEGRAD_FACTOR = float(os.environ.get("SIM_CV_AGEGRAD_FACTOR", "0.4"))


def _single_cv(age_group=None, gender=None):
    if _CV_AGEGRAD and age_group is not None:
        return _TRIM_BAND.get((age_group, gender), _TRIM_BAND_DEFAULT) * _CV_AGEGRAD_FACTOR
    return 0.05


# 8U times PROJECTED from a prior season run ~17-20% too slow (multi-year W1 profile-vs-
# actual medians: 2023 +5%, 2024 +12%, 2025 +17% — the most-complete year is worst; 8U
# improve enormously year-over-year and the same-distance curve is too sparse to fire at
# that age). Speed up 8U PROJECTIONS (strokes with NO current-season swim) by this factor.
# 0.88 corrects the bulk while staying conservative vs over-speeding kids who didn't jump.
# Applied in build_profiles_recency_weighted only when cur_year is passed AND the latest
# obs predates it (a true projection); current-season 8U swims are untouched. Env-tunable.
_8U_PROJ_FACTOR = float(os.environ.get("SIM_8U_PROJ_FACTOR", "0.88"))

# ── Empirical year-over-year scaling factors (shared with app._apply_age_up_correction) ──
# DIST_GROWTH_25_TO_50: combined factor for the FIRST band step where distance
# also changes (25 → 50). Includes one year of growth. Source: measured medians
# across NVSL 2019-2025 with n=2393.
DIST_GROWTH_25_TO_50 = {"free": 2.03, "back": 1.97, "breast": 1.96, "fly": 2.12}

# GROWTH_ONLY: per (from_band, to_band, stroke) growth-only ratios for same-distance
# transitions. Source: measured medians.
GROWTH_ONLY = {
    ("8U",    "9-10",  "fly"):    0.85,
    ("9-10",  "11-12", "free"):   0.928,
    ("9-10",  "11-12", "back"):   0.924,
    ("9-10",  "11-12", "breast"): 0.919,
    ("11-12", "13-14", "free"):   0.950,
    ("11-12", "13-14", "back"):   0.945,
    ("11-12", "13-14", "breast"): 0.938,
    ("11-12", "13-14", "fly"):    0.931,
    ("13-14", "15-18", "free"):   0.981,
    ("13-14", "15-18", "back"):   0.976,
    ("13-14", "15-18", "breast"): 0.978,
    ("13-14", "15-18", "fly"):    0.974,
}


def _expected_dist(band, stroke_short):
    """Distance for a stroke in a given band (NVSL rules)."""
    if band == "8U": return 25
    if band == "9-10": return 25 if stroke_short == "fly" else 50
    return 50


def _growth_factor(from_b, to_b, stroke_short):
    """Compose growth-only scaling across one or more single-band steps."""
    fi, ti = AGE_GROUP_ORDER.index(from_b), AGE_GROUP_ORDER.index(to_b)
    if ti <= fi: return 1.0
    f = 1.0
    for i in range(fi, ti):
        step = GROWTH_ONLY.get((AGE_GROUP_ORDER[i], AGE_GROUP_ORDER[i+1], stroke_short), 0.95)
        f *= step
    return f


def _scale_prior_band_time(t, from_band, to_band, stroke_short):
    """Scale a swimmer's prior-band time forward to their current band.

    Handles two cases: same distance (growth-only) and 25→50 (combined factor
    for the first step, then growth-only for any further steps)."""
    fi = AGE_GROUP_ORDER.index(from_band)
    ti = AGE_GROUP_ORDER.index(to_band)
    if fi >= ti: return t
    fd = _expected_dist(from_band, stroke_short)
    td = _expected_dist(to_band, stroke_short)
    if fd == td:
        return t * _growth_factor(from_band, to_band, stroke_short)
    elif fd == 25 and td == 50:
        combined = DIST_GROWTH_25_TO_50.get(stroke_short, 2.02)
        next_band = AGE_GROUP_ORDER[fi + 1]
        extra = _growth_factor(next_band, to_band, stroke_short)
        return t * combined * extra
    return t


# ── Profiles ───────────────────────────────────────────────────────────────────

def parse_event(label):
    parts = label.split(" ")
    return parts[0], parts[1], parts[2]


# Common nicknames -> formal first names. Reconciles the SwimTopia ladder (uses
# PREFERRED names, e.g. "Nick Ferrante") with meet history / leaders cache (use
# REGISTERED names, "Nicholas S Ferrante"). Without this the same swimmer splits
# into two identities — one with ladder data, one stuck in the impute list.
# Conservative, high-confidence entries only (ambiguous ones like Nate/Max omitted).
_NICKNAMES = {
    "nick": "nicholas", "nicky": "nicholas", "alex": "alexander", "xander": "alexander",
    "will": "william", "bill": "william", "billy": "william", "liam": "william",
    "ben": "benjamin", "benny": "benjamin", "sam": "samuel", "sammy": "samuel",
    "tom": "thomas", "tommy": "thomas", "mike": "michael", "matt": "matthew",
    "chris": "christopher", "dan": "daniel", "danny": "daniel", "joe": "joseph",
    "joey": "joseph", "charlie": "charles", "josh": "joshua", "andy": "andrew",
    "drew": "andrew", "tony": "anthony", "gabe": "gabriel", "zach": "zachary",
    "zack": "zachary", "jake": "jacob", "ted": "theodore", "teddy": "theodore",
    "eddie": "edward", "ed": "edward", "greg": "gregory", "jeff": "jeffrey",
    "nate": "nathan", "vinny": "vincent", "dom": "dominic", "ollie": "oliver",
    "kate": "katherine", "katie": "katherine", "kat": "katherine", "liz": "elizabeth",
    "lizzie": "elizabeth", "beth": "elizabeth", "maggie": "margaret", "abby": "abigail",
    "izzy": "isabella", "isa": "isabella", "bella": "isabella",
    "becca": "rebecca", "cici": "cecilia", "ellie": "eleanor", "nora": "eleanor",
    "mia": "amelia", "gabby": "gabriella", "annie": "anna", "sophie": "sophia",
}


def normalize_name(name):
    """Drop middle initials and map common nicknames to formal first names:
    'Theodore R Whitfield' -> 'Theodore Whitfield'; 'Nick Ferrante' -> 'Nicholas Ferrante'."""
    parts = name.split()
    if not parts:
        return name
    filtered = [parts[0]]
    for p in parts[1:-1]:
        if not (len(p.rstrip(".")) == 1 and p[0].isupper()):
            filtered.append(p)
    if len(parts) >= 2:
        filtered.append(parts[-1])
    # Canonicalize a nickname first name (preserve original capitalization style).
    formal = _NICKNAMES.get(filtered[0].lower())
    if formal and len(filtered) >= 2:
        filtered[0] = formal.capitalize()
    return " ".join(filtered)


def build_profiles(team_results):
    raw = {}
    for event_label, swimmers in team_results.items():
        age_group, gender, stroke = parse_event(event_label)
        for name, times in swimmers.items():
            key = normalize_name(name)
            if key not in raw:
                raw[key] = {"home_age_group": age_group, "gender": gender, "strokes": {}}
            else:
                cur_idx = AGE_GROUP_ORDER.index(raw[key]["home_age_group"])
                new_idx = AGE_GROUP_ORDER.index(age_group)
                # home_age_group should reflect the swimmer's CURRENT age group,
                # which (since data scans forward) is the HIGHEST age group seen.
                # Bug pre-Aug-2026: this used `<`, keeping the YOUNGEST age group as
                # home — so a swimmer with multi-year history (e.g., Wentland 9-10
                # → 11-12 → 13-14) was stuck at 9-10 and got filtered out by the
                # swim-up eligibility check for their current events.
                if new_idx > cur_idx:
                    raw[key]["home_age_group"] = age_group
            # Tag each time with the event age_group so we can filter cross-age-group
            # noise later (see note in build_profiles_recency_weighted).
            raw[key]["strokes"].setdefault(stroke, []).extend(
                (t, age_group) for t in times
            )

    profiles = {}
    for name, data in raw.items():
        home_idx = AGE_GROUP_ORDER.index(data["home_age_group"])
        allowed_ages = set()
        for delta in (0, 1):   # current age group + swim-up only
            j = home_idx + delta
            if 0 <= j < len(AGE_GROUP_ORDER):
                allowed_ages.add(AGE_GROUP_ORDER[j])
        strokes = {}
        for stroke, ttuples in data["strokes"].items():
            times = [t for t, ag in ttuples if ag in allowed_ages]
            if not times:
                continue
            strokes[stroke] = {
                "mean": statistics.mean(times),
                "std":  statistics.stdev(times) if len(times) > 1 else statistics.mean(times) * _single_cv(data["home_age_group"], data["gender"]),
            }
        profiles[name] = {
            "home_age_group": data["home_age_group"],
            "gender":         data["gender"],
            "strokes":        strokes,
        }
    return profiles


# Per-age-group/gender "best-anchored" trim band. A time slower than a swimmer's
# best (for that stroke) by more than this fraction is dropped as stale/outlier
# before recency-weighting — e.g. last season's slower times once a current-season
# time trial exists. Derived from 5 years of NVSL data: each band ≈ that group's
# within-season 90th-percentile race-to-race spread, so it keeps normal race
# variation but cuts the rest. Young swimmers vary (and improve) far more, so
# their bands are wider; teenagers barely improve, so theirs are tight and rarely
# fire (their year-old times are still accurate).
_TRIM_BAND = {
    ("8U",    "Boys"): 0.17, ("8U",    "Girls"): 0.16,
    ("9-10",  "Boys"): 0.10, ("9-10",  "Girls"): 0.09,
    ("11-12", "Boys"): 0.07, ("11-12", "Girls"): 0.07,
    ("13-14", "Boys"): 0.06, ("13-14", "Girls"): 0.05,
    ("15-18", "Boys"): 0.05, ("15-18", "Girls"): 0.05,
}
_TRIM_BAND_DEFAULT = 0.08


def _latest_season_only(filtered):
    """Keep only observations from the most recent SEASON (calendar year). A
    current-season swim (e.g. this year's time trial) fully supersedes prior
    seasons — a year-old time, even a close one, reflects a younger swimmer.
    Prior-season times are used only when there's no current-season data for the
    stroke. `filtered` is a list of (date, time); dates are 'YYYY-MM-DD' or
    'YYYYMMDD', both of which start with the 4-digit year."""
    if len(filtered) <= 1:
        return filtered
    latest = max(str(d)[:4] for d, _ in filtered)
    return [(d, t) for (d, t) in filtered if str(d)[:4] == latest]


def _trim_to_best_band(filtered, age_group, gender):
    """Drop times slower than best*(1+band) for this age/gender group, but ALWAYS
    keep the single most-recent swim (so a swimmer who genuinely got slower isn't
    pinned to a stale fast time). `filtered` is a list of (date, time). Returns the
    surviving list (never empty)."""
    if len(filtered) <= 1:
        return filtered
    band   = _TRIM_BAND.get((age_group, gender), _TRIM_BAND_DEFAULT)
    best   = min(t for _, t in filtered)
    cutoff = best * (1.0 + band)
    latest = max(filtered, key=lambda x: x[0])          # most-recent observation
    kept   = [(d, t) for (d, t) in filtered if t <= cutoff or (d, t) == latest]
    return kept or filtered


def build_profiles_recency_weighted(team_results_dated, decay=0.7, cur_year=None):
    """
    Like build_profiles, but each time has a date and recent times are weighted more.

    team_results_dated: {event_label: {swimmer_name: [(sortable_date, time), ...]}}
    decay: per-step decay factor. Most recent obs gets weight 1.0, one back gets
           weight `decay`, two back gets `decay**2`, etc.
           - decay=0.7 → moderate recency (W2 ~59%, W1 ~41% with 2 obs)
           - decay=0.5 → aggressive recency (W2 ~67%, W1 ~33%)
           - decay=1.0 → equivalent to simple mean (no recency)

    Returns the same profile structure as build_profiles, but with recency-weighted
    mean and stdev.
    """
    import math
    import re as _re
    def _season_year(d):
        m = _re.search(r"(?:19|20)\d{2}", str(d))
        return int(m.group(0)) if m else None

    raw = {}
    for event_label, swimmers in team_results_dated.items():
        age_group, gender, stroke = parse_event(event_label)
        band_idx = AGE_GROUP_ORDER.index(age_group)
        for name, dated_times in swimmers.items():
            key = normalize_name(name)
            if key not in raw:
                raw[key] = {"home_age_group": age_group, "gender": gender,
                            "strokes": {}, "_band_seasons": []}
            # Record (season_year, band_idx) per observation so we can resolve the
            # native band as the LOWEST band raced in the MOST RECENT season. A
            # swimmer can only swim UP within a season, so the lowest band they
            # appear in that season IS their real age group — the highest may just
            # be a swim-up. (Across seasons, aging is handled by preferring the
            # latest season.) Taking "highest band ever" instead conflated a
            # one-off swim-up with aging up, mis-homing the swimmer a band too high
            # AND dropping their native-band times as "wrong band."
            for d, _t in dated_times:
                raw[key]["_band_seasons"].append((_season_year(d), band_idx))
            # Tag each observation with its event age_group so we can later filter
            # out times from age groups too far below the swimmer's current group
            # (a 14-yr-old's 9-10 50-free at age 10 is NOT representative of their
            # current 13-14 ability).
            raw[key]["strokes"].setdefault(stroke, []).extend(
                (d, t, age_group) for d, t in dated_times
            )

    # Resolve home band = lowest band in the most recent real season. Sentinel
    # "no-date" years (>= 2090, e.g. undated ladder entries) don't define a season;
    # if a swimmer has only those, fall back to the old highest-band-ever rule.
    for _key, _data in raw.items():
        _bs = _data.pop("_band_seasons", [])
        _real = [(y, b) for (y, b) in _bs if y is not None and y < 2090]
        if _real:
            _latest = max(y for y, _b in _real)
            _home_idx = min(b for y, b in _real if y == _latest)
        elif _bs:
            _home_idx = max(b for _y, b in _bs)
        else:
            continue
        _data["home_age_group"] = AGE_GROUP_ORDER[_home_idx]

    profiles = {}
    for name, data in raw.items():
        home = data["home_age_group"]
        home_idx = AGE_GROUP_ORDER.index(home)
        # Keep times from the swimmer's CURRENT age group and any swim-up races
        # they did (one tier above home). Drop everything from prior age groups —
        # a kid's 11-12 50-free at age 12 is a different swimmer from their 13-14
        # 50-free at age 14.
        #
        # CARRY-FORWARD (added 2026-06): When a swimmer has NO current-band data
        # for a stroke but DOES have prior-band data, scale the prior-band time
        # forward via empirical growth factors instead of dropping. Without this,
        # aged-up swimmers like a former-13-14 in 15-18 who hasn't raced breast
        # yet this season got imputed at the league baseline (the well-known
        # "5-way tie at 43.03" problem). With it, we use their actual prior
        # ability translated to the current band.
        allowed_ages = set()
        for delta in (0, 1):
            j = home_idx + delta
            if 0 <= j < len(AGE_GROUP_ORDER):
                allowed_ages.add(AGE_GROUP_ORDER[j])

        strokes = {}
        # Process strokes that HAVE current-band data first, so a swimmer's real
        # current time always claims its out_key before any carry-forward writes to
        # it. A carry-forward stroke_key can map to the SAME out_key as a real one
        # (e.g. an aged-up 8U swimmer's scaled "25-back" -> "50-back" vs their real
        # "50-back" time trial); the `out_key not in strokes` guard below keeps
        # whichever lands first, so real data must go first or the scaled — and
        # wrongly faster — estimate would overwrite it.
        def _has_current(dated_obs):
            return any(ag in allowed_ages for _d, _t, ag in dated_obs)
        ordered_strokes = sorted(data["strokes"].items(),
                                 key=lambda kv: 0 if _has_current(kv[1]) else 1)
        for stroke_key, dated_obs in ordered_strokes:
            # stroke_key is like "50-back" or "25-fly". Split into distance + stroke_short.
            if "-" in stroke_key:
                _, stroke_short = stroke_key.split("-", 1)
            else:
                stroke_short = stroke_key

            # Try current-band data first (existing behavior).
            current_filtered = [(d, t) for d, t, ag in dated_obs if ag in allowed_ages]
            if current_filtered:
                filtered = current_filtered
                out_key = stroke_key  # keep original distance from current-band obs
            else:
                # Carry forward: collect any prior-band obs, scale each to home band.
                prior_obs = [(d, t, ag) for d, t, ag in dated_obs
                             if ag in AGE_GROUP_ORDER and AGE_GROUP_ORDER.index(ag) < home_idx]
                if not prior_obs:
                    continue
                filtered = [(d, _scale_prior_band_time(t, ag, home, stroke_short))
                            for d, t, ag in prior_obs]
                # Output key uses the home band's expected distance for this stroke.
                out_key = f"{_expected_dist(home, stroke_short)}-{stroke_short}"

            # Season precedence: once there's a current-season swim for this
            # stroke, drop prior seasons entirely (a year-old time is a younger,
            # slower swimmer). Then band-trim any remaining in-season slow
            # outliers. Together these keep the swimmer at their demonstrated
            # current ability instead of a year-spanning average.
            filtered = _latest_season_only(filtered)
            filtered = _trim_to_best_band(filtered, home, data["gender"])
            sorted_obs = sorted(filtered, key=lambda x: x[0], reverse=True)
            times = [t for _, t in sorted_obs]
            # 8U projection speed-up: only for an 8U swimmer's 8U EVENTS (25-yard, so a
            # swim-up 50 is excluded) AND only when these are PRIOR-season obs (no current
            # swim). Scales times => mean & std both scale (CV held).
            if (home == "8U" and out_key.startswith("25-") and cur_year is not None
                    and sorted_obs and int(str(sorted_obs[0][0])[:4]) < int(cur_year)):
                times = [t * _8U_PROJ_FACTOR for t in times]
            n = len(times)
            weights = [decay ** i for i in range(n)]
            wsum = sum(weights)
            mean = sum(w * t for w, t in zip(weights, times)) / wsum
            if n > 1:
                wvar = sum(w * (t - mean) ** 2 for w, t in zip(weights, times)) / wsum
                std = math.sqrt(wvar)
                # Avoid degenerate near-zero stdev (would make MC trivial)
                std = max(std, mean * 0.02)
            else:
                std = mean * _single_cv(home, data["gender"])
            # When both current-band and prior-band write to the same out_key
            # (rare: e.g. a swimmer in 9-10 with both 9-10 50-fly AND 8U 25-fly
            # scaled to 50-fly), keep the current-band entry (already written first
            # since current_filtered was checked before prior fallback).
            if out_key not in strokes:
                strokes[out_key] = {"mean": mean, "std": std}
        profiles[name] = {
            "home_age_group": home,
            "gender": data["gender"],
            "strokes": strokes,
        }
    return profiles


def is_eligible(profile, age_group, gender, stroke):
    if profile["gender"] != gender:
        return False
    if stroke not in profile["strokes"]:
        return False
    home_idx  = AGE_GROUP_ORDER.index(profile["home_age_group"])
    event_idx = AGE_GROUP_ORDER.index(age_group)
    if not (0 <= event_idx - home_idx <= 1):
        return False
    # 8U swim-up restriction (empirical: only 0.4% of 8U swims are swim-ups, and 35%
    # of those are 25-fly which keeps the same distance). Block 8U swimmers from
    # entering 9-10 events at 50m (distance doubles — rare/unrealistic in practice).
    if profile["home_age_group"] == "8U" and age_group == "9-10":
        if stroke.startswith("50-"):
            return False
    return True


# ── Deterministic points (used by medium mode and optimizer internals) ─────────

def race_points(your_means, opp_means):
    all_times = [(t, "yours") for t in your_means] + [(t, "opp") for t in opp_means]
    all_times.sort(key=lambda x: x[0])
    return sum(POINTS.get(i + 1, 0) for i, (_, team) in enumerate(all_times) if team == "yours")


# ── Distribution choice ───────────────────────────────────────────────────────

def _is_lognormal_event(age_group, stroke):
    """
    Should this event's swim times be sampled from log-normal (right-skewed)
    instead of symmetric normal? Based on variance-asymmetry analysis of 5 years
    of NVSL meet data:
      - 8U all strokes: positive skew (median +0.27%, 8U fly/breast +0.35%)
      - 9-10 25-fly: mild skew (+0.19%)
      - All other ages/strokes: near-symmetric, keep normal
    """
    if age_group == "8U":
        return True
    if age_group == "9-10" and stroke == "25-fly":
        return True
    return False


def _sample_times(means, stds, n, use_lognormal=False, crn_norms=None):
    """
    Sample n trial-times for each of len(means) swimmers.
    Returns array of shape (n, len(means)).
    Normal distribution by default; log-normal when use_lognormal=True
    (right-skewed, slow tail heavier than fast tail).

    Log-normal parameters chosen so that the returned distribution has the
    same mean and stdev as a normal would (just a different shape).

    If crn_norms is supplied, it must be an (n, len(means)) array of N(0,1)
    draws. We then apply a deterministic transform — same swimmer + same row
    of crn_norms → same time, every call. That's Common Random Numbers:
    canceling MC noise from paired lineup comparisons.
    """
    means = np.asarray(means, dtype=float)
    stds  = np.asarray(stds, dtype=float)
    stds  = _spread_adjust(means, stds)
    if crn_norms is not None:
        if not use_lognormal:
            return means + stds * crn_norms
        sigma_log_sq = np.log(1.0 + (stds / means) ** 2)
        sigma_log    = np.sqrt(sigma_log_sq)
        mu_log       = np.log(means) - 0.5 * sigma_log_sq
        return np.exp(mu_log + sigma_log * crn_norms)
    # Fallback: fresh random draws (legacy behavior).
    if not use_lognormal:
        return np.random.normal(means, stds, (n, len(means)))
    sigma_log_sq = np.log(1.0 + (stds / means) ** 2)
    sigma_log    = np.sqrt(sigma_log_sq)
    mu_log       = np.log(means) - 0.5 * sigma_log_sq
    return np.random.lognormal(mu_log, sigma_log, (n, len(means)))


# ── Monte Carlo ────────────────────────────────────────────────────────────────

def _pts_map(total):
    return np.array([POINTS.get(i + 1, 0) for i in range(total)], dtype=float)


_DQ_RATES = None
def _finish_rate(age_group, stroke):
    """P(a swimmer finishes, i.e. not DQ) for (band, stroke); 1.0 = no DQ. Loaded
    from dq_finish_rates.json (8U technical strokes only in v1). `stroke` may be
    '25-fly' or 'fly'. Returns 1.0 for anything not in the table."""
    global _DQ_RATES
    if _DQ_RATES is None:
        import os, json
        try:
            _DQ_RATES = json.load(open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "dq_finish_rates.json")))
        except Exception:
            _DQ_RATES = {}
    if not age_group or not stroke:
        return 1.0
    return float(_DQ_RATES.get(age_group, {}).get(str(stroke).split("-")[-1], 1.0))


def _dq_adjust(times, finish_rate):
    """DQ model: each swimmer finishes w.p. finish_rate; a DQ'd swimmer gets +inf
    time (ranks last) and is later zeroed from points so the place-points pie
    shrinks (the unfilled place scores nothing — correct NVSL behavior). Applied to
    EVERY swimmer in the event, so it's symmetric across both teams. Returns
    (times, finish_mask); finish_mask is None when finish_rate>=0.999 so callers do
    nothing — keeping non-DQ events byte-identical to before."""
    if finish_rate >= 0.999:
        return times, None
    finish = np.random.random(times.shape) < finish_rate
    return np.where(finish, times, np.inf), finish


def mc_event(your_entries, opp_entries, n=MC_DISPLAY_N, age_group=None, stroke=None):
    """
    your_entries / opp_entries: list of (mean, std) tuples.
    Returns (expected_pts, win_probability).

    age_group + stroke (optional): if provided, decides whether to use log-normal
    sampling for this event (8U + 9-10 25-fly = right-skewed per data).
    Pass None to keep legacy normal-distribution behavior.
    """
    if not your_entries:
        return 0.0, 0.0

    n_yours = len(your_entries)
    total   = n_yours + len(opp_entries)

    all_means = np.array([m for m, _ in your_entries] + [m for m, _ in opp_entries])
    all_stds  = np.array([s for _, s in your_entries] + [s for _, s in opp_entries])

    use_log  = (age_group is not None) and _is_lognormal_event(age_group, stroke or "")
    times    = _sample_times(all_means, all_stds, n, use_lognormal=use_log)
    times, finish = _dq_adjust(times, _finish_rate(age_group, stroke))
    ranks    = np.argsort(np.argsort(times, axis=1), axis=1)
    pts_grid = _pts_map(total)[ranks]
    if finish is not None:
        pts_grid = np.where(finish, pts_grid, 0.0)
    your_pts = pts_grid[:, :n_yours].sum(axis=1)

    total_pts = pts_grid.sum(axis=1)
    win_prob  = float((your_pts > total_pts - your_pts).mean())
    return float(your_pts.mean()), win_prob


# ── Meet-level simulation & win-probability optimizer ─────────────────────────

def _sim_event_our_pts(combo, opp_entries, your_profiles, stroke, n, age_group=None):
    """Simulate one event; return our pts array of shape (n,).
    age_group (optional): if provided, uses log-normal for 8U + 9-10 25-fly."""
    your_ents = [
        (your_profiles[s]["strokes"][stroke]["mean"],
         your_profiles[s]["strokes"][stroke]["std"])
        for s in combo
        if s in your_profiles and stroke in your_profiles[s].get("strokes", {})
    ]
    n_yours = len(your_ents)
    n_opp   = len(opp_entries)
    total   = n_yours + n_opp
    if total == 0:
        return np.zeros(n)
    all_means = np.array([m for m, _ in your_ents] + [m for m, _ in opp_entries])
    all_stds  = np.array([s for _, s in your_ents] + [s for _, s in opp_entries])
    use_log   = (age_group is not None) and _is_lognormal_event(age_group, stroke)
    times     = _sample_times(all_means, all_stds, n, use_lognormal=use_log)
    times, finish = _dq_adjust(times, _finish_rate(age_group, stroke))
    ranks     = np.argsort(np.argsort(times, axis=1), axis=1)
    pts_grid  = _pts_map(total)[ranks]
    if finish is not None:
        pts_grid = np.where(finish, pts_grid, 0.0)
    return pts_grid[:, :n_yours].sum(axis=1)


def simulate_our_total(your_lineup, opp_lineup, your_profiles, opp_profiles, events, n=10000):
    """Simulate our total individual-event score. Returns array of shape (n,)."""
    total = np.zeros(n)
    for event_label in events:
        age_group, _, stroke = parse_event(event_label)
        combo    = tuple(your_lineup.get(event_label, {}).get("swimmers", []))
        opp_sw   = opp_lineup.get(event_label, {}).get("swimmers", [])
        opp_ents = [
            (opp_profiles[s]["strokes"][stroke]["mean"],
             opp_profiles[s]["strokes"][stroke]["std"])
            for s in opp_sw
            if s in opp_profiles and stroke in opp_profiles[s].get("strokes", {})
        ]
        total += _sim_event_our_pts(combo, opp_ents, your_profiles, stroke, n, age_group=age_group)
    return total


def score_stats(our_totals, target=TARGET_SCORE):
    """Percentile of our distribution needed to reach target, plus our median."""
    sorted_t   = np.sort(our_totals)
    pct_needed = round(float(np.searchsorted(sorted_t, target) / len(sorted_t) * 100))
    return {"pct_needed": pct_needed, "our_median": round(float(np.median(our_totals)), 1), "target": target}


def _feasible_combo(new_combo, target_event, lineup, events):
    """True iff placing new_combo in target_event keeps all swimmer constraints satisfied."""
    swimmer_strokes = {}
    for event_label in events:
        _, _, stroke = parse_event(event_label)
        swimmers = new_combo if event_label == target_event else lineup[event_label]["swimmers"]
        for s in swimmers:
            swimmer_strokes.setdefault(s, []).append(stroke)
    for strokes in swimmer_strokes.values():
        if len(strokes) > MAX_EVENTS or len(set(strokes)) < len(strokes):
            return False
    return True



# ── Entries ────────────────────────────────────────────────────────────────────

def unconstrained_entries(profiles, events):
    """Top MAX_PER_EVENT swimmers per event as (mean, std) tuples."""
    entries = {}
    for event_label in events:
        age_group, gender, stroke = parse_event(event_label)
        entries[event_label] = sorted(
            (p["strokes"][stroke]["mean"], p["strokes"][stroke]["std"])
            for p in profiles.values()
            if is_eligible(p, age_group, gender, stroke)
        )[:MAX_PER_EVENT]
    return entries


def lineup_to_entries(profiles, lineup, events):
    """Convert lineup dict → {event_label: [(mean, std), ...]}."""
    entries = {}
    for event_label in events:
        _, _, stroke = parse_event(event_label)
        entries[event_label] = [
            (profiles[s]["strokes"][stroke]["mean"],
             profiles[s]["strokes"][stroke]["std"])
            for s in lineup.get(event_label, {}).get("swimmers", [])
            if s in profiles and stroke in profiles[s]["strokes"]
        ]
    return entries


# ── Self-optimal ───────────────────────────────────────────────────────────────

def self_optimal(profiles, events):
    prob = LpProblem("self_optimal", LpMaximize)

    diff_scores = {}
    for event_label in events:
        age_group, gender, stroke = parse_event(event_label)
        eligible = sorted(
            [(name, p["strokes"][stroke]["mean"])
             for name, p in profiles.items()
             if is_eligible(p, age_group, gender, stroke)],
            key=lambda x: x[1]
        )
        # Value each (swimmer, event) by expected placement points for their rank in
        # the event (NVSL 5-3-1 for top 3), NOT the time-gap to the next swimmer.
        # The old gap objective (next_t - t) rewarded "lead over the next guy"
        # regardless of whether the swimmer placed, so it could seed a swimmer into a
        # weak event where they had a big gap (but score 0) instead of an event where
        # they place top-3 — e.g. a #2-in-fly / #3-in-back swimmer buried in free
        # because his free gap happened to be largest. A tiny speed term breaks ties
        # deterministically (prefer faster swimmers for non-scoring fill slots).
        for i, (name, t) in enumerate(eligible):
            place_pts = (5.0, 3.0, 1.0)[i] if i < 3 else 0.0
            diff_scores[(name, event_label)] = place_pts + 0.0001 * (len(eligible) - i)

    x = {
        swimmer: {
            event_label: LpVariable(
                f"so_{swimmer}_{event_label}".replace(" ", "_").replace("-", "_").replace("&", ""),
                cat="Binary"
            )
            for event_label in events
            if (swimmer, event_label) in diff_scores
        }
        for swimmer in profiles
    }

    for swimmer in profiles:
        vars_ = list(x[swimmer].values())
        if vars_:
            prob += lpSum(vars_) <= MAX_EVENTS

    for event_label in events:
        vars_ = [x[s][event_label] for s in profiles if event_label in x.get(s, {})]
        if vars_:
            prob += lpSum(vars_) <= MAX_PER_EVENT

    strokes = {parse_event(e)[2] for e in events}
    for swimmer in profiles:
        for stroke in strokes:
            stroke_vars = [
                x[swimmer][e]
                for e in events
                if parse_event(e)[2] == stroke and e in x.get(swimmer, {})
            ]
            if stroke_vars:
                prob += lpSum(stroke_vars) <= 1

    prob += lpSum(
        x[name][event_label] * (score + FILL_BONUS)
        for (name, event_label), score in diff_scores.items()
        if event_label in x.get(name, {})
    )

    prob.solve(PULP_CBC_CMD(msg=0))

    lineup = {}
    for event_label in events:
        swimmers_in = [
            s for s in profiles
            if event_label in x.get(s, {})
            and value(x[s][event_label]) and value(x[s][event_label]) > 0.5
        ]
        lineup[event_label] = {"swimmers": swimmers_in, "expected_points": 0}

    return lineup


def save_lineup(lineup, filename):
    with open(filename, "w") as f:
        json.dump(lineup, f, indent=2)
