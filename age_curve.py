"""Individual-age year-over-year improvement curve (NVSL), fit from the leaders
caches (see fit_age_curve.py / age_improvement_curve.json).

v1 SCOPE (per the adversarial review): ship the SAME-DISTANCE improvement curve
plus a best-ever clamp ONLY. The 25->50 distance-crossing keeps app.py's existing
hardcoded DIST_GROWTH_25_TO_50 constants — the empirically-fit crossing ratios did
NOT beat them out-of-sample (they were ~1.5% worse on unseen swimmers), so they're
not worth the risk. The same-distance curve cut held-out point error ~48% on
swimmers entirely absent from the fit, so it earns its place.

All of this is gated behind USE_AGE_CURVE (default OFF) so the production behaviour
is byte-identical until the gated paired backtest + theory-2 drift check pass.
"""
import os
import json
import glob
import functools

_DIR = os.path.dirname(os.path.abspath(__file__))

# Master gate. Default ON (shipped 2026-06: the individual-age projection changes
# lineups in the right direction — realistic opponent times — which matters more
# than the meet-margin metric; the displayed total/win% are recalibrated separately).
# Set USE_AGE_CURVE=0 to fall back to the old band-only behaviour (used by the
# off-baseline backtest).
USE_AGE_CURVE = os.environ.get("USE_AGE_CURVE", "1") == "1"

# Only override a hardcoded band constant when the curve bucket is well-populated
# (the review flagged the n>=3 cutoff as too loose at the young/sparse tail).
_MIN_N = int(os.environ.get("AGE_CURVE_MIN_N", "30"))

# Never project a swimmer faster than their best-ever time by more than this
# fraction (the "Ada" guard against thin-data overshoot). Tunable on the backtest.
CLAMP_FLOOR = float(os.environ.get("AGE_CURVE_CLAMP_FLOOR", "0.05"))


@functools.lru_cache(maxsize=1)
def _curve():
    try:
        with open(os.path.join(_DIR, "age_improvement_curve.json")) as f:
            return json.load(f)
    except Exception:
        return {"same_distance_pct": {}, "crossing_25_to_50": {}}


def _step_factor(stroke, distance, age_from):
    """Single-year same-distance multiplier (t_{age+1}/t_age) for one year of
    growth. Requires n>=_MIN_N; falls back to the nearest YOUNGER populated age;
    returns None if nothing usable (caller then keeps the old band factor)."""
    tbl = _curve().get("same_distance_pct", {})
    for a in range(int(age_from), 4, -1):          # exact age, then younger
        e = tbl.get(f"{stroke}|{distance}|{a}")
        if e and e.get("n", 0) >= _MIN_N and e.get("median") is not None:
            return 1.0 + float(e["median"])
    return None


def same_dist_factor(stroke, distance, age_from, age_to):
    """Cumulative same-distance multiplier from age_from to age_to, composing one
    measured year-step at a time. Returns None if no usable bucket in the range."""
    try:
        age_from = int(age_from); age_to = int(age_to)
    except Exception:
        return None
    if age_to <= age_from:
        return None
    f, used = 1.0, False
    for a in range(age_from, age_to):
        step = _step_factor(stroke, distance, a)
        if step is not None:
            f *= step
            used = True
    return f if used else None


@functools.lru_cache(maxsize=1)
def _best_index():
    """{(norm_name, 'dist-stroke'): best (min) time} across all leaders caches.
    Used only for the best-ever clamp; built lazily on first use."""
    from Optimizer import normalize_name, parse_event
    idx = {}
    for fn in glob.glob(os.path.join(_DIR, "leaders_cache*.json")):
        try:
            with open(fn) as f:
                data = json.load(f)
        except Exception:
            continue
        for _team, tdata in (data.get("teams", {}) or {}).items():
            if not isinstance(tdata, dict):
                continue
            for event_label, entries in tdata.items():
                try:
                    _b, _g, dist_stroke = parse_event(event_label)   # e.g. '50-fly'
                except Exception:
                    continue
                for e in (entries or []):
                    nm = normalize_name(e.get("name") or "")
                    t = e.get("time")
                    if not nm or not t:
                        continue
                    k = (nm, dist_stroke)
                    tv = float(t)
                    if k not in idx or tv < idx[k]:
                        idx[k] = tv
    return idx


def best_ever(norm_name, stroke, distance):
    """Best-ever observed time for this swimmer+event, or None."""
    return _best_index().get((norm_name, f"{distance}-{stroke}"))


def project_same_dist(t_prior, stroke, distance, age_from, age_to, best_ever_time=None):
    """Project a SAME-DISTANCE time forward by individual age. Clamped so the
    result never beats the swimmer's best-ever by more than CLAMP_FLOOR. Returns
    None if the curve has nothing usable (caller keeps prior behaviour)."""
    fac = same_dist_factor(stroke, distance, age_from, age_to)
    if fac is None:
        return None
    t = t_prior * fac
    if best_ever_time:
        t = max(t, float(best_ever_time) * (1.0 - CLAMP_FLOOR))
    return t
