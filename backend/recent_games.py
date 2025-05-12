import requests
from tabulate import tabulate
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_espn_player_id(name: str):
    """
    Scan every NBA team's roster via the hidden API until we find a matching displayName.
    Returns (player_id, display_name) or (None, None) if not found.
    """
    # 1) Fetch all NBA teams
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    res = requests.get(teams_url, headers=HEADERS)
    res.raise_for_status()
    teams = res.json()["sports"][0]["leagues"][0]["teams"]  # List of { "team": { "id": ..., ... } }
    
    # 2) For each team, pull its roster
    for t in teams:
        team_id = t["team"]["id"]
        roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
        r = requests.get(roster_url, headers=HEADERS)
        if r.status_code != 200:
            continue
        # roster JSON sometimes nests under "athletes" or "roster"
        rosters = r.json().get("athletes") or r.json().get("roster", [])
        for p in rosters:
            if p.get("displayName", "").lower() == name.lower():
                return str(p["id"]), p["displayName"]
    return None, None

def get_player_recent_games(player_id: str, player_name: str):
    url = f"https://www.espn.com/nba/player/_/id/{player_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print("Error fetching page.")
        return
    
    # Import BeautifulSoup properly
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(res.text, "html.parser")
    
    recent_section = soup.select_one('section:-soup-contains("Recent Games")')
    if not recent_section:
        print("Could not find 'Recent Games' section.")
        return
        
    table = recent_section.find("table")
    if not table:
        print("Could not find game table.")
        return
        
    games = []
    rows = table.find("tbody").find_all("tr")
    for row in rows:
        cols = [td.text.strip() for td in row.find_all("td")]
        if len(cols) >= 14:
            date, opp, result, mins = cols[0], cols[1], cols[2], cols[3]
            fg_pct, three_pct, ft_pct = cols[4] + "%", cols[5] + "%", cols[6] + "%"
            reb, ast, blk = cols[7], cols[8], cols[9]
            stl = cols[10]
            to = cols[12]
            pf = cols[11]
            pts = cols[13]
            games.append([
                date, opp, result, mins,
                pts, reb, ast, stl, blk,
                to, pf,
                fg_pct, ft_pct, three_pct
            ])
            
    if not games:
        print("No recent games found.")
        return
        
    headers = ["DATE","OPP","RESULT","MIN","PTS","REB","AST","STL","BLK","TO","PF","FG%","FT%","3P%"]
    print(f"\nLast 5 Games for {player_name}")
    print(tabulate(games[:5], headers=headers, tablefmt="github"))

if __name__ == "__main__":
    name = input("Enter player name: ").strip()
    pid, display = get_espn_player_id(name)
    if not pid:
        print(f"No ESPN player found matching '{name}'.")
    else:
        get_player_recent_games(pid, display)