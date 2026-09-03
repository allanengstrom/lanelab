import re
import json
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from Get_url import build_urls, prompt_for_teams


def to_seconds(time_str):
    """Convert 'm:ss.xx' or 'ss.xx' to a float number of seconds."""
    if ":" in time_str:
        minutes, seconds = time_str.split(":")
        return int(minutes) * 60 + float(seconds)
    return float(time_str)


def parse_table(html_content):
    """Parse a single leaders page. Returns list of (name, time) tuples."""
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", {"class": "sys-cnt"})
    if not table:
        return []

    entries = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        time_val = cells[1].get_text(strip=True)

        swimmer_link = cells[2].find("a")
        name = swimmer_link.get_text(strip=True) if swimmer_link else cells[2].get_text(strip=True)

        entries.append((name, to_seconds(time_val)))

    return entries


def scrape_teams(team_names, year=2025):
    """
    Returns a nested dict:
        {
            team_name: {
                "age_group gender stroke": {
                    swimmer_name: [time1, time2, ...]
                }
            }
        }
    Times are sorted fastest first.
    """
    configs = build_urls(team_names, year=year, count=100)

    results = {team: defaultdict(lambda: defaultdict(list)) for team in team_names}

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible)"})

    total = len(configs)
    for i, config in enumerate(configs, 1):
        team = config["search_team"]
        event_label = f"{config['age_group']} {config['gender']} {config['stroke']}"

        print(f"[{i}/{total}] {team} | {event_label}", end="", flush=True)

        try:
            resp = session.get(config["url"], timeout=15)
            resp.raise_for_status()
            entries = parse_table(resp.content)
            for name, time_val in entries:
                results[team][event_label][name].append(time_val)
            print(f"  → {len(entries)} entries")
        except requests.RequestException as e:
            print(f"  → ERROR: {e}")

    output = {}
    for team, events in results.items():
        output[team] = {}
        for event_label, swimmers in events.items():
            output[team][event_label] = {
                name: sorted(times)
                for name, times in swimmers.items()
                if times
            }

    return output


def save_json(results, filename="results.json"):
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {filename}")


if __name__ == "__main__":
    teams = prompt_for_teams()
    year_input = input("Year [2025]: ").strip()
    year = int(year_input) if year_input else 2025

    results = scrape_teams(teams, year=year)
    save_json(results)
