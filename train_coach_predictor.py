#!/usr/bin/env python3
"""
Train the coach lineup predictor and save it to coach_predictor_model.pkl.

Run this once at install, and periodically after each season ends to
incorporate the new year of training data.

Usage:
    python3 train_coach_predictor.py

Output:
    coach_predictor_model.pkl  (used at runtime by coach_predictor.predict_opp_lineup)
"""
import json, os, time, pickle, math
import numpy as np
from collections import defaultdict

from sklearn.ensemble import HistGradientBoostingClassifier

from Optimizer import (parse_event, normalize_name, is_eligible,
                       build_profiles_recency_weighted)
import coach_predictor as cp

# Training-only helpers (mirror the inference-time pipeline in coach_predictor.py).
# Train years are everything except the most recent (held out for sanity).
TRAIN_YEARS = [2021, 2022, 2023, 2024]


def build_team_dated_through_week(history, team, year, max_week):
    out = defaultdict(lambda: defaultdict(list))
    weeks = history.get(str(year), {})
    for wl in weeks:
        if "Week" not in wl: continue
        wk = int(wl.replace("Week ", ""))
        if wk >= max_week: continue
        for m in weeks[wl].values():
            for side in ("team_a", "team_b"):
                if m[side].get("name") != team: continue
                for ev, d in m[side].get("lineup", {}).items():
                    for s in d.get("swimmers", []):
                        t = s.get("time_sec")
                        if t and 5 < t < 600:
                            out[ev][normalize_name(s["name"])].append((m.get("date", "?"), t))
    return {k: dict(v) for k, v in out.items()} if out else None


def build_training_data(history):
    X, y = [], []
    print(f"[train] scanning training years {TRAIN_YEARS}...")
    for year in TRAIN_YEARS:
        y_str = str(year)
        if y_str not in history: continue
        for wl in sorted(history[y_str].keys()):
            if "Week" not in wl: continue
            wk = int(wl.replace("Week ", ""))
            if wk < 2: continue
            current_global_wk = wk
            baselines = cp.league_baselines(year, wk, history)
            for m in history[y_str][wl].values():
                for side in ("team_a", "team_b"):
                    team = m[side].get("name")
                    if not team: continue
                    actual = {(normalize_name(s["name"]), ev)
                              for ev, d in m[side].get("lineup", {}).items()
                              for s in d.get("swimmers", [])}
                    if not actual: continue
                    dated = build_team_dated_through_week(history, team, year, wk)
                    if not dated: continue
                    profiles = build_profiles_recency_weighted(dated, decay=0.7)
                    if not profiles: continue
                    team_se, team_s = cp.build_team_state(team, year, wk, history)
                    tcz = cp.team_consistency_z(team, year)
                    all_evs = {ev for _sw, ev in team_se.keys()}
                    event_crowding = cp.compute_event_eligibility_stats(profiles, all_evs)
                    min_z_by_sw = {}
                    for sw_raw, p in profiles.items():
                        sw_norm = normalize_name(sw_raw)
                        zs = []
                        ag = p.get("home_age_group"); g = p.get("gender")
                        if ag and g:
                            for st in p.get("strokes", {}):
                                z = cp.profile_z_in_event(p, f"{ag} {g} {st}", baselines)
                                if z is not None: zs.append(z)
                        min_z_by_sw[sw_norm] = min(zs) if zs else None
                    for (sw_norm, ev), st in team_se.items():
                        if st["n_races"] == 0: continue
                        sw_raw = None
                        for sr in profiles:
                            if normalize_name(sr) == sw_norm:
                                sw_raw = sr; break
                        if not sw_raw: continue
                        p = profiles[sw_raw]
                        z = cp.profile_z_in_event(p, ev, baselines)
                        feat = cp.feature_row(team_se, team_s, sw_norm, ev,
                                               current_global_wk, z,
                                               min_z_by_sw.get(sw_norm),
                                               tcz, event_crowding)
                        X.append(feat)
                        y.append(1 if (sw_norm, ev) in actual else 0)
        print(f"[train]   year {year} done (rows so far: {len(X)})")
    return np.array(X), np.array(y, dtype=np.float32)


def main():
    print("="*70)
    print("Training coach_predictor")
    print("="*70)
    t0 = time.time()
    print(f"\n[stage 1] Loading history...")
    history = cp._load_history()

    print(f"[stage 2] Building training data...")
    X, y = build_training_data(history)
    print(f"[train]   {X.shape[0]} rows × {X.shape[1]} features, base rate {y.mean():.3f}")

    print(f"\n[stage 3] Fitting HistGradientBoostingClassifier...")
    t1 = time.time()
    model = HistGradientBoostingClassifier(
        max_iter=500, learning_rate=0.05, max_depth=6,
        min_samples_leaf=50, l2_regularization=1.0, random_state=42,
    )
    model.fit(X, y)
    print(f"[train]   fit in {time.time()-t1:.1f}s")

    print(f"\n[stage 4] Saving model → {cp.MODEL_PATH}")
    payload = {
        "model": model,
        "feature_names": cp.FEATURE_NAMES,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "train_years": TRAIN_YEARS,
        "n_train_rows": int(X.shape[0]),
        "base_rate": float(y.mean()),
    }
    with open(cp.MODEL_PATH, "wb") as f:
        pickle.dump(payload, f)
    size_kb = os.path.getsize(cp.MODEL_PATH) / 1024
    print(f"[done]   saved ({size_kb:.0f} KB)  total time {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
