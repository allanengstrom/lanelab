"""
Scrapes actual meet results from mynvsl.com/results/<meet_id>.
Returns the opponent's lineup in the same format as opp_lineup.json.
"""

import re
import urllib.request

# Maps NVSL event title → our event label format
# NVSL: "Boys Free 25M 8&U"  →  "8U Boys 25-free"

_STROKE_MAP = {"Free": "free", "Back": "back", "Breast": "breast", "Fly": "fly"}
_AGE_MAP    = {"8&U": "8U", "9-10": "9-10", "11-12": "11-12", "13-14": "13-14", "15-18": "15-18"}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def nvsl_event_to_label(title):
    """Convert 'Boys Free 25M 8&U' → '8U Boys 25-free'. Returns None for relays/unknowns."""
    if "Relay" in title or "IM" in title or "Medley" in title:
        return None
    # e.g. "Boys Free 25M 8&U" or "Girls Breast 50M 13-14"
    m = re.match(r"(Boys|Girls)\s+(\w+)\s+(\d+)M\s+([\w&-]+)", title)
    if not m:
        return None
    gender, stroke_name, dist, age_raw = m.groups()
    stroke = _STROKE_MAP.get(stroke_name)
    age    = _AGE_MAP.get(age_raw)
    if not stroke or not age:
        return None
    return f"{age} {gender} {dist}-{stroke}"


def find_meet_id(team1, team2, date_str, year=2025):
    """
    Search the schedules page for a meet between team1 and team2 on date_str (YYYYMMDD).
    Returns the integer meet ID, or None if not found.
    """
    url  = f"https://www.mynvsl.com/schedules?year={year}&date={date_str}"
    html = fetch(url)

    # Each meet row: two team links followed immediately by a results link
    # Pattern: capture team names and the result id from the same "row" of HTML
    pattern = re.compile(
        r'<td><a href="/team/[^"]*"[^>]*>(.*?)</a>.*?'
        r'<td><a href="/team/[^"]*"[^>]*>(.*?)</a>.*?'
        r'/results/(\d+)',
        re.DOTALL
    )
    t1_lower = team1.lower().strip()
    t2_lower = team2.lower().strip()

    for m in pattern.finditer(html):
        name_a = re.sub(r"<[^>]+>", "", m.group(1)).strip().lower()
        name_b = re.sub(r"<[^>]+>", "", m.group(2)).strip().lower()
        meet_id = int(m.group(3))
        if {name_a, name_b} == {t1_lower, t2_lower}:
            return meet_id

    return None


def parse_meet_results(meet_id, opp_team_name, your_team_name=None):
    """
    Fetch meet results and return:
      opp_lineup  — {event_label: {"swimmers": [...], "expected_points": 0}}
      opp_code    — the team abbreviation used in the results (e.g. "CP")
    """
    url  = f"https://www.mynvsl.com/results/{meet_id}"
    html = fetch(url)

    # Pull team names from scores table to verify we have the right meet
    score_teams = re.findall(r"<th>[\d.]+</th><td>(.*?)</td>", html)

    # Parse all events
    event_blocks = re.split(r'<th colspan="4">', html)

    all_entries = {}  # {event_label: [(code, name), ...]}
    for block in event_blocks[1:]:
        title_match = re.match(r"(.*?)</th>", block)
        if not title_match:
            continue
        raw_title = title_match.group(1).strip()
        label = nvsl_event_to_label(raw_title)
        if not label:
            continue

        rows = re.findall(
            r"<td>\d+\.</td>\s*<td>[\d:.]+</td>\s*<td>([A-Z]{1,4})</td>\s*<td>\s*(.*?)\s*</td>",
            block
        )
        all_entries[label] = [(code, name.strip()) for code, name in rows if name.strip()]

    # Determine the opponent's team code by matching names to the known opp team
    # We look at which code appears alongside opp_team_name in score_teams
    opp_code = _infer_code(score_teams, opp_team_name, all_entries)

    opp_lineup = {}
    for label, entries in all_entries.items():
        swimmers = [name for code, name in entries if code == opp_code]
        opp_lineup[label] = {"swimmers": swimmers, "expected_points": 0}

    return opp_lineup, opp_code


def _infer_code(score_teams, opp_team_name, all_entries):
    """
    Find the team code for opp_team_name.
    Strategy: collect all codes present, then match by initials of the opp team name.
    Falls back to whichever code is NOT matched by your_team_name.
    """
    all_codes = {code for entries in all_entries.values() for code, _ in entries}
    if not all_codes:
        return None

    # Try to match opp_team_name initials to a code
    opp_words = [w for w in re.split(r"[\s\-&]+", opp_team_name) if w]
    opp_initials = "".join(w[0].upper() for w in opp_words)

    for code in sorted(all_codes):
        if opp_initials.startswith(code) or code == opp_initials[:len(code)]:
            return code

    # Fallback: try partial match against score_teams list
    opp_lower = opp_team_name.lower().strip()
    for i, team in enumerate(score_teams):
        if opp_lower in team.lower():
            # The other team takes the other code
            other_idx = 1 - i
            other_name = score_teams[other_idx] if other_idx < len(score_teams) else ""
            other_words = [w for w in re.split(r"[\s\-&]+", other_name) if w]
            other_init = "".join(w[0].upper() for w in other_words)
            for code in sorted(all_codes):
                if code != other_init[:len(code)]:
                    return code

    # Last resort: return the lexicographically first code
    return sorted(all_codes)[0]


def find_team_meets(team_name, weeks, year=2025):
    """
    Search each week's schedule page for a meet involving team_name.
    weeks: list of {"week": int, "date": str, "label": str} dicts.
    Returns list of {"week", "date", "label", "meet_id", "opponent"} dicts
    (one per week where the team played; weeks with no match are omitted).
    Uses substring matching so shortened schedule names still resolve.
    """
    meets   = []
    t_lower = team_name.lower().strip()

    pattern = re.compile(
        r'<td><a href="/team/[^"]*"[^>]*>(.*?)</a>.*?'
        r'<td><a href="/team/[^"]*"[^>]*>(.*?)</a>.*?'
        r'/results/(\d+)',
        re.DOTALL,
    )

    for w in weeks:
        url  = f"https://www.mynvsl.com/schedules?year={year}&date={w['date']}"
        html = fetch(url)

        for m in pattern.finditer(html):
            raw_a   = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            raw_b   = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            name_a  = raw_a.lower()
            name_b  = raw_b.lower()
            meet_id = int(m.group(3))

            if t_lower in name_a or name_a in t_lower:
                meets.append({"week": w["week"], "date": w["date"],
                               "label": w["label"], "meet_id": meet_id,
                               "opponent": raw_b})
                break
            elif t_lower in name_b or name_b in t_lower:
                meets.append({"week": w["week"], "date": w["date"],
                               "label": w["label"], "meet_id": meet_id,
                               "opponent": raw_a})
                break

    return meets
