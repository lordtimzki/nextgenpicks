from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
from google import genai
from google.genai.errors import ClientError
import os
import json
import datetime
import uuid
from retrieve import get_player_data, get_team_stats, get_odds_and_matchup
from batch_analyze import batch_analyze, scheduled_refresh

# Initialize Firebase Admin
initialize_app()

@https_fn.on_request(secrets=["GOOGLE_API_KEY", "ODDS_API_KEY"], timeout_sec=120)
def analyze_player(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function to analyze a player with Personalization Context.
    Expects GET params: 'player_name' and optional 'uid'.
    """
    player_name = req.args.get('player_name')
    user_id = req.args.get('uid')

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
        matchup_display = "TBD"

        if odds_data.get("game_info"):
            game = odds_data["game_info"]
            player_team = player_data["team_name"]
            player_team_code = player_data["team_code"]

            if player_team.lower() in game["home"].lower():
                opponent_name = game["away"]
                matchup_display = f"{opponent_name.split()[-1][:3].upper()} @ {player_team_code}"
            else:
                opponent_name = game["home"]
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
                    "display": f"{prop['type']} {prop['line']} {market_name}",
                    "market": prop['market'],
                    "type": prop['type'],
                    "line": prop['line'],
                    "odds": prop['odds'],
                    "book": prop['book']
                })

        # FETCH USER PERSONAL MODEL
        db = firestore.client()
        personal_context_prompt = "Assign a Ranking Score (0.0 - 10.0) based on raw data edge."
        risk_tolerance = "Balanced"
        
        if user_id:
            user_ref = db.collection("users").document(user_id).collection("config").document("settings")
            user_doc = user_ref.get()
            if user_doc.exists:
                u = user_doc.to_dict()
                risk_tolerance = u.get('riskTolerance', 'Balanced')
                fav_stats = u.get('focusedStats', [])
                clicks = u.get('interactionHistory', {}) # Implicit context
                
                personal_context_prompt = f"""
                User Context Signals:
                - Risk Tolerance: {risk_tolerance} (Strictly penalize risky plays if Conservative)
                - Focused Stats: {", ".join(fav_stats)}
                - Interaction History: {player_name} has been clicked {clicks.get(player_name, 0)} times.
                
                TASK: Rank the best prop on a 0.0 to 10.0 scale. 
                If the user has high interaction with this player, give a slight 'interest boost' to the ranking.
                """

        # 5. Gemini Analysis (Updated for Ranking Score)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        client = genai.Client(api_key=google_api_key)
        
        prompt = f"""
        Act as a professional NBA handicapper using a Weighted Ranking System.

        **PLAYER:** {player_data['name']} | **REST:** {days_rest}
        **AVERAGES:** Pts: {player_data['averages']['pts']}, Reb: {player_data['averages']['reb']}, Ast: {player_data['averages']['ast']}
        **PROPS:** {json.dumps(formatted_props)}

        {personal_context_prompt}

        **OUTPUT FORMAT (JSON ONLY):**
        {{
          "ranking_score": 8.5,
          "recommended_direction": "Over",
          "is_fade": false,
          "analysis": "Brief logic here"
        }}
        """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.2}
        )
        ai_res = json.loads(response.text)

        # 6. Transform to PlayerCardData (Updated for Win/Loss Tracking & Interaction)
        grouped_props = {}
        if formatted_props:
            for p in formatted_props:
                stat_name = p['market'].replace('player_', '').replace('_', ' ').title().replace('Points', 'Pts').replace('Assists', 'Ast').replace('Rebounds', 'Reb')
                key = f"{p['market']}_{p['line']}"
                if key not in grouped_props:
                    grouped_props[key] = {
                        "id": str(uuid.uuid4()),
                        "statName": stat_name,
                        "line": p['line'],
                        "overOdds": 0,
                        "underOdds": 0
                    }
                if p['type'].lower() == 'over': grouped_props[key]['overOdds'] = p['odds']
                elif p['type'].lower() == 'under': grouped_props[key]['underOdds'] = p['odds']

        # Determine trending based on new 0.0 - 10.0 score
        final_score = ai_res.get("ranking_score", 5.0)
        trending = "up"
        if final_score >= 8.0: trending = "hot"
        elif final_score <= 4.0: trending = "fade"

        ios_card_data = {
            "id": player_data["id"],
            "name": player_data["name"],
            "teamAbbr": player_data["team_code"],
            "position": player_data.get("position", "N/A"),
            "imageName": player_data["image"],
            "props": list(grouped_props.values()),
            "opponent": matchup_display,
            "gameTime": "Tonight",
            "trending": trending,
            "rankingScore": final_score, # 0.0 - 10.0
            "isFade": ai_res.get("is_fade", False),
            "ai_analysis": ai_res.get("analysis", ""),
            "recommendedDirection": ai_res.get("recommended_direction", "Over"),
            "last_updated": datetime.datetime.now().isoformat()
        }
        
        # 7. Write to 'props' collection for App consumption
        db.collection("props").document(str(player_data["id"])).set(ios_card_data)

        return https_fn.Response(json.dumps({"status": "success", "data": ios_card_data}), mimetype='application/json')

    except Exception as e:
        return https_fn.Response(f"Internal Error: {str(e)}", status=500)