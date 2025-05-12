import requests
from bs4 import BeautifulSoup
from unidecode import unidecode
from tabulate import tabulate
from datetime import datetime

class NBAStatsFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.nba.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Cache for player IDs
        self.nba_player_ids = {}
        self.current_season = "2024-25"
    
    def _normalize_name(self, name):
        """Normalize player name for comparison"""
        return unidecode(name.lower()).replace('.', '').replace('-', ' ').replace("'", '')
    
    def _format_percentage(self, value):
        """Format percentage values to show as XX.X%"""
        if value is None:
            return "N/A"
        try:
            return f"{float(value)*100:.1f}%"
        except (ValueError, TypeError):
            return str(value)
    
    def search_player_nba(self, player_name):
        """Find NBA.com player ID for a given name"""
        normalized_name = self._normalize_name(player_name)
        
        # First, try to get the entire player list from NBA stats API
        players_url = "https://stats.nba.com/stats/playerindex?Historical=0&LeagueID=00&Season=2024-25"
        
        try:
            response = requests.get(players_url, headers=self.headers)
            data = response.json()
            
            # Extract player data
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            player_data = []
            for row in rows:
                player_data.append(dict(zip(headers, row)))
            
            # Search for the player by name
            for player in player_data:
                player_full_name = f"{player['PLAYER_FIRST_NAME']} {player['PLAYER_LAST_NAME']}"
                if self._normalize_name(player_full_name) == normalized_name:
                    player_id = player['PERSON_ID']
                    print(f"Found player on NBA.com: {player_full_name} (ID: {player_id})")
                    
                    # Store in cache
                    self.nba_player_ids[normalized_name] = player_id
                    return player_id
            
            # If we reach here, try an alternative approach with a search endpoint
            print(f"Player '{player_name}' not found in NBA.com player index, trying search...")
            
            # This is a backup approach - try to search via NBA.com's search functionality
            search_url = f"https://ak-static.cms.nba.com/wp-content/themes/nba-cms-game-theme/includes/autosuggest.php?term={normalized_name}&league=nba"
            
            response = requests.get(search_url, headers=self.headers)
            search_results = response.json()
            
            for player in search_results:
                if player['taxonomy'] == 'player':
                    # Extract player ID from URL
                    match = re.search(r'/player/(\d+)/', player['url'])
                    if match:
                        player_id = match.group(1)
                        print(f"Found player on NBA.com: {player['title']} (ID: {player_id})")
                        
                        # Store in cache
                        self.nba_player_ids[normalized_name] = player_id
                        return player_id
            
            print(f"No NBA players found matching '{player_name}' on NBA.com")
            return None
            
        except Exception as e:
            print(f"Error searching for player on NBA.com: {e}")
            return None
    
    def get_nba_stats(self, player_id, measure_type, season_type="Regular Season"):
        """Generic method to fetch stats from NBA.com"""
        url = "https://stats.nba.com/stats/playerdashboardbyyearoveryear"
        params = {
            "DateFrom": "",
            "DateTo": "",
            "GameSegment": "",
            "LastNGames": "0",
            "LeagueID": "00",
            "Location": "",
            "MeasureType": measure_type,
            "Month": "0",
            "OpponentTeamID": "0",
            "Outcome": "",
            "PORound": "0",
            "PaceAdjust": "N",
            "PerMode": "PerGame",
            "Period": "0",
            "PlayerID": player_id,
            "PlusMinus": "N",
            "Rank": "N",
            "Season": self.current_season,
            "SeasonSegment": "",
            "SeasonType": season_type,
            "ShotClockRange": "",
            "Split": "yoy",
            "VsConference": "",
            "VsDivision": ""
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching stats: Status code {response.status_code}")
                return None
                
            data = response.json()
            result_sets = data.get('resultSets', [])
            
            if not result_sets:
                print("No result sets found in response")
                return None
                
            # Get the last entry which should be the current season
            rows = result_sets[0].get('rowSet', [])
            if not rows:
                return None
                
            current_season = rows[-1]
            headers = result_sets[0].get('headers', [])
            
            return dict(zip(headers, current_season))
            
        except Exception as e:
            print(f"Error fetching stats: {e}")
            return None
    
    def get_nba_hustle_stats(self, player_id, season_type="Regular Season"):
        """Get hustle stats from NBA.com"""
        url = "https://stats.nba.com/stats/leaguehustlestatsplayer"
        params = {
            "College": "",
            "Conference": "",
            "Country": "",
            "DateFrom": "",
            "DateTo": "",
            "Division": "",
            "DraftPick": "",
            "DraftYear": "",
            "GameScope": "",
            "GameSegment": "",
            "Height": "",
            "LastNGames": "0",
            "LeagueID": "00",
            "Location": "",
            "Month": "0",
            "OpponentTeamID": "0",
            "Outcome": "",
            "PORound": "0",
            "PaceAdjust": "N",
            "PerMode": "PerGame",
            "Period": "0",
            "PlayerExperience": "",
            "PlayerPosition": "",
            "PlusMinus": "N",
            "Rank": "N",
            "Season": self.current_season,
            "SeasonSegment": "",
            "SeasonType": season_type,
            "ShotClockRange": "",
            "StarterBench": "",
            "TeamID": "0",
            "VsConference": "",
            "VsDivision": "",
            "Weight": ""
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching hustle stats: Status code {response.status_code}")
                return None
                
            data = response.json()
            
            # Extract headers and rows
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            # Find our player
            for row in rows:
                player_stats = dict(zip(headers, row))
                if str(player_stats['PLAYER_ID']) == str(player_id):
                    return player_stats
            
            print(f"Player ID {player_id} not found in hustle stats")
            return None
            
        except Exception as e:
            print(f"Error fetching hustle stats: {e}")
            return None
    
    def get_recent_games_stats(self, player_id, season_type="Regular Season", num_games=5):
        """Get stats from recent games"""
        url = "https://stats.nba.com/stats/playergamelog"
        params = {
            "DateFrom": "",
            "DateTo": "",
            "LeagueID": "00",
            "PlayerID": player_id,
            "Season": self.current_season,
            "SeasonType": season_type
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error fetching recent games: Status code {response.status_code}")
                return None
                
            data = response.json()
            result_sets = data.get('resultSets', [])
            
            if not result_sets:
                print("No result sets found in recent games response")
                return None
                
            headers = result_sets[0]['headers']
            rows = result_sets[0]['rowSet']
            
            recent_games = []
            for row in rows[:num_games]:
                game_stats = dict(zip(headers, row))
                
                # Calculate advanced metrics for each game
                fga = game_stats.get('FGA', 0)
                fgm = game_stats.get('FGM', 0)
                fg3a = game_stats.get('FG3A', 0)
                fg3m = game_stats.get('FG3M', 0)
                fta = game_stats.get('FTA', 0)
                ftm = game_stats.get('FTM', 0)
                pts = game_stats.get('PTS', 0)
                ast = game_stats.get('AST', 0)
                reb = game_stats.get('REB', 0)
                oreb = game_stats.get('OREB', 0)
                dreb = game_stats.get('DREB', 0)
                tov = game_stats.get('TOV', 0)
                stl = game_stats.get('STL', 0)
                blk = game_stats.get('BLK', 0)
                pf = game_stats.get('PF', 0)
                min_played = game_stats.get('MIN', 0)
                
                # Calculate percentages
                fg_pct = fgm / fga if fga > 0 else 0
                fg3_pct = fg3m / fg3a if fg3a > 0 else 0
                ft_pct = ftm / fta if fta > 0 else 0
                
                # Calculate advanced metrics
                ts_attempts = fga + 0.44 * fta
                ts_pct = pts / (2 * ts_attempts) if ts_attempts > 0 else 0
                
                efg_pct = (fgm + 0.5 * fg3m) / fga if fga > 0 else 0
                
                # Format game stats
                formatted_stats = {
                    'DATE': game_stats.get('GAME_DATE', 'N/A'),
                    'MATCHUP': game_stats.get('MATCHUP', 'N/A'),
                    'WL': game_stats.get('WL', 'N/A'),
                    'MIN': min_played,
                    'PTS': pts,
                    'REB': reb,
                    'AST': ast,
                    'STL': stl,
                    'BLK': blk,
                    'TOV': tov,
                    'PF': pf,
                    'FG%': self._format_percentage(fg_pct),
                    '3P%': self._format_percentage(fg3_pct),
                    'FT%': self._format_percentage(ft_pct),
                    'TS%': self._format_percentage(ts_pct),
                    'eFG%': self._format_percentage(efg_pct),
                    'OREB': oreb,
                    'DREB': dreb
                }
                
                recent_games.append(formatted_stats)
            
            return recent_games
            
        except Exception as e:
            print(f"Error fetching recent games: {e}")
            return None
    
    def format_stats_for_display(self, stats_dict, percentage_fields):
        """Format stats dictionary for display, converting specified fields to percentages"""
        if not stats_dict:
            return None
            
        formatted_stats = {}
        for key, value in stats_dict.items():
            if key in percentage_fields:
                formatted_stats[key] = self._format_percentage(value)
            else:
                formatted_stats[key] = value
                
        return formatted_stats
    
    def display_player_stats(self, player_name):
        """Display all stats for a player"""
        print(f"\n{'='*80}\nFetching stats for {player_name}\n{'='*80}")
        
        # Get player ID
        normalized_name = self._normalize_name(player_name)
        player_id = self.nba_player_ids.get(normalized_name)
        
        if not player_id:
            player_id = self.search_player_nba(player_name)
            
        if not player_id:
            print(f"Could not find NBA.com ID for {player_name}")
            return None
        
        # Percentage fields that need formatting
        percentage_fields = {
            'FG_PCT', 'FG3_PCT', 'FT_PCT', 'TS_PCT', 'EFG_PCT',
            'AST_PCT', 'OREB_PCT', 'DREB_PCT', 'REB_PCT', 'USG_PCT', 'PIE'
        }
        
        # Get regular season stats
        reg_traditional = self.get_nba_stats(player_id, "Base")
        reg_advanced = self.get_nba_stats(player_id, "Advanced")
        reg_hustle = self.get_nba_hustle_stats(player_id)
        reg_recent_games = self.get_recent_games_stats(player_id)
        
        # Get playoff stats if available
        playoff_traditional = self.get_nba_stats(player_id, "Base", "Playoffs")
        playoff_advanced = self.get_nba_stats(player_id, "Advanced", "Playoffs")
        playoff_hustle = self.get_nba_hustle_stats(player_id, "Playoffs")
        playoff_recent_games = self.get_recent_games_stats(player_id, "Playoffs")
        
        # Format all stats
        formatted_reg_traditional = self.format_stats_for_display(reg_traditional, percentage_fields)
        formatted_reg_advanced = self.format_stats_for_display(reg_advanced, percentage_fields)
        formatted_playoff_traditional = self.format_stats_for_display(playoff_traditional, percentage_fields)
        formatted_playoff_advanced = self.format_stats_for_display(playoff_advanced, percentage_fields)
        
        # Display Regular Season Stats
        print(f"\n{'='*80}\nRegular Season Stats (2024-25)\n{'='*80}")
        
        if formatted_reg_traditional:
            print("\nTraditional Stats:")
            relevant_traditional = {
                'GP': formatted_reg_traditional.get('GP'),
                'MIN': formatted_reg_traditional.get('MIN'),
                'PTS': formatted_reg_traditional.get('PTS'),
                'REB': formatted_reg_traditional.get('REB'),
                'AST': formatted_reg_traditional.get('AST'),
                'FG%': formatted_reg_traditional.get('FG_PCT'),
                '3P%': formatted_reg_traditional.get('FG3_PCT'),
                'FT%': formatted_reg_traditional.get('FT_PCT'),
                'STL': formatted_reg_traditional.get('STL'),
                'BLK': formatted_reg_traditional.get('BLK'),
                'TOV': formatted_reg_traditional.get('TOV')
            }
            for key, value in relevant_traditional.items():
                print(f"{key}: {value}")
        
        if formatted_reg_advanced:
            print("\nAdvanced Stats:")
            relevant_advanced = {
                'OFF_RTG': formatted_reg_advanced.get('OFF_RATING'),
                'DEF_RTG': formatted_reg_advanced.get('DEF_RATING'),
                'NET_RTG': formatted_reg_advanced.get('NET_RATING'),
                'TS%': formatted_reg_advanced.get('TS_PCT'),
                'eFG%': formatted_reg_advanced.get('EFG_PCT'),
                'AST%': formatted_reg_advanced.get('AST_PCT'),
                'OREB%': formatted_reg_advanced.get('OREB_PCT'),
                'DREB%': formatted_reg_advanced.get('DREB_PCT'),
                'REB%': formatted_reg_advanced.get('REB_PCT'),
                'USG%': formatted_reg_advanced.get('USG_PCT'),
                'PACE': formatted_reg_advanced.get('PACE'),
                'PIE': formatted_reg_advanced.get('PIE')
            }
            for key, value in relevant_advanced.items():
                print(f"{key}: {value}")
        
        if reg_hustle:
            print("\nHustle Stats:")
            relevant_hustle = {
                'CONTESTED_SHOTS': reg_hustle.get('CONTESTED_SHOTS'),
                'DEFLECTIONS': reg_hustle.get('DEFLECTIONS'),
                'CHARGES_DRAWN': reg_hustle.get('CHARGES_DRAWN'),
                'SCREEN_ASTS': reg_hustle.get('SCREEN_ASSISTS'),
                'LOOSE_BALLS_REC': reg_hustle.get('LOOSE_BALLS_RECOVERED'),
                'BOXOUTS': reg_hustle.get('DEF_BOXOUTS', 0) + reg_hustle.get('OFF_BOXOUTS', 0)
            }
            for key, value in relevant_hustle.items():
                print(f"{key}: {value}")
        
        if reg_recent_games:
            print(f"\nRecent Games (Last {len(reg_recent_games)}):")
            headers = ['DATE', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST', 'FG%', '3P%', 'FT%', 'TS%']
            rows = []
            for game in reg_recent_games:
                rows.append([
                    game['DATE'],
                    game['MATCHUP'],
                    game['MIN'],
                    game['PTS'],
                    game['REB'],
                    game['AST'],
                    game['FG%'],
                    game['3P%'],
                    game['FT%'],
                    game['TS%']
                ])
            print(tabulate(rows, headers=headers, tablefmt="github"))
        
        # Display Playoff Stats if available
        if formatted_playoff_traditional or formatted_playoff_advanced:
            print(f"\n{'='*80}\nPlayoff Stats (2024-25)\n{'='*80}")
            
            if formatted_playoff_traditional:
                print("\nTraditional Stats:")
                relevant_traditional = {
                    'GP': formatted_playoff_traditional.get('GP'),
                    'MIN': formatted_playoff_traditional.get('MIN'),
                    'PTS': formatted_playoff_traditional.get('PTS'),
                    'REB': formatted_playoff_traditional.get('REB'),
                    'AST': formatted_playoff_traditional.get('AST'),
                    'FG%': formatted_playoff_traditional.get('FG_PCT'),
                    '3P%': formatted_playoff_traditional.get('FG3_PCT'),
                    'FT%': formatted_playoff_traditional.get('FT_PCT'),
                    'STL': formatted_playoff_traditional.get('STL'),
                    'BLK': formatted_playoff_traditional.get('BLK'),
                    'TOV': formatted_playoff_traditional.get('TOV')
                }
                for key, value in relevant_traditional.items():
                    print(f"{key}: {value}")
            
            if formatted_playoff_advanced:
                print("\nAdvanced Stats:")
                relevant_advanced = {
                    'OFF_RTG': formatted_playoff_advanced.get('OFF_RATING'),
                    'DEF_RTG': formatted_playoff_advanced.get('DEF_RATING'),
                    'NET_RTG': formatted_playoff_advanced.get('NET_RATING'),
                    'TS%': formatted_playoff_advanced.get('TS_PCT'),
                    'eFG%': formatted_playoff_advanced.get('EFG_PCT'),
                    'AST%': formatted_playoff_advanced.get('AST_PCT'),
                    'OREB%': formatted_playoff_advanced.get('OREB_PCT'),
                    'DREB%': formatted_playoff_advanced.get('DREB_PCT'),
                    'REB%': formatted_playoff_advanced.get('REB_PCT'),
                    'USG%': formatted_playoff_advanced.get('USG_PCT'),
                    'PACE': formatted_playoff_advanced.get('PACE'),
                    'PIE': formatted_playoff_advanced.get('PIE')
                }
                for key, value in relevant_advanced.items():
                    print(f"{key}: {value}")
            
            if playoff_hustle:
                print("\nHustle Stats:")
                relevant_hustle = {
                    'CONTESTED_SHOTS': playoff_hustle.get('CONTESTED_SHOTS'),
                    'DEFLECTIONS': playoff_hustle.get('DEFLECTIONS'),
                    'CHARGES_DRAWN': playoff_hustle.get('CHARGES_DRAWN'),
                    'SCREEN_ASTS': playoff_hustle.get('SCREEN_ASSISTS'),
                    'LOOSE_BALLS_REC': playoff_hustle.get('LOOSE_BALLS_RECOVERED'),
                    'BOXOUTS': playoff_hustle.get('DEF_BOXOUTS', 0) + playoff_hustle.get('OFF_BOXOUTS', 0)
                }
                for key, value in relevant_hustle.items():
                    print(f"{key}: {value}")
            
            if playoff_recent_games:
                print(f"\nRecent Playoff Games (Last {len(playoff_recent_games)}):")
                headers = ['DATE', 'MATCHUP', 'MIN', 'PTS', 'REB', 'AST', 'FG%', '3P%', 'FT%', 'TS%']
                rows = []
                for game in playoff_recent_games:
                    rows.append([
                        game['DATE'],
                        game['MATCHUP'],
                        game['MIN'],
                        game['PTS'],
                        game['REB'],
                        game['AST'],
                        game['FG%'],
                        game['3P%'],
                        game['FT%'],
                        game['TS%']
                    ])
                print(tabulate(rows, headers=headers, tablefmt="github"))

def main():
    fetcher = NBAStatsFetcher()
    
    while True:
        print("\nNBA Player Stats Fetcher")
        print("1. Look up player stats")
        print("2. Exit")
        
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == '1':
            player_name = input("Enter player name: ").strip()
            if player_name:
                fetcher.display_player_stats(player_name)
            else:
                print("Please enter a valid player name.")
        elif choice == '2':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    main()