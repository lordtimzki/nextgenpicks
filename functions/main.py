from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore
import json
import datetime

# Initialize Firebase Admin for Firestore access
initialize_app()

@https_fn.on_request(timeout_sec=60)
def analyze_player(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP Cloud Function: The Personalization Bridge.
    Calculates weighted scores based on Focused Stats and Favorite Teams.
    """
    player_name = req.args.get('player_name')
    user_id = req.args.get('uid')
    
    if not player_name or not user_id:
        return https_fn.Response("Error: Missing 'player_name' or 'uid' parameter.", status=400)

    try:
        db = firestore.client()
        
        # 1. FETCH USER CONTEXT (Explicit Context)
        # Pulls the saved settings
        user_doc = db.collection("users").document(user_id).collection("config").document("settings").get()
        user_settings = user_doc.to_dict() if user_doc.exists else {}

        # 2. FIND GLOBAL PROPS
        # Query the 'props' collection that the scraper updates automatically
        props_query = db.collection("props").where("name", "==", player_name).stream()
        
        personalized_count = 0

        # Mapping UI Full Names to stat names
        stat_map = {
            "Points": "Pts", 
            "Rebounds": "Reb", 
            "Assists": "Ast", 
            "3-Pointers Made": "3PM",
            "Pts + Rebs + Asts": "PRA"
        }

        for doc in props_query:
            data = doc.to_dict()
            
            # The baseline 0-10 score calculated by the scraper math
            global_score = data.get("rankingScore", 5.0) 
            
            # 3. APPLY PERSONALIZATION WEIGHTS (Weighted Multiplier Logic)
            multiplier = 1.0
            
            # Team Loyalty Bonus: 20% boost if player is on your favorite team list
            fav_teams = user_settings.get('favoriteTeams', [])
            if data.get("teamAbbr") in fav_teams:
                multiplier += 0.2
                
            # Strategic Interest Bonus: 30% boost if you focus on this specific stat category
            focused_stats = user_settings.get('focusedStats', [])
            current_stat = data.get("statName")
            
            for full_name, short_name in stat_map.items():
                if full_name in focused_stats and current_stat == short_name:
                    multiplier += 0.3

            # Calculate personalized score and clamp it to 0.0 - 10.0 scale
            final_score = min(max(round(global_score * multiplier, 1), 0.0), 10.0)

            # 4. PREPARE PERSONALIZED DATA
            # Keep all original scraper data, but swap in the personalized score and trend
            data["rankingScore"] = final_score
            data["trending"] = "hot" if final_score >= 8.5 else "up"
            data["personalizedFor"] = user_id
            # Standard Zulu format for Swift compatibility
            data["lastPersonalized"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

            # 5. WRITE TO USER SUBCOLLECTION
            # Path: users/{uid}/personalizedProps/{docId}
            # This ensures users's feed doesn't affect anyone else
            user_props_ref = db.collection("users").document(user_id).collection("personalizedProps")
            user_props_ref.document(doc.id).set(data)
            personalized_count += 1

        if personalized_count == 0:
            return https_fn.Response(f"No props found for {player_name} in global feed.", status=404)

        return https_fn.Response(json.dumps({
            "status": "success",
            "message": f"Personalized {personalized_count} props for {user_id}",
            "location": f"users/{user_id}/personalizedProps"
        }), mimetype='application/json')

    except Exception as e:
        print(f"CRITICAL ERROR in main.py: {str(e)}")
        return https_fn.Response(f"Internal Server Error: {str(e)}", status=500)