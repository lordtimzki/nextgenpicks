import httpx
import os
# nba_api imports moved inside functions to avoid timeouts during deployment loading

# NOTE: In Cloud Functions, env vars like ODDS_API_KEY should be set in the function configuration 
# or via Secret Manager.
ODDS_KEY = os.getenv("ODDS_API_KEY")

# Get player data using nba api
def get_player_data(player_name):
    # Lazy import to speed up cold starts and deployment discovery
    from nba_api.stats.static import players, teams
    from nba_api.stats.endpoints import playergamelog, commonplayerinfo

    print(f"DEBUG: Searching for {player_name} on NBA.com...")
    
    nba_players = players.find_players_by_full_name(player_name)
    if not nba_players:
        return None

    player = nba_players[0]
    player_id = player['id']
    full_name = player['full_name']
    
    # Image url
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
    
    # Get player position from commonplayerinfo
    position = "N/A"
    try:
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        info_dict = player_info.get_normalized_dict()['CommonPlayerInfo']
        if info_dict:
            # Position field contains the player's position (e.g., "Center", "Guard", "Forward")
            position = str(info_dict[0].get('POSITION', 'N/A'))
            print(f"DEBUG: {full_name} position: {position}")
    except Exception as e:
        print(f"WARNING: Could not fetch player position: {e}")

    try:
        log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
        games_dict = log.get_normalized_dict()['PlayerGameLog']
    except Exception as e:
        print(f"ERROR: NBA API failed {e}")
        return None

    recent_games = []
    total_pts = 0
    total_reb = 0
    total_ast = 0
    
    # Safety check if it's a rookie with 0 games
    last_10 = games_dict[:10]
    
    # Set default values if no games found
    team_abbreviation = "UNK"
    if last_10:
         team_abbreviation = str(last_10[0]['MATCHUP'].split(" ")[0])

    team_full_name = "Unknown"

    # 'teams' is imported at the start of the function now
    nba_team = teams.find_team_by_abbreviation(team_abbreviation)
    if nba_team:
        team_full_name = nba_team['full_name']
    
    # Fallback: specific fix for common mismatches if API differs
    if team_abbreviation == "GSW": team_full_name = "Golden State Warriors"
    if team_abbreviation == "NYK": team_full_name = "New York Knicks"
    if team_abbreviation == "BKN": team_full_name = "Brooklyn Nets"
    if team_abbreviation == "PHX": team_full_name = "Phoenix Suns"

    for game in last_10:
        recent_games.append({
            "date": str(game['GAME_DATE']),
            "matchup": str(game['MATCHUP']),
            "pts": int(game['PTS']),
            "reb": int(game['REB']),
            "ast": int(game['AST']),
            "min": str(game['MIN'])
        })
        total_pts += int(game['PTS'])
        total_reb += int(game['REB'])
        total_ast += int(game['AST'])

    count = len(last_10)
    avg_stats = {
        "pts": round(float(total_pts / count), 1) if count > 0 else 0.0,
        "reb": round(float(total_reb / count), 1) if count > 0 else 0.0,
        "ast": round(float(total_ast / count), 1) if count > 0 else 0.0
    }

    return {
        "id": int(player_id),
        "name": str(full_name),
        "position": str(position),
        "team_code": str(team_abbreviation),
        "team_name": str(team_full_name),
        "image": headshot_url,
        "averages": avg_stats,
        "last_10_games": recent_games
    }

# Team stats using nba api
def get_team_stats(team_name: str):
    # Lazy import
    from nba_api.stats.endpoints import leaguedashteamstats

    print(f"DEBUG: Fetching stats for opponent: {team_name}")
    
    try:
        # Using Advanced stats for Defense Ratings
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season='2025-26',
            measure_type_detailed_defense='Advanced'
        )
        df = stats.get_data_frames()[0]
        
        team_row = df[df['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
        
        if team_row.empty:
            # Try matching just the city or team nickname
            simple_name = team_name.split()[-1]
            team_row = df[df['TEAM_NAME'].str.contains(simple_name, case=False, na=False)]

        if not team_row.empty:
            data = team_row.iloc[0]
            
            return {
                "name": str(data['TEAM_NAME']),
                "def_rating": float(data['DEF_RATING']),
                "def_rank": int(data['DEF_RATING_RANK']),
                "pace": float(data['PACE']),
                "pace_rank": int(data['PACE_RANK'])
            }
        else:
            print(f"DEBUG: Could not find stats for team: {team_name}")

    except Exception as e:
        print(f"ERROR fetching team stats: {e}")
    
    return None


# Get odds with odds api
def get_odds_and_matchup(player_name: str):
    from datetime import datetime, timezone
    
    print(f"DEBUG: Finding odds for {player_name}...")
    
    # Check key inside the function to avoid global scope issues if env var changes
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("ERROR: Missing ODDS_API_KEY")
        return {"game_info": None, "props": []}
    
    # Get current time in UTC for filtering past games
    now_utc = datetime.now(timezone.utc)
    print(f"DEBUG: Current UTC time: {now_utc.isoformat()}")

    with httpx.Client(timeout=30.0) as client:
        try:
            odds_resp = client.get(
                "https://api.the-odds-api.com/v4/sports/basketball_nba/events",
                params={"apiKey": api_key, "regions": "us"}
            )
            odds_resp.raise_for_status()
            all_events = odds_resp.json()
        except Exception as e:
            print(f"ERROR fetching events: {e}")
            return {"game_info": None, "props": []}
        
        # Filter out past games - only include games that haven't started yet
        future_events = []
        for event in all_events:
            commence_time_str = event.get("commence_time", "")
            try:
                # commence_time is ISO 8601 format (e.g., "2026-02-02T00:00:00Z")
                commence_time = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
                if commence_time > now_utc:
                    future_events.append(event)
                else:
                    print(f"DEBUG: Skipping past game: {event.get('home_team')} vs {event.get('away_team')} ({commence_time_str})")
            except Exception as e:
                print(f"WARNING: Could not parse commence_time '{commence_time_str}': {e}")
                # Include event if we can't parse the time (to be safe)
                future_events.append(event)
        
        print(f"DEBUG: {len(future_events)} future games found out of {len(all_events)} total")
        
        found_props = []
        game_info = None

        # Limit to 5 future events to save API calls
        for event in future_events[:5]:
            game_id = event["id"]
            
            try:
                props_resp = client.get(
                    f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{game_id}/odds",
                    params={
                        "apiKey": api_key,
                        "regions": "us",
                        "markets": "player_points,player_assists,player_rebounds",
                        "oddsFormat": "american"
                    }
                )
                props_resp.raise_for_status()
                data = props_resp.json()
            except Exception as e:
                print(f"ERROR fetching props for game {game_id}: {e}")
                continue
            
            player_found_in_game = False
            
            if "bookmakers" in data:
                for bookie in data["bookmakers"]:
                    for market in bookie["markets"]:
                        for outcome in market["outcomes"]:
                            if player_name.lower() in outcome["description"].lower():
                                player_found_in_game = True
                                found_props.append({
                                    "book": str(bookie["title"]),
                                    "market": str(market["key"]),
                                    "line": float(outcome["point"]),
                                    "type": str(outcome["name"]),
                                    "odds": int(outcome["price"])
                                })
            
            if player_found_in_game:
                game_info = {
                    "home": str(event["home_team"]),
                    "away": str(event["away_team"]),
                    "start": str(event["commence_time"])
                }
                break  # Found the player's game, stop searching

        return {
            "game_info": game_info,
            "props": found_props
        }
