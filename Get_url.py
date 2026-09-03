from team_names import nvsl_teams

# Age group label -> (URL id, list of stroke event codes)
AGE_GROUPS = {
    "8U":   {"id": 1, "strokes": ["25-free", "25-back", "25-breast", "25-fly"]},
    "9-10": {"id": 2, "strokes": ["50-free", "50-back", "50-breast", "25-fly"]},
    "11-12":{"id": 3, "strokes": ["50-free", "50-back", "50-breast", "50-fly"]},
    "13-14":{"id": 4, "strokes": ["50-free", "50-back", "50-breast", "50-fly"]},
    "15-18":{"id": 5, "strokes": ["50-free", "50-back", "50-breast", "50-fly"]},
}

GENDERS = {"Boys": 1, "Girls": 2}


def get_team_id(name):
    if name in nvsl_teams:
        return nvsl_teams[name]
    for k, v in nvsl_teams.items():
        if k.lower() == name.lower():
            return v
    raise ValueError(f"Team '{name}' not found. Check team_names.py for valid names.")


def build_urls(team_names, year=2025, count=100):
    """Return a list of dicts with 'url' and metadata for every combination."""
    team_ids = {name: get_team_id(name) for name in team_names}
    configs = []

    for age_label, age_info in AGE_GROUPS.items():
        age_id = age_info["id"]
        for gender_label, gender_id in GENDERS.items():
            for stroke in age_info["strokes"]:
                for team_name, team_id in team_ids.items():
                    url = (
                        f"https://www.mynvsl.com/leaders"
                        f"?post=1&mt=0&age={age_id}&sex={gender_id}"
                        f"&st=1&stroke={stroke}&m=1&year={year}"
                        f"&count={count}&division=&team={team_id}"
                    )
                    configs.append({
                        "url": url,
                        "search_team": team_name,
                        "age_group": age_label,
                        "gender": gender_label,
                        "stroke": stroke,
                        "year": year,
                    })

    return configs


def prompt_for_teams():
    """Prompt for exactly two teams: yours and the opponent's."""
    teams = []
    for label in ("Your team", "Other team"):
        while True:
            name = input(f"{label}: ").strip()
            try:
                get_team_id(name)
                teams.append(name)
                break
            except ValueError as e:
                print(f"  {e}")
    return teams
