#!/usr/bin/env python3
"""
Coverage blend (W2-W5 cure validated 2026-05-29, wired 2026-05-30).

Fills missing 2025 swimmers/strokes with their REAL prior-year (2024) times.

Why: early-season profiles are thin (only ~58% opponent coverage at W2 → 85% by W5).
Unprofiled swimmers are invisible to the scorer → phantom-thin opponent fields →
my swimmers over-win. ALSO breaks relay formation when missing key swimmers.

The W2-W5 cure (exp_blend.py): take the in-season profile, then for each swimmer
in the team's 2024 profile who's missing from the current profile, ADD their full
2024 record. For swimmers in BOTH, merge any missing strokes from 2024.

Crucially: use RAW 2024 TIMES (no z-score, no penalty). Real prior-year times
are "self-calibrating" — they reflect the swimmer's actual ability, not a
synthetic phantom. Median percentile imputation drove bias to −51 (too competitive
across the board). Raw 2024 → bias +0.5 (just right).

Empirical result (exp_blend.py, W2-W5, n=384): MAE 20.5, bias +0.5 (relay+blend),
beating multiplier band-aid (MAE 22.03) AND relay-only (21.88).

Usage:
    from coverage_blend import apply_coverage_blend
    enriched_profile = apply_coverage_blend(profile, team_name, year)

This is meant to run AFTER the production's augment_profiles_with_imputation step
to OVERRIDE z-score imputations with raw 2024 times where the swimmer raced in 2024.
"""
import os, json
from collections import defaultdict

from Optimizer import (
    build_profiles_recency_weighted, normalize_name, parse_event,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "nvsl_meet_history.json")

_HIST_CACHE = None
_PROFILE_CACHE = {}   # (team_name, year) -> profile dict


def _load_history():
    global _HIST_CACHE
    if _HIST_CACHE is None:
        with open(HISTORY_PATH) as f:
            _HIST_CACHE = json.load(f)
    return _HIST_CACHE


def _team_dated_year(team_name, year):
    """Build {event: {swimmer_n: [(date, time), ...]}} from a year's race history."""
    history = _load_history()
    out = defaultdict(lambda: defaultdict(list))
    for wl, meets in (history.get(str(year)) or {}).items():
        if "Week" not in wl or not isinstance(meets, dict): continue
        for m in meets.values():
            for side in ("team_a", "team_b"):
                t = m.get(side) or {}
                if t.get("name") != team_name: continue
                for ev, d in (t.get("lineup") or {}).items():
                    for s in (d.get("swimmers") or []):
                        if not isinstance(s, dict): continue
                        tm = s.get("time_sec")
                        if tm and 5 < tm < 600:
                            out[ev][normalize_name(s["name"])].append(
                                (m.get("date", "?"), tm))
    if not out:
        return None
    return {k: dict(v) for k, v in out.items()}


def build_team_prior_year_profile(team_name, prior_year=2024, decay=0.7):
    """Build a team's full prior-year profile from race history.

    Returns same format as Optimizer.build_profiles_recency_weighted:
      {swimmer_norm: {home_age_group, gender, strokes: {dist-stroke: {mean, std}}}}

    Returns {} if no data for that team/year.
    """
    cache_key = (team_name, prior_year)
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key]
    data = _team_dated_year(team_name, prior_year)
    if not data:
        _PROFILE_CACHE[cache_key] = {}
        return {}
    profile = build_profiles_recency_weighted(data, decay=decay) or {}
    _PROFILE_CACHE[cache_key] = profile
    return profile


def apply_coverage_blend(profile, team_name, current_year, prior_year=None, exclude_norm=None):
    """Enrich profile with raw prior-year times for missing swimmers/strokes.

    Mutates and returns a shallow copy of profile:
      - For each swimmer in prior_year profile NOT in profile: ADD them entirely
        (with prior-year home_age_group, gender, all strokes).
      - For swimmers in BOTH: ADD missing strokes only (preserve current means).
      - Does NOT remove swimmers, modify times of swimmers already in profile,
        or apply any z-score / league-shift adjustment.

    exclude_norm: set of normalized swimmer names to NEVER re-add (e.g. swimmers the
      coach marked ABSENT this week, or "not on team" user excludes). Critical: the
      caller drops absent swimmers from `profile` BEFORE calling this, so without this
      guard coverage_blend would see them "missing" and resurrect them from prior-year
      data — silently undoing the absence marking. Mirrors the imputation exclude set.

    Note: prior_year defaults to current_year - 1.

    Returns the enriched profile dict (new top-level dict; swimmer entries are
    new dicts where modified).
    """
    if prior_year is None:
        prior_year = current_year - 1
    prior_profile = build_team_prior_year_profile(team_name, prior_year)
    if not prior_profile:
        return dict(profile)

    enhanced = dict(profile)
    from Optimizer import normalize_name as _nn
    _exclude = {_nn(x) for x in (exclude_norm or ())}
    # Roster-aware guard: if the team has an authoritative SwimTopia roster, do NOT
    # re-add prior-year swimmers who aren't on it. Without this, coverage_blend
    # resurrects swimmers who AGED OUT or quit (e.g. a 15-18 who graduated) at their
    # stale prior-year times — and since the roster restriction in
    # augment_profiles_with_imputation already (correctly) dropped them, this silently
    # re-introduces phantoms the optimizer then fields (over-prediction; no UI checkbox
    # to remove them because the availability panel is built pre-blend). Teams WITHOUT a
    # roster keep the original behavior (add all missing prior-year swimmers).
    try:
        import roster as _roster
        _roster_set = _roster.roster_swimmer_set(team_name, current_year)
    except Exception:
        _roster_set = None
    n_skipped_offroster = n_skipped_excluded = 0
    for name, prior_data in prior_profile.items():
        if name not in enhanced:
            nn = _nn(name)
            if nn in _exclude:
                n_skipped_excluded += 1   # marked absent this week / user-excluded
                continue
            if _roster_set is not None and nn not in _roster_set:
                n_skipped_offroster += 1   # aged out / quit — not on current roster
                continue
            # Net-new swimmer (didn't race in current-year profile yet)
            enhanced[name] = prior_data
        else:
            # Already present — only add missing strokes (preserve current means)
            current_strokes = dict(enhanced[name].get("strokes", {}))
            n_added = 0
            for stroke_label, stroke_data in (prior_data.get("strokes", {}) or {}).items():
                if stroke_label not in current_strokes:
                    current_strokes[stroke_label] = stroke_data
                    n_added += 1
            if n_added > 0:
                # Only create new dict if we actually added something
                merged = dict(enhanced[name])
                merged["strokes"] = current_strokes
                enhanced[name] = merged
    if n_skipped_offroster:
        print(f"[coverage_blend] {team_name}: skipped {n_skipped_offroster} off-roster "
              f"prior-year swimmer(s) (aged out / quit — not on current roster)", flush=True)
    if n_skipped_excluded:
        print(f"[coverage_blend] {team_name}: skipped {n_skipped_excluded} excluded/absent "
              f"prior-year swimmer(s) (marked unavailable this week)", flush=True)
    return enhanced


def coverage_stats(profile, team_name, current_year, prior_year=None):
    """Diagnostic: how many swimmers/strokes coverage_blend would add.

    Returns dict with counts (no mutation).
    """
    if prior_year is None:
        prior_year = current_year - 1
    prior_profile = build_team_prior_year_profile(team_name, prior_year)
    if not prior_profile:
        return {"prior_year_swimmers": 0, "would_add_swimmers": 0,
                "would_add_strokes": 0}
    n_add_sw = sum(1 for name in prior_profile if name not in profile)
    n_add_st = 0
    for name, prior_data in prior_profile.items():
        if name not in profile: continue
        cur_strokes = set((profile[name].get("strokes") or {}).keys())
        prior_strokes = set((prior_data.get("strokes") or {}).keys())
        n_add_st += len(prior_strokes - cur_strokes)
    return {
        "prior_year_swimmers": len(prior_profile),
        "current_year_swimmers": len(profile),
        "would_add_swimmers": n_add_sw,
        "would_add_strokes": n_add_st,
    }
