from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import json
import datetime
import uuid
from retrieve import get_player_data, get_team_stats
from batch_analyze import batch_analyze, scheduled_refresh  # Import both for Firebase discovery

# Initialize Firebase Admin
initialize_app()

@https_fn.on_request(timeout_sec=120)
def analyze_player(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to analyze a player.
    Expects a GET request with query parameter 'player_name', e.g., ?player_name=LeBron+James
    """
    player_name = req.args.get('player_name')
    if not player_name:
        return https_fn.Response("Missing 'player_name' query parameter", status=400)

    try:
        # 1. Player Stats
        player_data = get_player_data(player_name)
        if not player_data:
            return https_fn.Response(f"Player '{player_name}' not found", status=404)
        
        # 2. Betting Odds (Odds API removed - legacy endpoint)
        odds_data = {"game_info": None, "props": []}

        # 3. Opponent Analysis
        opponent_name = "Unknown"
        opponent_stats = None
        matchup_display = "TBD"

        if odds_data.get("game_info"):
            game = odds_data["game_info"]
            player_team = player_data["team_name"]
            player_team_code = player_data["team_code"]

            # Determine opponent and matchup display
            if player_team.lower() in game["home"].lower():
                opponent_name = game["away"]
                # Player is home team, show "AWAY @ HOME"
                matchup_display = f"{opponent_name.split()[-1][:3].upper()} @ {player_team_code}"
            else:
                opponent_name = game["home"]
                # Player is away team, show "AWAY @ HOME"
                matchup_display = f"{player_team_code} @ {opponent_name.split()[-1][:3].upper()}"

            opponent_stats = get_team_stats(opponent_name)
        
        # 4. Days Rest Calculation
        days_rest = "Unknown"
        if player_data.get("last_10_games"):
            last_game_date_str = player_data["last_10_games"][0]["date"]
            for fmt in ["%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]:
                try:
                    last_game_date = datetime.datetime.strptime(last_game_date_str, fmt)
                    days_rest = (datetime.datetime.now() - last_game_date).days
                    break
                except ValueError:
                    continue
        
        # Format props
        formatted_props = []
        if odds_data.get('props'):
            for prop in odds_data['props']:
                market_name = prop['market'].replace('player_', '').replace('_', ' ').title()
                formatted_props.append({
                    "display": f"{prop['type']} {prop['line']} {market_name} at {prop['odds']:+d} ({prop['book']})",
                    "market": prop['market'],
                    "type": prop['type'],
                    "line": prop['line'],
                    "odds": prop['odds'],
                    "book": prop['book']
                })

        # 5. Construct Final Result (Legacy structure for reference/debugging)
        result = {
            "player": {
                "name": player_data["name"],
                "id": player_data["id"],
                "team": player_data["team_name"],
                "team_code": player_data["team_code"],
                "image": player_data["image"],
                "averages": player_data["averages"],
                "recent_games": player_data["last_10_games"][:5]
            },
            "matchup": {
                "opponent": opponent_name,
                "opponent_stats": opponent_stats,
                "game_info": odds_data.get("game_info"),
                "days_rest": days_rest
            },
            "props": {
                "available": formatted_props,
                "count": len(formatted_props)
            },
            "last_updated": datetime.datetime.now().isoformat()
        }

        # 7. Write to Firestore 'players' (Legacy)
        db = firestore.client()
        doc_ref = db.collection("players").document(str(player_data["id"]))
        doc_ref.set(result)

        # 8. Transform to PlayerCardData for iOS App and write to 'props' collection
        # Group props by market+line to form PlayerProp objects
        # Map: "market_line" -> {statName, line, over, under}
        grouped_props = {}
        
        if formatted_props:
            for p in formatted_props:
                # p has: market, type (Over/Under), line, odds, book
                # statName from market (e.g., player_points -> Points)
                stat_name = p['market'].replace('player_', '').replace('_', ' ').title().replace('Points', 'Pts').replace('Assists', 'Ast').replace('Rebounds', 'Reb')
                
                key = f"{p['market']}_{p['line']}"
                if key not in grouped_props:
                    grouped_props[key] = {
                        "id": str(uuid.uuid4()), # Generate valid UUID for Swift Codable
                        "statName": stat_name,
                        "line": p['line'],
                        "overOdds": 0,
                        "underOdds": 0
                    }
                
                if p['type'].lower() == 'over':
                    grouped_props[key]['overOdds'] = p['odds']
                elif p['type'].lower() == 'under':
                    grouped_props[key]['underOdds'] = p['odds']
        
        ios_props = list(grouped_props.values())
        
        trending = "up"

        # Game Start Time
        game_time = "Scheduled"
        if odds_data.get("game_info"):
             # Parse and format if needed, or just say 'Tonight'
             # For now, simplistic mapping.
             game_time = "Tonight" 

        ios_card_data = {
            "id": player_data["id"],
            "name": player_data["name"],
            "teamAbbr": player_data["team_code"],
            "position": player_data.get("position", "N/A"),  # Use actual position from NBA API
            "imageName": player_data["image"], # Sends URL, App needs to handle it or we use placeholder
            "props": ios_props,
            "opponent": matchup_display,  # Full matchup like "LAL @ BKN"
            "gameTime": game_time,
            "trending": trending,
            "last_updated": datetime.datetime.now().isoformat()
        }
        
        # Write to 'props' collection (which FirebaseService queries)
        # Using player_id as doc ID to avoid duplicates
        db.collection("props").document(str(player_data["id"])).set(ios_card_data)

        return https_fn.Response(json.dumps({
            "status": "success",
            "message": "Player analyzed and saved to Firestore",
            "player_id": player_data["id"],
            "data": ios_card_data
        }), mimetype='application/json')


    except Exception as e:
        return https_fn.Response(f"Internal Error: {str(e)}", status=500)
