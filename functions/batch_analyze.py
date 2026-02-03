"""
Batch Analyze Cloud Function - Underdog Fantasy + ESPN Version
Fetches player props from Underdog Fantasy (free API, no auth required)
Uses ESPN for game schedules
Analyzes with Gemini AI
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


def fetch_json_httpx(url: str, headers: dict = None) -> tuple:
    """Fetch JSON using httpx (available in Cloud Functions)."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=default_headers)
            if resp.status_code == 200:
                return resp.status_code, resp.json()
            return resp.status_code, None
    except Exception as e:
        print(f"Fetch error for {url}: {e}")
        return None, None


def get_underdog_nba_props() -> dict:
    """
    Fetch all NBA player props from Underdog Fantasy.
    Returns structured data with players and their props.
    """
    print("=== Fetching Underdog Fantasy Props ===")

    status, data = fetch_json_httpx(
        "https://api.underdogfantasy.com/v1/over_under_lines")

    if status != 200 or not data:
        print(f"ERROR: Failed to fetch Underdog data (status: {status})")
        return {"players": [], "games": []}

    # Extract all data
    players_raw = data.get("players", [])
    appearances = data.get("appearances", [])
    lines = data.get("over_under_lines", [])
    games = data.get("games", [])

    print(f"  Total players: {len(players_raw)}")
    print(f"  Total lines: {len(lines)}")

    # Filter to NBA only
    nba_players = {
        p["id"]: p for p in players_raw if p.get("sport_id") == "NBA"}
    print(f"  NBA players: {len(nba_players)}")

    # Create appearance -> player mapping
    appearance_to_player = {}
    appearance_to_match = {}
    appearance_to_team_id = {}
    for app in appearances:
        player_id = app.get("player_id")
        if player_id in nba_players:
            appearance_to_player[app["id"]] = player_id
            appearance_to_match[app["id"]] = app.get("match_id")
            appearance_to_team_id[app["id"]] = app.get("team_id", "")

    # Create game lookup
    games_by_id = {g["id"]: g for g in games}

    # Build team_id -> abbreviation mapping from games
    team_id_to_abbr = {}
    for game in games:
        abbr_title = game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away_abbr, home_abbr = abbr_title.split(" @ ")
            away_team_id = game.get("away_team_id")
            home_team_id = game.get("home_team_id")
            if away_team_id:
                team_id_to_abbr[away_team_id] = away_abbr
            if home_team_id:
                team_id_to_abbr[home_team_id] = home_abbr

    # Group lines by player
    players_with_props = {}

    for line in lines:
        if line.get("status") != "active":
            continue

        ou = line.get("over_under", {})
        app_stat = ou.get("appearance_stat", {})
        app_id = app_stat.get("appearance_id", "")

        if app_id not in appearance_to_player:
            continue

        player_id = appearance_to_player[app_id]
        player = nba_players[player_id]
        match_id = appearance_to_match.get(app_id)
        team_id = appearance_to_team_id.get(app_id, "")
        game = games_by_id.get(match_id, {})

        if player_id not in players_with_props:
            players_with_props[player_id] = {
                "player": player,
                "game": game,
                "team_id": team_id,
                "team_abbr": team_id_to_abbr.get(team_id, ""),
                "props": []
            }

        stat_name = app_stat.get("display_stat", "Unknown")
        stat_value = float(line.get("stat_value", 0))

        options = line.get("options", [])
        over_option = next(
            (o for o in options if o.get("choice") == "higher"), None)
        under_option = next(
            (o for o in options if o.get("choice") == "lower"), None)

        prop = {
            "id": line.get("id"),
            "stat_name": stat_name,
            "line": stat_value,
            "over_american": over_option.get("american_price", "-110") if over_option else "-110",
            "under_american": under_option.get("american_price", "-110") if under_option else "-110",
        }

        players_with_props[player_id]["props"].append(prop)

    print(f"  NBA players with props: {len(players_with_props)}")
    total_props = sum(len(p["props"]) for p in players_with_props.values())
    print(f"  Total NBA props: {total_props}")

    return {
        "players": list(players_with_props.values()),
        "games": [g for g in games if g.get("sport_id") == "NBA"]
    }


def get_espn_nba_schedule() -> list:
    """Fetch today's NBA schedule from ESPN."""
    print("\n=== Fetching ESPN NBA Schedule ===")

    status, data = fetch_json_httpx(
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard")

    if status != 200 or not data:
        print(f"ERROR: Failed to fetch ESPN data (status: {status})")
        return []

    events = data.get("events", [])
    print(f"  Games today: {len(events)}")

    games = []
    for event in events:
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        home_team = next(
            (c for c in competitors if c.get("homeAway") == "home"), {})
        away_team = next(
            (c for c in competitors if c.get("homeAway") == "away"), {})

        game = {
            "id": event.get("id"),
            "name": event.get("name"),
            "short_name": event.get("shortName"),
            "date": event.get("date"),
            "status": event.get("status", {}).get("type", {}).get("description", "Scheduled"),
            "home_team": home_team.get("team", {}).get("displayName", ""),
            "home_abbr": home_team.get("team", {}).get("abbreviation", ""),
            "away_team": away_team.get("team", {}).get("displayName", ""),
            "away_abbr": away_team.get("team", {}).get("abbreviation", ""),
        }
        games.append(game)
        print(f"    {game['short_name']} - {game['status']}")

    return games


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

        position = "N/A"
        try:
            player_info = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id)
            info = player_info.get_normalized_dict()['CommonPlayerInfo']
            if info:
                position = str(info[0].get('POSITION', 'N/A'))
        except:
            pass

        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id, season='2025-26')
            games = log.get_normalized_dict()['PlayerGameLog'][:5]

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


def format_props_for_ios(props: list) -> list:
    """Format Underdog props for iOS app structure."""
    ios_props = []
    seen_stats = set()

    # Prioritize main stats
    priority_stats = ["Points", "Rebounds", "Assists",
                      "3-Pointers Made", "Pts + Rebs + Asts"]

    def prop_priority(p):
        stat = p["stat_name"]
        if stat in priority_stats:
            return priority_stats.index(stat)
        return 100

    sorted_props = sorted(props, key=prop_priority)

    for prop in sorted_props:
        stat_name = prop["stat_name"]

        if stat_name in seen_stats or len(ios_props) >= 6:
            continue
        seen_stats.add(stat_name)

        short_name = stat_name
        short_name = short_name.replace("Points", "Pts")
        short_name = short_name.replace("Rebounds", "Reb")
        short_name = short_name.replace("Assists", "Ast")
        short_name = short_name.replace("3-Pointers Made", "3PM")
        short_name = short_name.replace("Pts + Rebs + Asts", "PRA")
        short_name = short_name.replace("Fantasy Points", "FPTS")

        try:
            over_odds = int(prop["over_american"].replace("+", ""))
        except:
            over_odds = -110
        try:
            under_odds = int(prop["under_american"].replace("+", ""))
        except:
            under_odds = -110

        ios_props.append({
            "id": prop["id"],
            "statName": short_name,
            "line": prop["line"],
            "overOdds": over_odds,
            "underOdds": under_odds,
        })

    return ios_props


@https_fn.on_request(secrets=["GOOGLE_API_KEY"], timeout_sec=540, memory=1024)
def batch_analyze(req: https_fn.Request) -> https_fn.Response:
    """
    Fetch NBA player props from Underdog Fantasy and analyze with Gemini.
    Uses ESPN for schedule data and nba_api for player stats enrichment.
    """

    print("\n" + "="*60)
    print("=== UNDERDOG + ESPN BATCH ANALYSIS ===")
    print("="*60 + "\n")

    # 1. Fetch props from Underdog Fantasy (no API key needed!)
    underdog_data = get_underdog_nba_props()

    if not underdog_data["players"]:
        return https_fn.Response(json.dumps({
            "status": "error",
            "message": "No NBA player props found from Underdog Fantasy",
            "note": "This may happen if no NBA games are scheduled today"
        }), status=404, mimetype='application/json')

    # 2. Fetch ESPN schedule for additional game context
    espn_games = get_espn_nba_schedule()

    print(
        f"\nProcessing {len(underdog_data['players'])} players with props...\n")

    # 3. Enrich with NBA stats (parallel)
    enriched_players = []

    def enrich_player(player_data):
        player = player_data["player"]
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(
        )

        # Try to get NBA API stats
        nba_stats = get_player_stats_quick(player_name)

        return {
            "underdog_player": player,
            "underdog_props": player_data["props"],
            "underdog_game": player_data.get("game", {}),
            "underdog_team_abbr": player_data.get("team_abbr", ""),
            "nba_stats": nba_stats,
            "name": player_name,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(enrich_player, p): p["player"].get(
            "id") for p in underdog_data["players"]}
        for future in as_completed(futures):
            try:
                result = future.result()
                enriched_players.append(result)
                if result.get("nba_stats"):
                    print(f"✓ Enriched {result['name']}")
                else:
                    print(f"○ Basic data for {result['name']}")
            except Exception as e:
                print(f"✗ Error: {e}")

    print(f"\n📊 Processed {len(enriched_players)} players\n")

    # 4. Gemini AI Analysis
    ai_by_name = {}
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if google_api_key and len(enriched_players) > 0:
        try:
            players_for_ai = enriched_players[:25]
            summaries = []

            for ep in players_for_ai:
                ud_game = ep.get("underdog_game", {})
                nba_stats = ep.get("nba_stats") or {}

                opponent = ud_game.get("abbreviated_title", "TBD")
                averages = nba_stats.get(
                    "averages", {"pts": 0, "reb": 0, "ast": 0})

                # Get top props for context
                top_props = [
                    f"{p['stat_name']} {p['line']}" for p in ep["underdog_props"][:3]]

                summaries.append({
                    "name": ep["name"],
                    "position": nba_stats.get("position", ep["underdog_player"].get("position_name", "N/A")),
                    "averages": averages,
                    "opponent": opponent,
                    "props": top_props
                })

            client = genai.Client(api_key=google_api_key)
            prompt = f"""You are an expert NBA handicapper providing prop bet analysis.

**PLAYERS TO ANALYZE:** {len(summaries)}

**DATA:**
{json.dumps(summaries, indent=2)}

**FOR EACH PLAYER PROVIDE:**
1. "trending": "hot" (strong bet) or "up" (standard play)
2. "analysis": A specific 1-2 sentence analysis that MUST include:
   - The opponent context
   - A concrete recommendation on one of their props

**OUTPUT FORMAT (VALID JSON):**
{{
    "players": [
        {{
            "name": "Player Name",
            "trending": "hot",
            "analysis": "Facing the Celtics who rank 3rd in defensive rating. Lean Under 24.5 pts."
        }}
    ]
}}
"""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"response_mime_type": "application/json",
                        "temperature": 0.4}
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

    # 5. Clear old props and write to Firestore
    db = firestore.client()

    print("🗑️  Clearing old props collection...")
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

    print(f"🗑️  Deleted {deleted_count} old documents")

    # Write new data
    batch = db.batch()
    written_count = 0

    for ep in enriched_players:
        ud_player = ep["underdog_player"]
        ud_props = ep["underdog_props"]
        ud_game = ep.get("underdog_game", {})
        nba_stats = ep.get("nba_stats")

        ios_props = format_props_for_ios(ud_props)
        if not ios_props:
            continue

        # Get player info (prefer NBA API data if available)
        if nba_stats:
            player_id = nba_stats["id"]
            player_name = nba_stats["name"]
            team_abbr = nba_stats["team_code"]
            position = nba_stats["position"]
            image_url = nba_stats["image"]
        else:
            player_id = ud_player.get("id", str(uuid.uuid4()))
            player_name = ep["name"]
            # Use team abbreviation from Underdog data
            team_abbr = ep.get("underdog_team_abbr", "UNK")
            position = ud_player.get("position_name", "N/A")
            image_url = ud_player.get("image_url", "")

        # Determine opponent based on player's team
        abbr_title = ud_game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away, home = abbr_title.split(" @ ")
            if team_abbr == away:
                opponent = f"@ {home}"
            elif team_abbr == home:
                opponent = f"vs {away}"
            else:
                opponent = abbr_title
        else:
            opponent = ud_game.get("short_title", "TBD")

        # Game time with UTC timestamp for client-side conversion
        game_time = "Tonight"
        game_time_utc = None
        scheduled = ud_game.get("scheduled_at", "")
        if scheduled:
            try:
                game_dt = datetime.datetime.fromisoformat(
                    scheduled.replace('Z', '+00:00'))
                game_time = game_dt.strftime("%I:%M %p UTC")
                game_time_utc = game_dt.isoformat()
            except:
                pass

        # AI analysis
        player_ai = ai_by_name.get(player_name.lower(), {})
        trending = player_ai.get("trending", "up")
        analysis = player_ai.get("analysis", "")
        if trending not in ["up", "hot"]:
            trending = "up"

        ios_card = {
            "id": player_id if isinstance(player_id, int) else str(player_id),
            "name": player_name,
            "teamAbbr": team_abbr,
            "position": position,
            "imageName": image_url,
            "props": ios_props,
            "opponent": opponent,
            "gameTime": game_time,
            "gameTimeUTC": game_time_utc,
            "trending": trending,
            "ai_analysis": analysis,
            "source": "underdog",
            "last_updated": datetime.datetime.now().isoformat()
        }

        # Use string ID for Firestore document
        doc_id = str(player_id) if isinstance(player_id, int) else player_id
        doc_ref = db.collection("props").document(doc_id)
        batch.set(doc_ref, ios_card)
        written_count += 1

        if written_count % 400 == 0:
            batch.commit()
            batch = db.batch()

    if written_count % 400 != 0:
        batch.commit()

    print(f"\n{'='*60}")
    print(f"=== COMPLETE: Wrote {written_count} players to Firestore ===")
    print("="*60 + "\n")

    return https_fn.Response(json.dumps({
        "status": "success",
        "message": f"Fetched and analyzed {written_count} players from Underdog Fantasy",
        "players_written": written_count,
        "source": "underdog_fantasy",
        "espn_games_today": len(espn_games)
    }), mimetype='application/json')


# ============================================================
# SCHEDULED FUNCTION - Runs automatically via Cloud Scheduler
# ============================================================

@scheduler_fn.on_schedule(
    schedule="0 9,18 * * *",
    timezone=scheduler_fn.Timezone("America/Los_Angeles"),
    secrets=["GOOGLE_API_KEY"],
    timeout_sec=540,
    memory=1024
)
def scheduled_refresh(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Automatically refresh all player props twice daily.
    Runs at 9am and 6pm Pacific Time.
    """
    print("\n" + "="*60)
    print("=== SCHEDULED REFRESH - UNDERDOG + ESPN ===")
    print(f"=== Time: {datetime.datetime.now().isoformat()} ===")
    print("="*60 + "\n")

    # Reuse the same logic
    underdog_data = get_underdog_nba_props()
    if not underdog_data["players"]:
        print("No NBA props available")
        return

    espn_games = get_espn_nba_schedule()

    # Process players (simplified version for scheduled runs)
    db = firestore.client()

    # Clear old
    props_ref = db.collection("props")
    for doc in props_ref.stream():
        doc.reference.delete()

    # Write new
    for player_data in underdog_data["players"]:
        player = player_data["player"]
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(
        )
        ud_game = player_data.get("game", {})
        team_abbr = player_data.get("team_abbr", "UNK")

        ios_props = format_props_for_ios(player_data["props"])
        if not ios_props:
            continue

        # Determine opponent based on player's team
        abbr_title = ud_game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away, home = abbr_title.split(" @ ")
            if team_abbr == away:
                opponent = f"@ {home}"
            elif team_abbr == home:
                opponent = f"vs {away}"
            else:
                opponent = abbr_title
        else:
            opponent = ud_game.get("short_title", "TBD")

        game_time = "Tonight"
        game_time_utc = None
        if ud_game.get("scheduled_at"):
            try:
                game_dt = datetime.datetime.fromisoformat(
                    ud_game["scheduled_at"].replace('Z', '+00:00'))
                game_time = game_dt.strftime("%I:%M %p UTC")
                game_time_utc = game_dt.isoformat()
            except:
                pass

        card = {
            "id": player.get("id", str(uuid.uuid4())),
            "name": player_name,
            "teamAbbr": team_abbr,
            "position": player.get("position_name", "N/A"),
            "imageName": player.get("image_url", ""),
            "props": ios_props,
            "opponent": opponent,
            "gameTime": game_time,
            "gameTimeUTC": game_time_utc,
            "trending": "up",
            "ai_analysis": "",
            "source": "underdog",
            "last_updated": datetime.datetime.now().isoformat()
        }

        db.collection("props").document(str(card["id"])).set(card)

    print("=== SCHEDULED REFRESH COMPLETE ===")
