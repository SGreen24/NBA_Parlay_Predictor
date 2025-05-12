#!/usr/bin/env python3

"""
NBA Hypothetical Line Predictor
================================

This script allows you to:
  1. Pick a team & player.
  2. Pick an opponent & defender at the same position.
  3. Gather:
        • Roster & per-game stats from ESPN (via team_fetcher.py).
        • Advanced metrics (Off_Rating, Def_Rating, USG%, Pace) via NBAStatsFetcher.
        • Recent games & head-to-head history via recent_games.py & NBAStatsFetcher.
        • Injuries and compute injured players’ usage impact.
  4. Input a line (e.g. 23.5) and Over/Under.
  5. Compute a probability using:
        – Baseline per-game average.
        – Recent‐games normal distribution.
        – Head‐to‐head adjustments.
        – Offensive Rating & Pace factors.
        – Injured‐usage factor.
        – Defender defensive rating adjustment.
  6. Print a detailed breakdown of all factors.
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime

from advanced_metrics import NBAStatsFetcher
from recent_games import get_espn_player_id
from team_fetcher import (
    fetch_full_roster,
    fetch_team_per_game_stats,
    fetch_espn_injuries,
)

# -----------------------------------------------------------------------
#  CONSTANTS
# -----------------------------------------------------------------------

LEAGUE_AVG_DEF_RATING = 110.0    # League-average defensive rating
LEAGUE_AVG_OFF_RATING = 110.0    # League-average offensive rating
LEAGUE_AVG_PACE       = 100.0    # League-average pace
H2H_LOOKBACK_GAMES    = 5        # How many head-to-head games to consider
RECENT_LOOKBACK       = 5        # How many recent games to consider
INJ_USAGE_WEIGHT      = 0.01     # Weight per 1% USG lost

# -----------------------------------------------------------------------
#  UTILITIES
# -----------------------------------------------------------------------

def log(msg: str):
    """Print a timestamped message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def normal_cdf(x: float) -> float:
    """Compute the standard normal CDF for x."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def calc_prob(mean: float, std: float, line: float, ou: str) -> float:
    """
    Given a normal distribution (mean, std):
      - if Over, returns P(X > line)
      - if Under, returns P(X < line)
    """
    if std <= 0:
        return 1.0 if (ou == "O" and mean > line) or (ou == "U" and mean < line) else 0.0
    z = (line - mean) / std
    return (1 - normal_cdf(z)) if ou == "O" else normal_cdf(z)

# -----------------------------------------------------------------------
#  SECTION 1: TEAM & PLAYER SELECTION
# -----------------------------------------------------------------------

def select_team(prompt: str):
    """
    Prompt for a team abbrev, then fetch roster, per-game stats, and injuries.
    Returns: (abbrev, roster_df, pergame_df, inj_df)
    """
    while True:
        abbrev = input(f"{prompt} (NBA abbrev, e.g. 'GS'): ").strip().upper()
        try:
            roster  = fetch_full_roster(abbrev)
            pergame = fetch_team_per_game_stats(abbrev)
            injuries = fetch_espn_injuries(abbrev)
            log(f"Loaded data for {abbrev}")
            return abbrev, roster, pergame, injuries
        except Exception as e:
            log(f"Error loading '{abbrev}': {e}")
            print("Please try again.\n")

def display_roster_names(roster_df: pd.DataFrame, inj_df: pd.DataFrame):
    """
    Print each PLAYER name, appending ' (Inactive)' if listed in inj_df.
    """
    print("\nRoster:")
    injured = set(inj_df["PLAYER"])
    for name in roster_df["PLAYER"]:
        suffix = " (Inactive)" if name in injured else ""
        print(f"  - {name}{suffix}")
    print("")

def choose_player(roster_df: pd.DataFrame) -> str:
    """Prompt until the user chooses a valid player name from roster_df."""
    names = roster_df["PLAYER"].tolist()
    while True:
        name = input("Choose your player (full name): ").strip()
        if name in names:
            log(f"Player chosen: {name}")
            return name
        log(f"Invalid player name: {name}")
        print("Name not in roster; try again.\n")

# -----------------------------------------------------------------------
#  SECTION 2: OPPONENT DEFENDER SELECTION
# -----------------------------------------------------------------------

def find_opponent_starter(op_abbrev: str, position: str) -> str:
    """
    Fetch the opponent roster and return the first player whose POSITION matches.
    """
    opp_roster = fetch_full_roster(op_abbrev)
    matches = [row["PLAYER"] for _, row in opp_roster.iterrows()
               if row["POSITION"] == position]
    if not matches:
        raise ValueError(f"No player at position '{position}' on {op_abbrev}")
    defender = matches[0]
    log(f"Defender chosen: {defender} ({position})")
    return defender

# -----------------------------------------------------------------------
#  SECTION 3: ADVANCED METRIC FETCHING
# -----------------------------------------------------------------------

def get_player_advanced(fetcher: NBAStatsFetcher, player_name: str):
    """
    Fetch:
      - Base stats (traditional)
      - Advanced stats (Off/Def Rating, USG%, Pace)
      - Hustle stats (unused here)
    Returns: (base_dict, adv_dict, hustle_dict)
    """
    pid = fetcher.search_player_nba(player_name)
    if pid is None:
        raise ValueError(f"Could not find NBA.com ID for {player_name}")
    base   = fetcher.get_nba_stats(pid, "Base") or {}
    adv    = fetcher.get_nba_stats(pid, "Advanced") or {}
    hustle = fetcher.get_nba_hustle_stats(pid) or {}
    off_rt = adv.get("OFF_RATING", LEAGUE_AVG_OFF_RATING)
    def_rt = adv.get("DEF_RATING", LEAGUE_AVG_DEF_RATING)
    pace   = adv.get("PACE", LEAGUE_AVG_PACE)
    usage  = adv.get("USG_PCT", 0.0)
    log(f"{player_name}: OffRT={off_rt}, DefRT={def_rt}, Pace={pace}, USG%={usage}")
    return base, adv, hustle

# -----------------------------------------------------------------------
#  SECTION 4: HEAD-TO-HEAD & RECENT FORM
# -----------------------------------------------------------------------

def compute_head_to_head(fetcher: NBAStatsFetcher, pid: str, opp_abbrev: str):
    """
    Compute mean & std for PTS, REB, AST from last H2H_LOOKBACK_GAMES vs opp_abbrev.
    """
    games = fetcher.get_recent_games_stats(pid, num_games=50) or []
    h2h = [g for g in games if f" {opp_abbrev}" in g["MATCHUP"]][:H2H_LOOKBACK_GAMES]
    if not h2h:
        log("No head-to-head games found.")
        return {}, {}
    df = pd.DataFrame(h2h)
    means = df[["PTS","REB","AST"]].astype(float).mean().to_dict()
    stds  = df[["PTS","REB","AST"]].astype(float).std().to_dict()
    log(f"H2H means: {means}, stds: {stds}")
    return means, stds

def compute_recent_distribution(fetcher: NBAStatsFetcher, pid: str, line_choice: str):
    """
    Compute mean & std for the last RECENT_LOOKBACK games for the chosen stat(s).
    """
    games = fetcher.get_recent_games_stats(pid, num_games=RECENT_LOOKBACK) or []
    vals = []
    for g in games[:RECENT_LOOKBACK]:
        s = 0
        if "P" in line_choice: s += float(g["PTS"])
        if "R" in line_choice: s += float(g["REB"])
        if "A" in line_choice: s += float(g["AST"])
        vals.append(s)
    if not vals:
        return 0.0, 0.0
    mean = float(np.mean(vals))
    std  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
    log(f"Recent {line_choice}: mean={mean}, std={std}")
    return mean, std

# -----------------------------------------------------------------------
#  SECTION 5: INJURY USAGE IMPACT
# -----------------------------------------------------------------------

def compute_injury_usage_impact(fetcher: NBAStatsFetcher, injuries: pd.DataFrame):
    """
    Sum USG% of each injured player, then return multiplier:
      1 + (total_usg% * INJ_USAGE_WEIGHT)
    """
    total_usg = 0.0
    for name in injuries["PLAYER"]:
        try:
            _, adv, _ = get_player_advanced(fetcher, name)
            usg = adv.get("USG_PCT", 0.0)
            total_usg += usg
            log(f"Injured {name} USG%={usg}")
        except Exception:
            log(f"Could not fetch advanced for injured {name}")
    mult = 1.0 + (total_usg * INJ_USAGE_WEIGHT)
    log(f"Injury usage multiplier: {mult:.3f} (total_usg={total_usg:.1f}%)")
    return mult

# -----------------------------------------------------------------------
#  SECTION 6: LINE INPUT PROMPTS
# -----------------------------------------------------------------------

def prompt_stat_choice():
    valid = {"P","R","A","PR","PA","RA","PRA"}
    while True:
        c = input("What stat(s)? (P, R, A or combo e.g. 'PR'): ").strip().upper()
        if c in valid:
            return c
        print("Invalid; try one of:", ", ".join(sorted(valid)))

def prompt_line_value():
    while True:
        raw = input("Enter your predicted line value (e.g. 23.5): ").strip()
        try:
            return float(raw)
        except:
            print("Invalid number; try again.")

def prompt_over_under():
    while True:
        raw = input("Over or Under? (O/U): ").strip().upper()
        if raw in {"O","U"}:
            return raw
        print("Invalid; enter O or U.")

# -----------------------------------------------------------------------
#  SECTION 7: MAIN WORKFLOW
# -----------------------------------------------------------------------

def main():
    print("\n" + "="*60)
    print("      NBA Hypothetical Line Predictor")
    print("="*60 + "\n")

    # 1) Select your team & player
    your_abbrev, roster_df, stats_df, inj_df = select_team(
        "What team would you like to find a player to bet on?"
    )
    display_roster_names(roster_df, inj_df)
    player_name = choose_player(roster_df)
    position    = roster_df.loc[roster_df["PLAYER"]==player_name, "POSITION"].iloc[0]

    # 2) Select opponent & defender
    opp_abbrev, _, _, _ = select_team("Name your hypothetical OPPONENT team")
    defender = find_opponent_starter(opp_abbrev, position)

    # 3) Fetch all metrics
    fetcher = NBAStatsFetcher()
    pid = fetcher.search_player_nba(player_name)
    base, adv, hustle = get_player_advanced(fetcher, player_name)
    _, opp_adv, _     = get_player_advanced(fetcher, defender)

    # 4) Baseline per-game total for stat_choice
    stat_choice = prompt_stat_choice()
    baseline = sum(
        base.get("PTS",0) if c=="P" else
        base.get("REB",0) if c=="R" else
        base.get("AST",0) if c=="A" else 0
        for c in stat_choice
    )
    log(f"Baseline per-game {stat_choice} = {baseline:.1f}")

    # 5) Head-to-head & recent
    h2h_means, h2h_stds       = compute_head_to_head(fetcher, pid, opp_abbrev)
    recent_mean, recent_std   = compute_recent_distribution(fetcher, pid, stat_choice)

    # 6) Injury usage
    inj_usage_mult = compute_injury_usage_impact(fetcher, inj_df)

    # 7) Prompt line
    line_val = prompt_line_value()
    ou       = prompt_over_under()

    # 8) Blend mean & std
    h2h_mean = h2h_means.get(stat_choice, baseline) if len(stat_choice)==1 else baseline
    blend_mean = (
        0.4 * baseline +
        0.3 * recent_mean +
        0.2 * h2h_mean +
        0.1 * (baseline * inj_usage_mult)
    )
    blend_std = recent_std

    # 9) Base probability
    prob = calc_prob(blend_mean, blend_std, line_val, ou)

    # 10) Offense & pace adjustment
    off_factor  = adv.get("OFF_RATING", LEAGUE_AVG_OFF_RATING) / LEAGUE_AVG_OFF_RATING
    pace_factor = adv.get("PACE", LEAGUE_AVG_PACE) / LEAGUE_AVG_PACE
    prob *= off_factor * pace_factor

    # 11) Defender defensive rating adjustment
    def_factor = LEAGUE_AVG_DEF_RATING / opp_adv.get("DEF_RATING", LEAGUE_AVG_DEF_RATING)
    prob *= def_factor

    # 12) Clamp and output
    prob = max(0.0, min(1.0, prob))

    print("\n" + "-"*50)
    print(f"Matchup: {player_name} vs {defender}")
    print(f"Line: {stat_choice} {ou} {line_val}")
    print("-"*50)
    print(f"Estimated probability: {prob*100:.2f}%\n")
    print("Breakdown of factors:")
    print(f" • Baseline per-game:       {baseline:.1f}")
    print(f" • Recent mean/std:         {recent_mean:.1f} / {recent_std:.1f}")
    if h2h_means:
        print(f" • H2H mean:                {h2h_mean:.1f}")
    print(f" • Injury usage multiplier: {inj_usage_mult:.2f}×")
    print(f" • Blended mean:            {blend_mean:.1f}")
    print(f" • Std used:                {blend_std:.1f}")
    print(f" • Off. Rating factor:      {off_factor:.2f}×")
    print(f" • Pace factor:             {pace_factor:.2f}×")
    print(f" • Defender factor:         {def_factor:.2f}×")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
