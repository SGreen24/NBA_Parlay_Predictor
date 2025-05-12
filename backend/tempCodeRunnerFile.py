import requests
from datetime import datetime
import pytz

API_KEY = 'be659f16abe2a1dcac28190abd652ac3'
SPORT = 'basketball_nba'
REGIONS = 'us'
MARKETS = 'player_points,player_rebounds,player_assists,player_points_rebounds_assists'
ODDS_FORMAT = 'american'

def fetch_today_events():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events'
    params = {'apiKey': API_KEY}
    res = requests.get(url, params=params)
    if res.status_code != 200:
        print(f"Failed to fetch events: {res.status_code}")
        print(res.text)
        return []
    return res.json()

def find_event(events, player_name):
    # crude check: find team with matching player name part
    last = player_name.split()[-1].lower()
    for event in events:
        matchup = f"{event['away_team']} @ {event['home_team']}".lower()
        if any(team for team in matchup.split(' @ ') if last in team.lower()):
            return event['id'], f"{event['away_team']} @ {event['home_team']}"
    return None, None

def fetch_player_props(event_id):
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT
    }
    res = requests.get(url, params=params)
    if res.status_code != 200:
        print(f"Failed to fetch odds: {res.status_code}")
        print(res.text)
        return None
    return res.json()

def display_player_props(data, player_name):
    last = player_name.split()[-1].lower()
    found = False

    for book in data.get("bookmakers", []):
        print(f"\n📊 Bookmaker: {book['title']}")
        for market in book.get("markets", []):
            market_name = market["key"].replace("player_", "").replace("_", " ").title()
            for outcome in market.get("outcomes", []):
                name = outcome["name"].lower()
                if last in name:
                    point = outcome.get("point", "N/A")
                    odds = outcome.get("price", "N/A")
                    print(f"  • {market_name}: Line = {point}, Odds = {odds}")
                    found = True
    if not found:
        print(f"⚠️ No player props found for '{player_name}'.")

def main():
    player_input = input("Enter the player's full name (e.g., Jayson Tatum): ").strip()
    events = fetch_today_events()
    if not events:
        return

    event_id, matchup = find_event(events, player_input)
    if not event_id:
        print(f"❌ No event found today for '{player_input}'.")
        return

    print(f"✅ Found matchup: {matchup}")
    props = fetch_player_props(event_id)
    if props:
        display_player_props(props, player_input)

if __name__ == '__main__':
    main()
