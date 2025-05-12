import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

def get_player_recent_games(player_id: str, player_name: str):
    url = f"https://www.espn.com/nba/player/_/id/{player_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("Error fetching page.")
        return

    soup = BeautifulSoup(res.text, "html.parser")
    recent_section = soup.select_one('section:-soup-contains("Recent Games")')
    if not recent_section:
        print("Could not find 'Recent Games' section.")
        return

    table = recent_section.find("table")
    if not table:
        print("Could not find game table.")
        return

    rows = table.find("tbody").find_all("tr")
    games = []

    for row in rows:
        cols = [td.text.strip() for td in row.find_all("td")]
        if len(cols) >= 13:
            date = cols[0]
            opp = cols[1]
            result = cols[2]
            min_played = cols[3]
            fg_pct = cols[4] + '%'
            three_pct = cols[5] + '%'
            ft_pct = cols[6] + '%'
            reb = cols[7]
            ast = cols[8]
            blk = cols[9]
            stl = cols[10]
            to = cols[11]
            pf = cols[12]
            pts = cols[13]

            games.append([
                date, opp, result, min_played, pts, reb, ast, stl, blk, to, pf, fg_pct, ft_pct, three_pct
            ])
        elif "Semifinals" not in cols[0]:  # Skip headings
            print("Skipping incomplete row:", cols)

    if not games:
        print("No recent games found.")
        return

    headers = ["DATE", "OPP", "RESULT", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "FG%", "FT%", "3P%"]
    print(f"\nLast 5 Games for {player_name}")
    print(tabulate(games[:5], headers=headers, tablefmt="github"))

# User input
if __name__ == "__main__":
    player_id = input("Enter ESPN Player ID (e.g. 4065648 for Tatum): ").strip()
    player_name = input("Enter Player Name: ").strip()
    get_player_recent_games(player_id, player_name)
