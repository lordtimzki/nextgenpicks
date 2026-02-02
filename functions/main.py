from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
from google import genai
from google.genai.errors import ClientError
import os
import json
import datetime
from retrieve import get_player_data, get_team_stats, get_odds_and_matchup

# Initialize Firebase Admin
initialize_app()

@https_fn.on_request()
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
        
        # 2. Betting Odds
        odds_data = get_odds_and_matchup(player_data["name"])
        
        # 3. Opponent Analysis
        opponent_name = "Unknown"
        opponent_stats = None
        
        if odds_data.get("game_info"):
            game = odds_data["game_info"]
            player_team = player_data["team_name"]
            
            # Determine opponent
            if player_team.lower() in game["home"].lower():
                opponent_name = game["away"]
            else:
                opponent_name = game["home"]
            
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

        # 5. Gemini Analysis
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
             return https_fn.Response("Server configuration error: GOOGLE_API_KEY missing", status=500)

        client = genai.Client(api_key=google_api_key)
        
        prompt = f"""
        Act as a professional NBA handicapper analyzing ALL available prop bets for this player.

        **PLAYER:** {player_data['name']} ({player_data['team_code']})
        **OPPONENT:** {opponent_name}
        **DAYS REST:** {days_rest}

        **PLAYER AVERAGES (Last 10 Games):**
        - Points: {player_data['averages']['pts']}
        - Rebounds: {player_data['averages']['reb']}
        - Assists: {player_data['averages']['ast']}

        **OPPONENT DEFENSIVE PROFILE:**
        {f"- Defense Rating: {opponent_stats['def_rating']} (Rank #{opponent_stats['def_rank']})" if opponent_stats else "- Defense: Not Available"}
        {f"- Pace: {opponent_stats['pace']} (Rank #{opponent_stats['pace_rank']})" if opponent_stats else "- Pace: Not Available"}
        
        **RECENT GAME LOG (Last 5 Games):**
        {json.dumps(player_data['last_10_games'][:5], indent=2)}

        **AVAILABLE PROP BETS TO ANALYZE:**
        {json.dumps(formatted_props, indent=2) if formatted_props else "No props available"}

        **YOUR TASK:**
        1. Analyze EACH available prop bet individually
        2. Rank all props by value/edge
        3. Identify your TOP RECOMMENDED play

        **OUTPUT FORMAT (VALID JSON ONLY):**
        {{
        "top_pick": {{
            "prop": "Over 25.5 Points",
            "action": "BET",
            "confidence": "68%",
            "reasoning": "Explanation here"
        }},
        "all_props_ranked": [
            {{
            "prop": "Over 25.5 Points",
            "action": "BET",
            "confidence": "68%",
            "value_score": "8/10",
            "analysis": "Analysis here"
            }}
        ],
        "summary": "Overall advice"
        }}
        """
        
        ai_analysis = None
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp", # Using a known model or consistent with backend
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            )
            ai_analysis = json.loads(response.text)
        except Exception as e:
            ai_analysis = {"error": str(e)}

        # 6. Construct Final Result
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
            "ai_analysis": ai_analysis,
            "last_updated": datetime.datetime.now().isoformat()
        }

        # 7. Write to Firestore
        db = firestore.client()
        # Use player ID as document ID for easy lookup
        doc_ref = db.collection("players").document(str(player_data["id"]))
        doc_ref.set(result)

        return https_fn.Response(json.dumps(result), mimetype='application/json')

    except Exception as e:
        return https_fn.Response(f"Internal Error: {str(e)}", status=500)
