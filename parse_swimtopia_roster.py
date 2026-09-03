#!/usr/bin/env python3
"""
Parse a SwimTopia /manage/people page (HTML) into a clean roster JSON.

The page lists athletes as rows like:
  <tr class="user odd" id="user_XXXX">
    <td><a href="/manage/users/XXXX">Lastname, Firstname "Nick"</a> <span>(AGE)</span></td>
    <td><span class="label-athlete tag">Boys 11-12</span></td>
    <td><a href="/manage/organization_accounts/...">SHB-00XXX</a></td>
    ...

Output: roster/<team_slug>.json
  {
    "team": "Sleepy Hollow B & R",
    "source": "SwimTopia 2026",
    "scraped_at": "...",
    "swimmers": [
      {"name": "Nathaniel Arispe Rocha", "age": 11,
       "swimtopia_group": "Boys 11-12", "nvsl_age_group": "11-12 Boys",
       "gender": "Boys", "account": "SHB-00818",
       "swimtopia_user_id": 10272795},
      ...
    ]
  }

Usage:
    python3 parse_swimtopia_roster.py shbr_swimtopia.html "Sleepy Hollow B & R"
"""

import json
import os
import re
import sys
from datetime import datetime


def _strip_nickname(first):
    """Remove "Nickname" tokens. 'Alyssa "Allie"' -> 'Alyssa'."""
    return re.sub(r'\s*"[^"]+"\s*', '', first).strip()


def _swimtopia_to_nvsl_age_group(swt_group):
    """
    SwimTopia uses 'Boys 11-12', 'Boys 6 & Under', 'Men 15-18', etc.
    NVSL events use '8U Boys', '11-12 Boys', '15-18 Boys', etc.

    Returns (nvsl_age_group_string, gender) e.g. ('11-12 Boys', 'Boys').
    """
    m = re.match(r"(Boys|Girls|Men|Women)\s+(.+)", swt_group.strip())
    if not m:
        return None, None
    raw_gender, age_part = m.group(1), m.group(2)
    gender = "Boys" if raw_gender in ("Boys", "Men") else "Girls"
    age_part = age_part.strip()

    # NVSL convention: anything <=8 is "8U". 9-10, 11-12, 13-14, 15-18 keep their labels.
    if age_part in ("6 & Under", "7-8"):
        nvsl_age = "8U"
    elif age_part == "9-10":
        nvsl_age = "9-10"
    elif age_part == "11-12":
        nvsl_age = "11-12"
    elif age_part == "13-14":
        nvsl_age = "13-14"
    elif age_part == "15-18":
        nvsl_age = "15-18"
    else:
        nvsl_age = age_part
    return f"{nvsl_age} {gender}", gender


def parse(html):
    out = []
    # Each athlete row: id="user_XXXX" with name in first td, group label, account
    rows = re.finditer(
        r'<tr class="user (?:odd|even)" id="user_(\d+)">(.*?)</tr>',
        html, flags=re.DOTALL,
    )
    for row in rows:
        user_id = int(row.group(1))
        body    = row.group(2)

        # Name: <a href="/manage/users/XXX">Last, First "Nick"</a> then optional <span>(AGE)</span>
        name_m = re.search(r'<a href="/manage/users/\d+">([^<]+)</a>', body)
        if not name_m: continue
        raw_name = name_m.group(1).strip()
        # Convert "Last, First" → "First Last"
        if "," in raw_name:
            last, first = raw_name.split(",", 1)
            first = _strip_nickname(first.strip())
            full_name = f"{first} {last.strip()}"
        else:
            full_name = raw_name

        # Age in tooltip span — looks like "(AGE)"
        age_m = re.search(r'<span class="tip"[^>]*>\s*\((\d+)\)\s*</span>', body)
        age = int(age_m.group(1)) if age_m else None

        # Group label — find ALL label-athlete tags, pick the first that matches
        # the Boys/Girls/Men/Women age-group pattern. Some swimmers have
        # multiple tags (e.g., "2025 Seal Pups" + "Girls 7-8"); we want the latter.
        # Skip swimmers labeled "Non-competitive".
        if 'label-non_competitive' in body:
            continue   # Skip Seal Pups / non-competitive entries entirely
        all_tags = re.findall(r'<span class="label-athlete tag">\s*([^<]+?)\s*</span>', body)
        swt_group = None
        for tag in all_tags:
            cleaned = tag.replace("&amp;", "&").strip()
            if re.match(r"^(Boys|Girls|Men|Women)\s+", cleaned):
                swt_group = cleaned
                break
        nvsl_age_group, gender = _swimtopia_to_nvsl_age_group(swt_group) if swt_group else (None, None)
        if not swt_group:
            continue   # No valid age-group tag — skip (coaches, adults, etc.)

        # Account number (e.g. SHB-00818)
        acct_m = re.search(r'<a href="/manage/organization_accounts/\d+">\s*([A-Z0-9\-]+)\s*</a>', body)
        account = acct_m.group(1).strip() if acct_m else None

        out.append({
            "name":              full_name,
            "age":               age,
            "swimtopia_group":   swt_group,
            "nvsl_age_group":    nvsl_age_group,
            "gender":            gender,
            "account":           account,
            "swimtopia_user_id": user_id,
        })
    return out


def _safe_team_path(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    html_path = sys.argv[1]
    team_name = sys.argv[2]
    season    = sys.argv[3] if len(sys.argv) > 3 else "2026"

    with open(html_path) as f:
        html = f.read()
    swimmers = parse(html)
    print(f"Parsed {len(swimmers)} athletes from {html_path}")
    # Quick age-group summary
    from collections import Counter
    ag_counts = Counter(s["nvsl_age_group"] for s in swimmers)
    for ag, n in sorted(ag_counts.items()):
        print(f"  {ag:<18} {n}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roster")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{_safe_team_path(team_name)}.json")
    payload = {
        "team":       team_name,
        "source":     f"SwimTopia {season}",
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "n_swimmers": len(swimmers),
        "swimmers":   swimmers,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
