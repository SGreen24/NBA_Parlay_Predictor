#!/usr/bin/env python3

import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import LeagueDashPlayerStats

def fetch_full_roster(abbrev: str) -> pd.DataFrame:
    """
    Fetch the full ESPN roster for an NBA team (by abbrev, e.g. "GS").
    Returns a DataFrame with columns: PLAYER, POSITION.
    """
    abbrev = abbrev.upper()
    # Resolve ESPN team ID
    teams_resp = requests.get(
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams",
        timeout=10
    )
    teams_resp.raise_for_status()
    data = teams_resp.json()
    teams = (data.get("sports", [{}])[0]
                 .get("leagues", [{}])[0]
                 .get("teams", [])
             if isinstance(data, dict) else data)

    team_id = None
    for t in teams:
        info = t.get("team", {}) if isinstance(t, dict) else {}
        if info.get("abbreviation", "").upper() == abbrev:
            team_id = info.get("id")
            break
    if not team_id:
        raise ValueError(f"No ESPN team found for '{abbrev}'")

    # Fetch roster JSON
    resp = requests.get(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster",
        timeout=10
    )
    resp.raise_for_status()
    roster_json = resp.json()

    # Extract entries
    entries = []
    if isinstance(roster_json, dict):
        for path in (["roster","entries"], ["entries"], ["athletes"], ["players"], ["roster"]):
            cur = roster_json
            try:
                for k in path:
                    cur = cur[k]
                if isinstance(cur, list):
                    entries = cur
                    break
            except (KeyError, TypeError):
                continue
    else:
        entries = roster_json

    # Build DataFrame
    rows = []
    for e in entries:
        ath = (e.get("athlete") if isinstance(e, dict) else None) or e
        if not isinstance(ath, dict):
            continue
        name = ath.get("fullName") or ath.get("displayName") or "Unknown"
        pos  = ath.get("position", {}).get("abbreviation", "")
        rows.append({"PLAYER": name, "POSITION": pos})
    if not rows:
        raise ValueError("No roster entries found")
    return pd.DataFrame(rows)


def fetch_espn_injuries(abbrev: str) -> pd.DataFrame:
    """
    Fetch ESPN injuries for a given team abbrev (e.g. "GS").
    Returns DataFrame with columns: PLAYER.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    resp = requests.get(url, params={"team": abbrev.upper()}, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, list):
        entries = data
    else:
        inj = data.get("injuries", [])
        if isinstance(inj, dict):
            entries = inj.get("entries", [])
        elif isinstance(inj, list):
            entries = inj
        else:
            entries = []

    names = []
    for e in entries:
        ath = e.get("athlete") or {}
        name = ath.get("fullName") or ath.get("displayName")
        if name:
            names.append(name)
    return pd.DataFrame({"PLAYER": names})


def fetch_team_per_game_stats(abbrev: str, season: str = "2024-25") -> pd.DataFrame:
    """
    Pull per-game stats for PPG, APG, RPG, SPG, BPG, FG%, FT%, 3P% from NBA.com.
    """
    full = LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame"
    ).get_data_frames()[0]

    team_df = full[full["TEAM_ABBREVIATION"] == abbrev.upper()]
    stats = team_df[[
        "PLAYER_NAME", "PTS", "AST", "REB", "STL", "BLK",
        "FG_PCT", "FT_PCT", "FG3_PCT"
    ]].rename(columns={
        "PLAYER_NAME": "PLAYER",
        "PTS": "PPG",
        "AST": "APG",
        "REB": "RPG",
        "STL": "SPG",
        "BLK": "BPG",
        "FG_PCT": "FG_PCT",
        "FT_PCT": "FT_PCT",
        "FG3_PCT": "FG3_PCT"
    }).fillna(0)

    # Convert to human-readable
    for col in ["PPG","APG","RPG","SPG","BPG"]:
        stats[col] = stats[col].round(1)
    for pct in ["FG_PCT","FT_PCT","FG3_PCT"]:
        stats[pct] = (stats[pct] * 100).round(1)

    return stats


def main():
    espn_abbrev = "CLE"
    nba_abbrev  = "CLE"

    # 1) Roster + position
    roster_df = fetch_full_roster(espn_abbrev)

    # 2) Injuries → mark inactive
    inj_df = fetch_espn_injuries(espn_abbrev)
    injured = set(inj_df["PLAYER"])
    roster_df["ACTIVE"] = roster_df["PLAYER"].apply(
        lambda n: "Inactive" if n in injured else "Active"
    )

    # 3) Per-game stats
    stats_df = fetch_team_per_game_stats(nba_abbrev)

    # 4) Merge everything
    df = roster_df.merge(stats_df, on="PLAYER", how="left").fillna(0)

    # 5) Print
    today = datetime.now().strftime("%B %d, %Y")
    header = (
        f"{'PLAYER':25} | {'POS':3} | {'PPG':>4} | {'APG':>4} | {'RPG':>4} | "
        f"{'SPG':>4} | {'BPG':>4} | {'FG%':>5} | {'FT%':>5} | {'3P%':>5} | {'ACTIVE'}"
    )
    print(f"\nGolden State Warriors Full Per-Game Stats (as of {today})\n")
    print(header)
    print("-" * len(header))
    for _, r in df.iterrows():
        print(
            f"{r['PLAYER']:25} | {r['POSITION']:3} | "
            f"{r['PPG']:4.1f} | {r['APG']:4.1f} | {r['RPG']:4.1f} | "
            f"{r['SPG']:4.1f} | {r['BPG']:4.1f} | "
            f"{r['FG_PCT']:5.1f}% | {r['FT_PCT']:5.1f}% | {r['FG3_PCT']:5.1f}% | "
            f"{r['ACTIVE']}"
        )


if __name__ == "__main__":
    main()
