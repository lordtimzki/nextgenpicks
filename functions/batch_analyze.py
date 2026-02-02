"""
Batch Analyze Cloud Function - Dynamic Version
Fetches ALL player props from upcoming NBA games and analyzes them.
No hardcoded player list - gets whatever the odds API returns.
"""

from firebase_functions import https_fn, scheduler_fn
from firebase_admin import firestore
from google import genai
import httpx
import os
import json
import datetime
import uuid
from datetime import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Note: Firebase is initialized in main.py which imports this module


def get_all_upcoming_props(odds_api_key: str) -> dict:
    """
    Fetch ALL player props from ALL upcoming NBA games.
    Returns: { "players": [{ player_name, team, props: [...], game_info }, ...] }
    """
    print("=== Fetching ALL upcoming game props ===")
    
    now_utc = datetime.datetime.now(timezone.utc)
    
    with httpx.Client(timeout=60.0) as client:
        # 1. Get all upcoming NBA events
        try:
            events_resp = client.get(
                "https://api.the-odds-api.com/v4/sports/basketball_nba/events",
                params={"apiKey": odds_api_key, "regions": "us"}
            )
            events_resp.raise_for_status()
            all_events = events_resp.json()
        except Exception as e:
            print(f"ERROR fetching events: {e}")
            return {"players": [], "events": []}
        
        # 2. Filter to games that are upcoming OR currently live (started within last 24 hours)
        # This ensures we capture live props and upcoming games
        relevant_events = []
        twenty_four_hours_ago = now_utc - datetime.timedelta(hours=24)
        
        for event in all_events:
            commence_time_str = event.get("commence_time", "")
            try:
                commence_time = datetime.datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
                # Include if: upcoming OR started within last 24 hours (could be live)
                if commence_time > twenty_four_hours_ago:
                    relevant_events.append(event)
                    status = "🔴 LIVE" if commence_time <= now_utc else "📅 Upcoming"
                    print(f"{status}: {event['home_team']} vs {event['away_team']} at {commence_time_str}")
                else:
                    print(f"⏭️ Skipping old game: {event['home_team']} vs {event['away_team']}")
            except Exception as e:
                print(f"WARNING: Could not parse time '{commence_time_str}': {e}")
                relevant_events.append(event)  # Include if can't parse
        
        print(f"\n📊 Found {len(relevant_events)} relevant games (live + upcoming)\n")
        
        # 3. Fetch player props for each game - collect ALL unique players
        all_players = {}  # player_name -> { props: [...], game_info: {...} }
        
        for event in relevant_events:
            game_id = event["id"]
            game_info = {
                "home": event["home_team"],
                "away": event["away_team"],
                "start": event["commence_time"]
            }
            
            try:
                props_resp = client.get(
                    f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{game_id}/odds",
                    params={
                        "apiKey": odds_api_key,
                        "regions": "us",
                        "markets": "player_points,player_assists,player_rebounds",
                        "oddsFormat": "american"
                    }
                )
                props_resp.raise_for_status()
                data = props_resp.json()
            except Exception as e:
                print(f"ERROR fetching props for {event['home_team']} vs {event['away_team']}: {e}")
                continue
            
            # Log response for debugging
            bookmakers_count = len(data.get("bookmakers", []))
            print(f"   📖 {event['home_team']} vs {event['away_team']}: {bookmakers_count} bookmakers with odds")
            
            # Extract all players from the props
            if "bookmakers" in data:
                for bookie in data["bookmakers"]:
                    for market in bookie["markets"]:
                        for outcome in market["outcomes"]:
                            player_name = outcome["description"]
                            
                            # Initialize player entry if not exists
                            if player_name not in all_players:
                                all_players[player_name] = {
                                    "name": player_name,
                                    "game_info": game_info,
                                    "props": []
                                }
                            
                            # Add this prop
                            all_players[player_name]["props"].append({
                                "book": bookie["title"],
                                "market": market["key"],
                                "line": float(outcome["point"]),
                                "type": outcome["name"],
                                "odds": int(outcome["price"])
                            })
        
        print(f"🏀 Found props for {len(all_players)} unique players\n")
        
        return {
            "players": list(all_players.values()),
            "events": relevant_events
        }


def get_player_stats_quick(player_name: str) -> dict | None:
    """Get basic player stats from NBA API."""
    try:
        from nba_api.stats.static import players, teams
        from nba_api.stats.endpoints import playergamelog, commonplayerinfo
        
        nba_players = players.find_players_by_full_name(player_name)
        if not nba_players:
            return None
        
        player = nba_players[0]
        player_id = player['id']
        
        # Get position
        position = "N/A"
        try:
            player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            info = player_info.get_normalized_dict()['CommonPlayerInfo']
            if info:
                position = str(info[0].get('POSITION', 'N/A'))
        except:
            pass
        
        # Get recent stats
        try:
            log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
            games = log.get_normalized_dict()['PlayerGameLog'][:5]  # Last 5 games
            
            if games:
                team_code = str(games[0]['MATCHUP'].split(" ")[0])
                nba_team = teams.find_team_by_abbreviation(team_code)
                team_name = nba_team['full_name'] if nba_team else "Unknown"
                
                avg_pts = sum(g['PTS'] for g in games) / len(games)
                avg_reb = sum(g['REB'] for g in games) / len(games)
                avg_ast = sum(g['AST'] for g in games) / len(games)
                
                return {
                    "id": int(player_id),
                    "name": player['full_name'],
                    "position": position,
                    "team_code": team_code,
                    "team_name": team_name,
                    "image": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
                    "averages": {
                        "pts": round(avg_pts, 1),
                        "reb": round(avg_reb, 1),
                        "ast": round(avg_ast, 1)
                    }
                }
        except Exception as e:
            print(f"Could not get game log for {player_name}: {e}")
        
        # Minimal fallback
        return {
            "id": int(player_id),
            "name": player['full_name'],
            "position": position,
            "team_code": "UNK",
            "team_name": "Unknown",
            "image": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
            "averages": {"pts": 0, "reb": 0, "ast": 0}
        }
    except Exception as e:
        print(f"Error getting stats for {player_name}: {e}")
        return None


@https_fn.on_request(secrets=["GOOGLE_API_KEY", "ODDS_API_KEY"], timeout_sec=540, memory=1024)
def batch_analyze(req: https_fn.Request) -> https_fn.Response:
    """
    Dynamically fetch ALL player props for upcoming NBA games.
    No hardcoded player list - gets whatever the odds API returns.
    """
    
    print("\n" + "="*60)
    print("=== DYNAMIC BATCH ANALYSIS - ALL UPCOMING GAME PROPS ===")
    print("="*60 + "\n")
    
    odds_api_key = os.getenv("ODDS_API_KEY")
    if not odds_api_key:
        return https_fn.Response(json.dumps({
            "status": "error",
            "message": "ODDS_API_KEY not configured"
        }), status=500, mimetype='application/json')
    
    # 1. Get ALL props from upcoming games
    props_data = get_all_upcoming_props(odds_api_key)
    
    if not props_data["players"]:
        return https_fn.Response(json.dumps({
            "status": "error",
            "message": "No player props found for upcoming games",
            "events_checked": len(props_data.get("events", []))
        }), status=404, mimetype='application/json')
    
    print(f"Processing {len(props_data['players'])} players with props...\n")
    
    # 2. Enrich with NBA stats (parallel)
    enriched_players = []
    
    def enrich_player(player_props):
        stats = get_player_stats_quick(player_props["name"])
        if stats:
            return {
                "player_stats": stats,
                "props": player_props["props"],
                "game_info": player_props["game_info"]
            }
        return None
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(enrich_player, p): p["name"] for p in props_data["players"]}
        for future in as_completed(futures):
            player_name = futures[future]
            try:
                result = future.result()
                if result:
                    enriched_players.append(result)
                    print(f"✓ Enriched {player_name}")
                else:
                    print(f"✗ Could not enrich {player_name}")
            except Exception as e:
                print(f"✗ Error enriching {player_name}: {e}")
    
    print(f"\n📊 Enriched {len(enriched_players)} players with NBA stats\n")
    
    # 3. Single Gemini call for detailed analysis
    ai_by_name = {}  # name -> {trending, analysis}
    google_api_key = os.getenv("GOOGLE_API_KEY")
    
    if google_api_key and len(enriched_players) > 0:
        try:
            # Build detailed summary for Gemini with opponent info
            players_for_ai = enriched_players[:25]  # Limit for token budget
            summaries = []
            for ep in players_for_ai:
                ps = ep["player_stats"]
                game = ep["game_info"]
                
                # Determine opponent
                if ps["team_name"].lower() in game["home"].lower():
                    opp = game["away"]
                    home_away = "away"
                else:
                    opp = game["home"]
                    home_away = "home"
                
                summaries.append({
                    "name": ps["name"],
                    "team": ps["team_code"],
                    "position": ps["position"],
                    "averages": ps["averages"],
                    "opponent": opp,
                    "home_away": home_away,
                    "props": [f"{p['type']} {p['line']} {p['market'].replace('player_', '')}" for p in ep["props"][:4]]
                })
            
            client = genai.Client(api_key=google_api_key)
            prompt = f"""
            You are an expert NBA handicapper providing prop bet analysis.
            
            **PLAYERS TO ANALYZE:** {len(summaries)}
            
            **DATA:**
            {json.dumps(summaries, indent=2)}
            
            **FOR EACH PLAYER PROVIDE:**
            1. "trending": "hot" (strong bet) or "up" (standard play)
            2. "analysis": A specific 1-2 sentence analysis that MUST include:
               - The opponent they're facing (e.g., "vs Lakers")
               - Why this matchup matters (e.g., "Lakers rank 28th in perimeter D")
               - A concrete recommendation on the prop
            
            **EXAMPLE GOOD ANALYSIS:**
            "Facing the Lakers at home who allow 4th most PPG to guards. Look at Over 28.5 pts."
            
            **EXAMPLE BAD ANALYSIS (TOO GENERIC):**
            "Luka is a triple-double threat nightly."
            
            **OUTPUT FORMAT (VALID JSON):**
            {{
                "players": [
                    {{
                        "name": "Player Name",
                        "trending": "hot",
                        "analysis": "Facing the Celtics who rank 3rd in defensive rating. Expect a tough night, lean Under 24.5 pts."
                    }}
                ]
            }}
            """
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0.4}
            )
            ai_results = json.loads(response.text)
            print("✓ Gemini analysis complete")
            
            for p in ai_results.get("players", []):
                ai_by_name[p["name"].lower()] = {
                    "trending": p.get("trending", "up"),
                    "analysis": p.get("analysis", "")
                }
        except Exception as e:
            print(f"Gemini error (continuing without AI): {e}")
    
    # 4. Clear old props and write new data to Firestore
    db = firestore.client()
    
    # Delete all existing props first (fresh start each run)
    print("🗑️  Clearing old props collection...")
    props_ref = db.collection("props")
    old_docs = props_ref.stream()
    deleted_count = 0
    delete_batch = db.batch()
    
    for doc in old_docs:
        delete_batch.delete(doc.reference)
        deleted_count += 1
        # Commit in chunks to avoid batch limits
        if deleted_count % 400 == 0:
            delete_batch.commit()
            delete_batch = db.batch()
    
    if deleted_count % 400 != 0:
        delete_batch.commit()
    
    print(f"🗑️  Deleted {deleted_count} old documents")
    
    # Now write new data
    batch = db.batch()
    written_count = 0
    
    for ep in enriched_players:
        ps = ep["player_stats"]
        game = ep["game_info"]
        
        # Determine opponent
        if ps["team_name"].lower() in game["home"].lower():
            opponent = game["away"]
        else:
            opponent = game["home"]
        
        # Get AI analysis or default
        player_ai = ai_by_name.get(ps["name"].lower(), {})
        trending = player_ai.get("trending", "up") if isinstance(player_ai, dict) else player_ai
        analysis = player_ai.get("analysis", "") if isinstance(player_ai, dict) else ""
        if trending not in ["up", "hot"]:
            trending = "up"
        
        # Group props by market+line
        grouped_props = {}
        for p in ep["props"]:
            stat_name = p['market'].replace('player_', '').replace('_', ' ').title()
            stat_name = stat_name.replace('Points', 'Pts').replace('Assists', 'Ast').replace('Rebounds', 'Reb')
            
            key = f"{p['market']}_{p['line']}"
            if key not in grouped_props:
                grouped_props[key] = {
                    "id": str(uuid.uuid4()),
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
        
        # Skip players with no props - they shouldn't be in the feed
        if not ios_props:
            print(f"⏭️ Skipping {ps['name']} - no props available")
            continue
        
        # Build card data
        ios_card = {
            "id": ps["id"],
            "name": ps["name"],
            "teamAbbr": ps["team_code"],
            "position": ps["position"],
            "imageName": ps["image"],
            "props": ios_props,
            "opponent": opponent,
            "gameTime": "Tonight",  # All are upcoming
            "trending": trending,
            "ai_analysis": analysis,  # Detailed analysis with opponent context
            "last_updated": datetime.datetime.now().isoformat()
        }
        
        doc_ref = db.collection("props").document(str(ps["id"]))
        batch.set(doc_ref, ios_card)
        written_count += 1
        
        # Firestore batch limit is 500, commit in chunks
        if written_count % 400 == 0:
            batch.commit()
            batch = db.batch()
    
    # Final commit
    if written_count % 400 != 0:
        batch.commit()
    
    print(f"\n{'='*60}")
    print(f"=== COMPLETE: Wrote {written_count} players to Firestore ===")
    print("="*60 + "\n")
    
    return https_fn.Response(json.dumps({
        "status": "success",
        "message": f"Dynamically fetched and analyzed {written_count} players",
        "players_written": written_count,
        "games_checked": len(props_data.get("events", []))
    }), mimetype='application/json')


def run_batch_analysis() -> dict:
    """
    Core batch analysis logic - shared by HTTP and scheduled triggers.
    Returns a dict with status and results.
    """
    import os
    
    odds_api_key = os.getenv("ODDS_API_KEY")
    if not odds_api_key:
        return {"status": "error", "message": "ODDS_API_KEY not configured"}
    
    # 1. Get ALL props from upcoming games
    props_data = get_all_upcoming_props(odds_api_key)
    
    if not props_data["players"]:
        # Still clear old data even if no new props
        db = firestore.client()
        props_ref = db.collection("props")
        old_docs = props_ref.stream()
        deleted_count = 0
        delete_batch = db.batch()
        for doc in old_docs:
            delete_batch.delete(doc.reference)
            deleted_count += 1
            if deleted_count % 400 == 0:
                delete_batch.commit()
                delete_batch = db.batch()
        if deleted_count % 400 != 0:
            delete_batch.commit()
        
        return {
            "status": "no_props",
            "message": "No player props found for upcoming games",
            "events_checked": len(props_data.get("events", [])),
            "old_docs_deleted": deleted_count
        }
    
    print(f"Processing {len(props_data['players'])} players with props...\n")
    
    # 2. Enrich with NBA stats (parallel)
    enriched_players = []
    
    def enrich_player(player_props):
        stats = get_player_stats_quick(player_props["name"])
        if stats:
            return {
                "player_stats": stats,
                "props": player_props["props"],
                "game_info": player_props["game_info"]
            }
        return None
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(enrich_player, p): p["name"] for p in props_data["players"]}
        for future in as_completed(futures):
            player_name = futures[future]
            try:
                result = future.result()
                if result:
                    enriched_players.append(result)
            except Exception:
                pass
    
    # 3. Gemini analysis
    ai_by_name = {}
    google_api_key = os.getenv("GOOGLE_API_KEY")
    
    if google_api_key and enriched_players:
        try:
            players_for_ai = enriched_players[:25]
            summaries = []
            for ep in players_for_ai:
                ps = ep["player_stats"]
                game = ep["game_info"]
                opp = game["away"] if ps["team_name"].lower() in game["home"].lower() else game["home"]
                home_away = "away" if ps["team_name"].lower() in game["home"].lower() else "home"
                summaries.append({
                    "name": ps["name"], "team": ps["team_code"], "position": ps["position"],
                    "averages": ps["averages"], "opponent": opp, "home_away": home_away,
                    "props": [f"{p['type']} {p['line']} {p['market'].replace('player_', '')}" for p in ep["props"][:4]]
                })
            
            client = genai.Client(api_key=google_api_key)
            prompt = f"""You are an expert NBA handicapper. Analyze these {len(summaries)} players.
For each: "trending" (hot/up) and "analysis" (1-2 sentences with opponent + recommendation).
Data: {json.dumps(summaries)}
Return JSON: {{"players": [{{"name": "...", "trending": "hot", "analysis": "Facing X who rank..."}}]}}"""
            
            response = client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0.4}
            )
            for p in json.loads(response.text).get("players", []):
                ai_by_name[p["name"].lower()] = {"trending": p.get("trending", "up"), "analysis": p.get("analysis", "")}
        except Exception as e:
            print(f"Gemini error: {e}")
    
    # 4. Clear and write to Firestore
    db = firestore.client()
    props_ref = db.collection("props")
    old_docs = props_ref.stream()
    deleted_count = 0
    delete_batch = db.batch()
    for doc in old_docs:
        delete_batch.delete(doc.reference)
        deleted_count += 1
        if deleted_count % 400 == 0:
            delete_batch.commit()
            delete_batch = db.batch()
    if deleted_count % 400 != 0:
        delete_batch.commit()
    
    batch = db.batch()
    written_count = 0
    
    for ep in enriched_players:
        ps = ep["player_stats"]
        game = ep["game_info"]
        opponent = game["away"] if ps["team_name"].lower() in game["home"].lower() else game["home"]
        player_ai = ai_by_name.get(ps["name"].lower(), {})
        trending = player_ai.get("trending", "up") if isinstance(player_ai, dict) else "up"
        analysis = player_ai.get("analysis", "") if isinstance(player_ai, dict) else ""
        
        # Group props
        grouped_props = {}
        for p in ep["props"]:
            stat_name = p['market'].replace('player_', '').replace('_', ' ').title()
            stat_name = stat_name.replace('Points', 'Pts').replace('Assists', 'Ast').replace('Rebounds', 'Reb')
            key = f"{p['market']}_{p['line']}"
            if key not in grouped_props:
                grouped_props[key] = {"id": str(uuid.uuid4()), "statName": stat_name, "line": p['line'], "overOdds": 0, "underOdds": 0}
            if p['type'].lower() == 'over':
                grouped_props[key]['overOdds'] = p['odds']
            elif p['type'].lower() == 'under':
                grouped_props[key]['underOdds'] = p['odds']
        
        ios_props = list(grouped_props.values())
        if not ios_props:
            continue
        
        ios_card = {
            "id": ps["id"], "name": ps["name"], "teamAbbr": ps["team_code"],
            "position": ps["position"], "imageName": ps["image"], "props": ios_props,
            "opponent": opponent, "gameTime": "Tonight", "trending": trending,
            "ai_analysis": analysis, "last_updated": datetime.datetime.now().isoformat()
        }
        
        batch.set(db.collection("props").document(str(ps["id"])), ios_card)
        written_count += 1
        if written_count % 400 == 0:
            batch.commit()
            batch = db.batch()
    
    if written_count % 400 != 0:
        batch.commit()
    
    return {"status": "success", "players_written": written_count, "games_checked": len(props_data.get("events", []))}


# ============================================================
# SCHEDULED FUNCTION - Runs automatically via Cloud Scheduler
# ============================================================
# Schedule: "0 9,18 * * *" = 9am and 6pm every day (UTC)
# Adjust timezone as needed with timezone parameter

@scheduler_fn.on_schedule(
    schedule="0 9,18 * * *",  # 9am and 6pm UTC daily (adjust as needed)
    timezone=scheduler_fn.Timezone("America/Los_Angeles"),  # PST
    secrets=["GOOGLE_API_KEY", "ODDS_API_KEY"],
    timeout_sec=540,
    memory=1024
)
def scheduled_refresh(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Automatically refresh all player props twice daily.
    Runs at 9am and 6pm Pacific Time.
    """
    print("\n" + "="*60)
    print("=== SCHEDULED REFRESH - AUTO-TRIGGERED ===")
    print(f"=== Time: {datetime.datetime.now().isoformat()} ===")
    print("="*60 + "\n")
    
    result = run_batch_analysis()
    
    print(f"\n=== SCHEDULED REFRESH COMPLETE ===")
    print(f"Result: {json.dumps(result)}")

