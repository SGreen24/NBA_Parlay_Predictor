#!/usr/bin/env python3
"""
NBA Daily Line Predictor (v4)
==============================
Adds:
  - Probability calculator for range of betting lines
  - Adjusted final odds based on matchup factors
"""

import requests
import math
import numpy as np
import pandas as pd
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from advanced_metrics import NBAStatsFetcher
from recent_games import get_espn_player_id
from team_fetcher import (
    fetch_full_roster,
    fetch_team_per_game_stats,
    fetch_espn_injuries,
)

# -----------------------------------------------------------------------
# CONFIG & CONSTANTS
# -----------------------------------------------------------------------
WEIGHTS = {"baseline":0.35,"recent":0.30,"h2h":0.20,"injury":0.15}
REST_FACTOR = {"b2b":0.90,"short":0.98,"normal":1.02}
MIN_EMPIRICAL = 10
H2H_GAMES     = 5
RECENT_GAMES  = 5
INJ_WEIGHT    = 0.01
LETTER_MAP    = {"P":"PTS","R":"REB","A":"AST"}

# static league averages
LG_OFF = 110.0
LG_DEF = 110.0
LG_PACE= 100.0

# -----------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------
def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.3, status_forcelist=(500,502,503,504))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def empirical_prob(vals, line, ou):
    arr = np.array(vals)
    if ou=="O":
        return float((arr>line).sum()/len(arr))
    return float((arr<line).sum()/len(arr))

def gauss_prob(mean, std, line, ou):
    if std<=0:
        return 1.0 if (ou=="O" and mean>line) or (ou=="U" and mean<line) else 0.0
    z=(line-mean)/std
    return (1-normal_cdf(z)) if ou=="O" else normal_cdf(z)

def compute_injury_usage_impact(fetcher, injuries):
    total_usg = 0.0
    for name in injuries["PLAYER"]:
        try:
            _, adv = get_player_stats(fetcher, name, "Playoffs")
            usg = adv.get("USG_PCT", 0.0)
            total_usg += usg
            log(f"Injured {name} USG% = {usg}")
        except:
            log(f"Could not fetch injured {name}")
    mult = 1 + (total_usg * INJ_WEIGHT)
    log(f"Injury multiplier: {mult:.3f}")
    return mult

def get_rest_factor(fetcher, pid):
    recent = fetcher.get_recent_games_stats(pid, num_games=1) or []
    if not recent or "DATE" not in recent[0]:
        return REST_FACTOR["normal"]
    last = pd.to_datetime(recent[0]["DATE"], errors="coerce")
    if pd.isna(last):
        return REST_FACTOR["normal"]
    days = (datetime.now()-last.to_pydatetime()).days
    return REST_FACTOR["b2b"] if days==0 else REST_FACTOR["short"] if days==1 else REST_FACTOR["normal"]

def get_player_stats(fetcher, name, season_type="Regular Season"):
    pid = fetcher.search_player_nba(name)
    if pid is None:
        raise ValueError(f"No NBA.com ID for {name}")
    base   = fetcher.get_nba_stats(pid,"Base",season_type)     or {}
    adv    = fetcher.get_nba_stats(pid,"Advanced",season_type) or {}
    hustle = fetcher.get_nba_hustle_stats(pid,season_type)     or {}
    log(f"{name} ({season_type}): OffRT={adv.get('OFF_RATING')}, DefRT={adv.get('DEF_RATING')}, Pace={adv.get('PACE')}, USG%={adv.get('USG_PCT')}")
    return pid, base, adv, hustle

def generate_probabilities(blend_mean, blend_std, hist_vals, adv_reg, opp_adv_reg, inj_mult, rest_mult, home_mult, ou, line_min, line_max):
    results = []
    for line in np.arange(line_min, line_max + 1):
        if len(hist_vals) >= MIN_EMPIRICAL:
            p_raw = empirical_prob(hist_vals, line, ou)
        else:
            p_raw = gauss_prob(blend_mean, blend_std, line, ou)

        off_f  = adv_reg.get("OFF_RATING", LG_OFF) / LG_OFF
        pace_f = adv_reg.get("PACE", LG_PACE) / LG_PACE
        def_f  = LG_DEF / opp_adv_reg.get("DEF_RATING", LG_DEF)

        p_final = p_raw * off_f * pace_f * def_f * inj_mult * rest_mult * home_mult
        p_final = max(0, min(1, p_final))
        results.append((line, p_final))

    return sorted(results, key=lambda x: x[1], reverse=(ou == "O"))

# -----------------------------------------------------------------------
# MENU
# -----------------------------------------------------------------------
def select_team(prompt):
    while True:
        abb = input(f"{prompt} (NBA abbrev): ").strip().upper()
        try:
            r, pg, inj = fetch_full_roster(abb), fetch_team_per_game_stats(abb), fetch_espn_injuries(abb)
            log(f"Loaded {abb}")
            return abb, r, pg, inj
        except Exception as e:
            log(f"Error loading {abb}: {e}")
            print("Try again.\n")

def display_roster(r_df, inj_df):
    inj = set(inj_df["PLAYER"])
    print("\nRoster:")
    for n in r_df["PLAYER"]:
        suffix = " (Inactive)" if n in inj else ""
        print(f"  - {n}{suffix}")
    print("")

def choose_player(r_df):
    names = r_df["PLAYER"].tolist()
    while True:
        n = input("Choose your player (full name): ").strip()
        if n in names:
            log(f"Player chosen: {n}")
            return n
        print("Name not found; try again.")

def find_defender(opp, pos):
    df = fetch_full_roster(opp)
    injuries = fetch_espn_injuries(opp)
    injured_players = set(injuries["PLAYER"])

    # Filter defenders by position
    matches = [r["PLAYER"] for _, r in df.iterrows() if r["POSITION"] == pos]

    if not matches:
        raise ValueError(f"No players found for position {pos} on team {opp}.")

    # Return the first healthy player
    for defender in matches:
        if defender not in injured_players:
            log(f"Defender chosen: {defender} ({pos})")
            return defender

    # If all are injured, fallback to first
    fallback = matches[0]
    log(f"⚠️ All {pos} players on {opp} are inactive. Using {fallback} by default.")
    return fallback


def prompt_stat():
    valid={"P","R","A","PR","PA","RA","PRA"}
    while True:
        c=input("What stat(s)? (P, R, A or combo e.g. 'PRA'): ").strip().upper()
        if c in valid: return c
        print("Invalid; try again.")

def prompt_ou():
    while True:
        o=input("Over or Under? (O/U): ").strip().upper()
        if o in {"O","U"}: return o
        print("Enter O or U.")

# -----------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------
def main():
    sess    = make_session()
    fetcher = NBAStatsFetcher()
    fetcher.session = sess

    print("\n" + "="*60)
    print("🏀  NBA DAILY LINE PREDICTOR v4 — SMART BETTING INSIGHTS")
    print("="*60 + "\n")

    print("🔷 STEP 1: SELECT TEAMS")
    your, roster_df, _, inj_df = select_team("➤ Your team abbreviation")
    display_roster(roster_df, inj_df)
    player = choose_player(roster_df)
    pos    = roster_df.loc[roster_df["PLAYER"]==player,"POSITION"].iloc[0]

    opp, _, _, _ = select_team("➤ Opponent team abbreviation")
    defender = find_defender(opp, pos)

    print("\n🔷 STEP 2: FETCHING PLAYER METRICS (Regular Season & Playoffs)")
    pid, base_reg, adv_reg, hustle_reg             = get_player_stats(fetcher, player,   "Regular Season")
    _,   _,       opp_adv_reg, opp_hustle_reg      = get_player_stats(fetcher, defender, "Regular Season")
    _,   base_pl, adv_pl,    hustle_pl             = get_player_stats(fetcher, player,   "Playoffs")
    _,   _,       opp_adv_pl, opp_hustle_pl        = get_player_stats(fetcher, defender, "Playoffs")

    # ---------------------------- REGULAR SEASON ----------------------------
    print("\n" + "="*60)
    print("🟦 REGULAR SEASON METRICS — Player vs Defender")
    print("="*60)

    print("\n📊 Advanced Metrics")
    percent_stats = {"USG_PCT", "TS_PCT", "EFG_PCT", "AST_PCT", "OREB_PCT", "DREB_PCT", "PIE"}
    for m in ["OFF_RATING","DEF_RATING","PACE","USG_PCT","TS_PCT","EFG_PCT","AST_PCT","OREB_PCT","DREB_PCT","PIE"]:
        pv, dv = adv_reg.get(m, 0), opp_adv_reg.get(m, 0)
        diff = pv - dv

        if m in percent_stats:
            pv_display = f"{pv*100:.1f}%"
            dv_display = f"{dv*100:.1f}%"
            diff_display = f"{diff*100:+.1f}%"
        else:
            pv_display = f"{pv:>5.1f}"
            dv_display = f"{dv:>5.1f}"
            diff_display = f"{diff:+.1f}"

        print(f"  • {m:12}: {pv_display:>7} vs {dv_display:>7}   Δ {diff_display}")

    print("\n🛡️ Hustle Metrics")
    for h in ["CONTESTED_SHOTS","DEFLECTIONS","CHARGES_DRAWN","SCREEN_ASSISTS","LOOSE_BALLS_RECOVERED","DEF_BOXOUTS","OFF_BOXOUTS"]:
        ph, dh = hustle_reg.get(h, 0), opp_hustle_reg.get(h, 0)
        print(f"  • {h:25}: {ph:>5.0f} vs {dh:>5.0f}   Δ {ph - dh:+.3f}")

    # ------------------------------ PLAYOFFS -------------------------------
    print("\n" + "="*60)
    print("🟥 PLAYOFF METRICS — Player vs Defender")
    print("="*60)

    print("\n📊 Advanced Metrics")
    for m in ["OFF_RATING","DEF_RATING","PACE","USG_PCT","TS_PCT","EFG_PCT","AST_PCT","OREB_PCT","DREB_PCT","PIE"]:
        pv, dv = adv_pl.get(m, 0), opp_adv_pl.get(m, 0)
        diff = pv - dv

        if m in percent_stats:
            pv_display = f"{pv*100:.1f}%"
            dv_display = f"{dv*100:.1f}%"
            diff_display = f"{diff*100:+.1f}%"
        else:
            pv_display = f"{pv:>5.1f}"
            dv_display = f"{dv:>5.1f}"
            diff_display = f"{diff:+.1f}"

        print(f"  • {m:12}: {pv_display:>7} vs {dv_display:>7}   Δ {diff_display}")

    print("\n🛡️ Hustle Metrics")
    for h in ["CONTESTED_SHOTS","DEFLECTIONS","CHARGES_DRAWN","SCREEN_ASSISTS","LOOSE_BALLS_RECOVERED","DEF_BOXOUTS","OFF_BOXOUTS"]:
        ph, dh = hustle_pl.get(h, 0), opp_hustle_pl.get(h, 0)
        print(f"  • {h:25}: {ph:>5.0f} vs {dh:>5.0f}   Δ {ph - dh:+.3f}")

    # ---------------------------- STAT CHOICE ----------------------------
    print("\n🔷 STEP 3: STATISTIC TO ANALYZE")
    stat_choice = prompt_stat()
    baseline    = sum(base_reg.get(LETTER_MAP[c], 0) for c in stat_choice)

    hist = fetcher.get_recent_games_stats(pid, num_games=RECENT_GAMES * 4) or []
    hist_vals = [sum(float(g[LETTER_MAP[c]]) for c in stat_choice) for g in hist]
    recent_mean, recent_std = (np.mean(hist_vals), np.std(hist_vals, ddof=1)) if hist_vals else (0, 0)

    h2h_games = [g for g in hist if opp in g.get("MATCHUP", "")][:H2H_GAMES]
    h2h_vals = [sum(float(g[LETTER_MAP[c]]) for c in stat_choice) for g in h2h_games]
    h2h_mean = np.mean(h2h_vals) if h2h_vals else baseline

    inj_mult  = compute_injury_usage_impact(fetcher, inj_df)
    rest_mult = get_rest_factor(fetcher, pid)
    home_mult = 1.0  # optional

    blend_mean = (
        WEIGHTS["baseline"] * baseline +
        WEIGHTS["recent"]   * recent_mean +
        WEIGHTS["h2h"]      * h2h_mean +
        WEIGHTS["injury"]   * (baseline * inj_mult)
    )
    blend_std = recent_std

    # ---------------------------- LINE RANGE ----------------------------
    print("\n🔷 STEP 4: LINE RANGE INPUT")
    line_min = float(input("➤ Minimum line (e.g. 20.5): ").strip())
    line_max = float(input("➤ Maximum line (e.g. 35.5): ").strip())
    ou       = prompt_ou()

    results = generate_probabilities(
        blend_mean, blend_std, hist_vals,
        adv_reg, opp_adv_reg,
        inj_mult, rest_mult, home_mult,
        ou, line_min, line_max
    )

    print("\n✅ FINAL PROBABILITY RANKINGS")
    print(f"{player} vs {defender} | {stat_choice} ({ou})")
    print("-" * 45)
    for line, prob in results:
        print(f" • {stat_choice} {ou} {line:.1f}: {prob*100:.1f}% chance")
    print("-" * 45 + "\n")



if __name__ == "__main__":
    main()
