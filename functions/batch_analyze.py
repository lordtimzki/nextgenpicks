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


# ============================================================
# RANKING SYSTEM FUNCTIONS
# ============================================================

def calculate_urgency_score(game_time_utc: str) -> float:
    """
    Calculate urgency score based on how soon the game starts.
    Within 2 hours: 10 points
    Within 6 hours: 7 points
    Today: 5 points
    Otherwise: 2 points
    """
    if not game_time_utc:
        return 2.0

    try:
        game_dt = datetime.datetime.fromisoformat(
            game_time_utc.replace('Z', '+00:00'))
        now = datetime.datetime.now(timezone.utc)
        hours_until_game = (game_dt - now).total_seconds() / 3600

        if hours_until_game <= 2:
            return 10.0
        elif hours_until_game <= 6:
            return 7.0
        elif hours_until_game <= 24:
            return 5.0
        else:
            return 2.0
    except Exception:
        return 2.0


def calculate_odds_value_score(props: list) -> float:
    """
    Calculate odds value score based on skewed odds.
    If over odds > -105 (plus money or close): higher score
    Standard -110/-110: neutral score
    """
    if not props:
        return 5.0

    best_odds_score = 5.0

    for prop in props:
        try:
            over_odds = int(
                str(prop.get("over_american", "-110")).replace("+", ""))
        except (ValueError, TypeError):
            over_odds = -110

        # Plus money or better odds indicate value
        if over_odds >= 100:
            odds_score = 10.0
        elif over_odds >= -105:
            odds_score = 8.0
        elif over_odds >= -110:
            odds_score = 5.0
        elif over_odds >= -120:
            odds_score = 3.0
        else:
            odds_score = 2.0

        best_odds_score = max(best_odds_score, odds_score)

    return best_odds_score


def calculate_prop_ranking_score(prop: dict, averages: dict, game_time_utc: str) -> tuple:
    """
    Calculate ranking score for a SINGLE prop.
    Returns (total_score, edge_value, player_average_for_stat, urgency_score, recommended_direction)

    Formula: (edgeScore * 0.4) + (starPowerScore * 0.3) + (urgencyScore * 0.2) + (oddsValueScore * 0.1)
    """
    stat = prop.get("stat_name", "").lower()
    line = float(prop.get("line", 0))

    # Determine which average to use for this prop
    player_avg = 0
    stat_lower = stat.lower()

    if "3-pointer" in stat_lower or "3pm" in stat_lower:
        player_avg = averages.get("fg3m", 0)  # Use actual 3PM stat
    elif "point" in stat_lower or "pts" in stat_lower:
        player_avg = averages.get("pts", 0)
    elif "rebound" in stat_lower or "reb" in stat_lower:
        player_avg = averages.get("reb", 0)
    elif "assist" in stat_lower or "ast" in stat_lower:
        player_avg = averages.get("ast", 0)
    elif "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        player_avg = averages.get(
            "pts", 0) + averages.get("reb", 0) + averages.get("ast", 0)

    # 1. Edge Score - how much player avg exceeds the line
    edge = player_avg - line if player_avg > 0 else 0
    edge_score = min(10.0, max(0.0, (edge / 5.0) * 10.0))

    # Determine recommendation: Over if player avg > line, Under otherwise
    recommended_direction = "Over" if player_avg > line else "Under"

    # 2. Star Power Score - based on total production
    total_production = averages.get(
        "pts", 0) + averages.get("reb", 0) + averages.get("ast", 0)
    star_score = min(10.0, total_production / 4.0)

    # 3. Urgency Score
    urgency_score = calculate_urgency_score(game_time_utc)

    # 4. Odds Value Score (for this single prop)
    try:
        over_odds = int(
            str(prop.get("over_american", "-110")).replace("+", ""))
    except (ValueError, TypeError):
        over_odds = -110

    if over_odds >= 100:
        odds_score = 10.0
    elif over_odds >= -105:
        odds_score = 8.0
    elif over_odds >= -110:
        odds_score = 5.0
    elif over_odds >= -120:
        odds_score = 3.0
    else:
        odds_score = 2.0

    # Calculate total score
    total = (edge_score * 0.4) + (star_score * 0.3) + \
        (urgency_score * 0.2) + (odds_score * 0.1)

    return total, round(edge, 2), round(player_avg, 1), urgency_score, recommended_direction


def calculate_ranking_score(player_data: dict, props: list, game_time_utc: str) -> tuple:
    """
    Calculate ranking score for a player (legacy - finds best prop score).
    Returns (total_score, component_scores)
    """
    averages = player_data.get("averages", {"pts": 0, "reb": 0, "ast": 0})

    best_score = 0
    best_components = {"edge": 0, "star": 0, "urgency": 0, "odds": 0}

    for prop in props:
        score, edge, player_avg, urgency, recommended_direction = calculate_prop_ranking_score(
            prop, averages, game_time_utc)
        if score > best_score:
            best_score = score
            total_production = averages.get(
                "pts", 0) + averages.get("reb", 0) + averages.get("ast", 0)
            best_components = {
                "edge": round(min(10.0, max(0.0, (edge / 5.0) * 10.0)), 2),
                "star": round(min(10.0, total_production / 4.0), 2),
                "urgency": round(urgency, 2),
                "odds": 5.0
            }

    return best_score, best_components


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
    # Use string keys to avoid type mismatches
    team_id_to_abbr = {}
    for game in games:
        abbr_title = game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away_abbr, home_abbr = abbr_title.split(" @ ")
            away_team_id = game.get("away_team_id")
            home_team_id = game.get("home_team_id")
            if away_team_id:
                team_id_to_abbr[str(away_team_id)] = away_abbr
            if home_team_id:
                team_id_to_abbr[str(home_team_id)] = home_abbr

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
            # Try team_id lookup with string key, fallback to extracting from game title
            team_abbr = team_id_to_abbr.get(str(team_id), "")
            if not team_abbr and game:
                # Try to infer from game abbreviated_title
                abbr_title = game.get("abbreviated_title", "")
                if " @ " in abbr_title:
                    away, home = abbr_title.split(" @ ")
                    # If only two teams in game, we can't determine which is the player's
                    # but at least we have the matchup context
                    team_abbr = ""  # Will be resolved later with opponent display
            players_with_props[player_id] = {
                "player": player,
                "game": game,
                "team_id": team_id,
                "team_abbr": team_abbr,
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
    """Get basic player stats from NBA API including last 5 games for hit rate."""
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
                avg_fg3m = sum(g['FG3M'] for g in games) / len(games)

                # Extract last 5 game stats for hit rate calculation
                last5_games = []
                for g in games:
                    last5_games.append({
                        "pts": g['PTS'],
                        "reb": g['REB'],
                        "ast": g['AST'],
                        "fg3m": g['FG3M'],
                        "matchup": g['MATCHUP'],
                        "date": g['GAME_DATE']
                    })

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
                        "ast": round(avg_ast, 1),
                        "fg3m": round(avg_fg3m, 1)
                    },
                    "last5Games": last5_games
                }
        except Exception as e:
            print(f"Could not get game log for {player_name}: {e}")

        return {
            "id": int(player_id),
            "name": player['full_name'],
            "position": position,
            "team_code": "",
            "team_name": "",
            "image": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
            "averages": {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0},
            "last5Games": []
        }
    except Exception as e:
        print(f"Error getting stats for {player_name}: {e}")
        return None


def calculate_hit_rate(last5_games: list, stat_name: str, line: float) -> dict:
    """
    Calculate hit rate for a specific stat against a line.
    Returns dict with hits, total, and individual game results.
    """
    if not last5_games:
        return {"hits": 0, "total": 0, "results": []}

    stat_key = None
    stat_lower = stat_name.lower()

    if "3-pointer" in stat_lower or "3pm" in stat_lower:
        stat_key = "fg3m"
    elif "point" in stat_lower or "pts" in stat_lower:
        stat_key = "pts"
    elif "rebound" in stat_lower or "reb" in stat_lower:
        stat_key = "reb"
    elif "assist" in stat_lower or "ast" in stat_lower:
        stat_key = "ast"
    elif "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        stat_key = "pra"  # Combined stat

    if not stat_key:
        return {"hits": 0, "total": 0, "results": []}

    hits = 0
    results = []

    for game in last5_games:
        if stat_key == "pra":
            value = game.get("pts", 0) + game.get("reb", 0) + \
                game.get("ast", 0)
        else:
            value = game.get(stat_key, 0)

        hit = value > line
        if hit:
            hits += 1
        results.append({
            "value": value,
            "hit": hit,
            "date": game.get("date", ""),
            "matchup": game.get("matchup", "")
        })

    return {
        "hits": hits,
        "total": len(last5_games),
        "results": results
    }


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

    # 4. Calculate ranking scores for all players
    print("📊 Calculating ranking scores...")
    for ep in enriched_players:
        nba_stats = ep.get("nba_stats") or {}
        averages = nba_stats.get(
            "averages", {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0})
        ud_game = ep.get("underdog_game", {})
        game_time_utc = None
        if ud_game.get("scheduled_at"):
            try:
                game_dt = datetime.datetime.fromisoformat(
                    ud_game["scheduled_at"].replace('Z', '+00:00'))
                game_time_utc = game_dt.isoformat()
            except:
                pass

        # Calculate ranking score
        ranking_score, score_components = calculate_ranking_score(
            {"averages": averages},
            ep["underdog_props"],
            game_time_utc
        )
        ep["ranking_score"] = ranking_score
        ep["score_components"] = score_components
        ep["player_averages"] = averages

    # Sort by ranking score (highest first) and mark top 12 as featured
    enriched_players.sort(key=lambda x: x.get(
        "ranking_score", 0), reverse=True)
    featured_count = min(12, len(enriched_players))
    for i, ep in enumerate(enriched_players):
        ep["featured"] = i < featured_count

    print(f"✓ Marked top {featured_count} players as featured")

    # 5. Gemini AI Analysis (per-prop, not per-player)
    # Key format: "playername_statname" -> analysis
    ai_by_prop = {}
    google_api_key = os.getenv("GOOGLE_API_KEY")

    # Build list of top props to analyze (will be sorted later, but estimate top 20)
    # First, collect all props with their ranking scores
    all_props_for_ranking = []
    for ep in enriched_players:
        ud_player = ep["underdog_player"]
        ud_props = ep["underdog_props"]
        nba_stats = ep.get("nba_stats") or {}
        player_averages = ep.get(
            "player_averages", {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0})
        ud_game = ep.get("underdog_game", {})

        # Get player's team
        player_team = ""
        if nba_stats and nba_stats.get("team_code"):
            player_team = nba_stats["team_code"]
        elif ep.get("underdog_team_abbr"):
            player_team = ep["underdog_team_abbr"]

        # Determine opponent from matchup
        abbr_title = ud_game.get("abbreviated_title", "")  # e.g., "PHX @ LAL"
        opponent_team = ""
        if " @ " in abbr_title:
            away, home = abbr_title.split(" @ ")
            if player_team == away:
                opponent_team = home
            elif player_team == home:
                opponent_team = away
            else:
                # Fallback: just use the other team
                opponent_team = home if player_team != home else away

        game_time_utc = None
        if ud_game.get("scheduled_at"):
            try:
                game_dt = datetime.datetime.fromisoformat(
                    ud_game["scheduled_at"].replace('Z', '+00:00'))
                game_time_utc = game_dt.isoformat()
            except:
                pass

        priority_stats = ["Points", "Rebounds", "Assists",
                          "3-Pointers Made", "Pts + Rebs + Asts"]
        for prop in ud_props:
            stat_name = prop.get("stat_name", "")
            if stat_name not in priority_stats:
                continue

            prop_score, edge, player_avg, urgency_score, recommended_direction = calculate_prop_ranking_score(
                prop, player_averages, game_time_utc
            )

            all_props_for_ranking.append({
                "player_name": ep["name"],
                "player_team": player_team,
                "opponent_team": opponent_team,
                "position": nba_stats.get("position", ud_player.get("position_name", "N/A")),
                "stat_name": stat_name,
                "line": prop.get("line", 0),
                "player_avg": player_avg,
                "ranking_score": prop_score,
                "averages": player_averages
            })

    # Sort by ranking score and take top 20 for AI analysis
    all_props_for_ranking.sort(key=lambda x: x["ranking_score"], reverse=True)
    top_props_for_ai = all_props_for_ranking[:20]

    if google_api_key and len(top_props_for_ai) > 0:
        try:
            # Build prop-specific summaries
            prop_summaries = []
            for prop_data in top_props_for_ai:
                # Get the relevant average for this stat
                stat_lower = prop_data["stat_name"].lower()
                relevant_avg = prop_data["player_avg"]
                avg_label = "average"

                if "point" in stat_lower:
                    avg_label = "pts avg"
                elif "rebound" in stat_lower:
                    avg_label = "reb avg"
                elif "assist" in stat_lower:
                    avg_label = "ast avg"
                elif "3-pointer" in stat_lower:
                    avg_label = "3PM avg"
                elif "pts + rebs + asts" in stat_lower:
                    avg_label = "PRA avg"

                prop_summaries.append({
                    "player": prop_data["player_name"],
                    "team": prop_data["player_team"],
                    "opponent": prop_data["opponent_team"],
                    "position": prop_data["position"],
                    "stat": prop_data["stat_name"],
                    "line": prop_data["line"],
                    f"{avg_label}": relevant_avg
                })

            client = genai.Client(api_key=google_api_key)
            prompt = f"""You are an expert NBA handicapper providing prop bet analysis.

**CRITICAL CONTEXT:**
- Each prop shows which TEAM the player plays FOR and which team they play AGAINST (opponent).
- The player is ON the "team" field, playing AGAINST the "opponent" field.
- Example: If team="PHX" and opponent="LAL", the player plays FOR Phoenix AGAINST the Lakers.

**PROPS TO ANALYZE:** {len(prop_summaries)}

**DATA:**
{json.dumps(prop_summaries, indent=2)}

**ANALYSIS GUIDELINES - FOCUS ON MATCHUP FACTORS:**
- DO NOT just say "player averages X which is higher than the line" - that's not insightful
- FOCUS ON these matchup-specific factors:
  * Opponent's defensive rating and how they defend this position/stat
  * Opponent's pace of play (fast pace = more possessions = more stats)
  * Opponent's weaknesses (e.g., "LAL allows 4th most rebounds to centers")
  * Recent injury news affecting opponent's defense
  * Back-to-back or fatigue factors
  * Home/away splits if relevant
- Be specific about WHY the matchup favors Over or Under

**FOR EACH PROP PROVIDE:**
1. "player": The player's name (must match exactly)
2. "stat": The stat type (must match exactly: "Points", "Rebounds", "Assists", "3-Pointers Made", or "Pts + Rebs + Asts")
3. "trending": "hot" (strong edge based on matchup) or "up" (standard play)
4. "analysis": 1-2 sentences focusing on MATCHUP FACTORS, not just averages. Why does this specific opponent make Over/Under favorable?
5. "direction": "Over" or "Under" recommendation

**OUTPUT FORMAT (VALID JSON):**
{{
    "props": [
        {{
            "player": "Cooper Flagg",
            "stat": "Points",
            "trending": "hot",
            "analysis": "LAL ranks 28th in perimeter defense and plays at the 5th fastest pace. High-volume scoring opportunity.",
            "direction": "Over"
        }},
        {{
            "player": "Cooper Flagg",
            "stat": "Rebounds",
            "trending": "up",
            "analysis": "LAL allows the 3rd most rebounds to forwards this season. Favorable glass matchup.",
            "direction": "Over"
        }}
    ]
}}
"""

            response = client.models.generate_content(
                model="gemini-3-pro",
                contents=prompt,
                config={"response_mime_type": "application/json",
                        "temperature": 0.3}
            )
            ai_results = json.loads(response.text)
            print("✓ Gemini per-prop analysis complete")

            for p in ai_results.get("props", []):
                # Create unique key: playername_stat
                key = f"{p['player'].lower()}_{p['stat'].lower()}"
                ai_by_prop[key] = {
                    "trending": p.get("trending", "up"),
                    "analysis": p.get("analysis", ""),
                    "direction": p.get("direction", "")
                }
        except Exception as e:
            print(f"Gemini error (continuing without AI): {e}")

    # 6. Build individual prop cards (one document per prop)
    print("📊 Building individual prop cards...")
    all_prop_cards = []

    for ep in enriched_players:
        ud_player = ep["underdog_player"]
        ud_props = ep["underdog_props"]
        ud_game = ep.get("underdog_game", {})
        nba_stats = ep.get("nba_stats")
        player_averages = ep.get(
            "player_averages", {"pts": 0, "reb": 0, "ast": 0})

        # Get player info (prefer NBA API data if available)
        if nba_stats and nba_stats.get("team_code") and nba_stats["team_code"] != "UNK":
            player_id = nba_stats["id"]
            player_name = nba_stats["name"]
            team_abbr = nba_stats["team_code"]
            position = nba_stats["position"]
            image_url = nba_stats["image"]
        else:
            player_id = ud_player.get("id", str(uuid.uuid4()))
            player_name = ep["name"]
            team_abbr = ep.get("underdog_team_abbr", "")
            if not team_abbr and nba_stats and nba_stats.get("team_code") and nba_stats["team_code"] != "UNK":
                team_abbr = nba_stats["team_code"]
            if not team_abbr:
                abbr_title = ud_game.get("abbreviated_title", "")
                if " @ " in abbr_title:
                    away, home = abbr_title.split(" @ ")
                    team_abbr = away
            position = ud_player.get("position_name", "N/A")
            if nba_stats:
                position = nba_stats.get("position", position)
            image_url = ud_player.get("image_url", "")
            if nba_stats and nba_stats.get("image"):
                image_url = nba_stats["image"]

        # Show full matchup
        abbr_title = ud_game.get("abbreviated_title", "")
        opponent = abbr_title if abbr_title else ud_game.get(
            "short_title", "TBD")

        # Game time
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

        # AI analysis is now per-prop, handled below in the prop loop

        # Create individual prop cards for priority stats only
        priority_stats = ["Points", "Rebounds", "Assists",
                          "3-Pointers Made", "Pts + Rebs + Asts"]

        # Get last 5 games for hit rate calculation
        last5_games = []
        if nba_stats:
            last5_games = nba_stats.get("last5Games", [])

        for prop in ud_props:
            stat_name = prop.get("stat_name", "")
            # Only include priority stats for cleaner feed
            if stat_name not in priority_stats:
                continue

            # Calculate ranking score for this specific prop
            prop_score, edge, player_avg, urgency_score, recommended_direction = calculate_prop_ranking_score(
                prop, player_averages, game_time_utc
            )

            # Calculate hit rate for this prop
            line = float(prop.get("line", 0))
            hit_rate = calculate_hit_rate(last5_games, stat_name, line)

            # Format stat name
            short_name = stat_name.replace(
                "Points", "Pts").replace("Rebounds", "Reb")
            short_name = short_name.replace(
                "Assists", "Ast").replace("3-Pointers Made", "3PM")
            short_name = short_name.replace("Pts + Rebs + Asts", "PRA")

            try:
                over_odds = int(
                    str(prop.get("over_american", "-110")).replace("+", ""))
            except:
                over_odds = -110
            try:
                under_odds = int(
                    str(prop.get("under_american", "-110")).replace("+", ""))
            except:
                under_odds = -110

            prop_card = {
                "player_id": str(player_id) if isinstance(player_id, int) else player_id,
                "name": player_name,
                "teamAbbr": team_abbr,
                "position": position,
                "imageName": image_url,
                "opponent": opponent,
                "gameTime": game_time,
                "gameTimeUTC": game_time_utc,
                "source": "underdog",
                "last_updated": datetime.datetime.now().isoformat(),
                # Single prop info
                "statName": short_name,
                "statNameFull": stat_name,
                "line": prop.get("line", 0),
                "overOdds": over_odds,
                "underOdds": under_odds,
                "propId": prop.get("id", str(uuid.uuid4())),
                # Ranking data
                "rankingScore": round(prop_score, 2),
                "edge": edge,
                "playerAverage": player_avg,
                "urgencyScore": urgency_score,
                "recommendedDirection": recommended_direction,
                # Hit rate data (last 5 games)
                "hitRate": {
                    "hits": hit_rate["hits"],
                    "total": hit_rate["total"],
                    "results": hit_rate["results"]
                },
                # Will be set after sorting
                "section": "topPicks",
                "featured": False,
                "trending": "up",
                "ai_analysis": "",
                # Player averages for context
                "playerAverages": {
                    "pts": player_averages.get("pts", 0),
                    "reb": player_averages.get("reb", 0),
                    "ast": player_averages.get("ast", 0),
                    "fg3m": player_averages.get("fg3m", 0)
                }
            }

            all_prop_cards.append(prop_card)

    print(f"📊 Created {len(all_prop_cards)} individual prop cards")

    # 7. Sort and categorize props
    # Sort by ranking score (highest first)
    all_prop_cards.sort(key=lambda x: x.get("rankingScore", 0), reverse=True)

    # "forYou" section: top 5 best-ranked props for 5-leg parlay builders
    for_you_count = min(5, len(all_prop_cards))
    for i, card in enumerate(all_prop_cards[:for_you_count]):
        card["section"] = "forYou"
        card["featured"] = True

        # Add AI analysis for this specific prop (per-prop lookup)
        prop_key = f"{card['name'].lower()}_{card['statNameFull'].lower()}"
        prop_ai = ai_by_prop.get(prop_key, {})

        card["trending"] = prop_ai.get("trending", "up")
        if card["trending"] not in ["up", "hot"]:
            card["trending"] = "up"
        card["ai_analysis"] = prop_ai.get("analysis", "")

        # Add AI recommendation direction for this prop
        if prop_ai.get("direction"):
            card["aiRecommended"] = prop_ai.get("direction")

    # "topPicks" section: props 6-20 (next best after forYou)
    top_picks_start = for_you_count
    top_picks_end = min(20, len(all_prop_cards))
    top_picks_count = top_picks_end - top_picks_start

    for i, card in enumerate(all_prop_cards[top_picks_start:top_picks_end]):
        card["section"] = "topPicks"
        card["featured"] = True

        # Add AI analysis for this specific prop (per-prop lookup)
        prop_key = f"{card['name'].lower()}_{card['statNameFull'].lower()}"
        prop_ai = ai_by_prop.get(prop_key, {})

        card["trending"] = prop_ai.get("trending", "up")
        if card["trending"] not in ["up", "hot"]:
            card["trending"] = "up"
        card["ai_analysis"] = prop_ai.get("analysis", "")

        # Add AI recommendation direction for this prop
        if prop_ai.get("direction"):
            card["aiRecommended"] = prop_ai.get("direction")

    # Mark remaining cards as allProps
    for card in all_prop_cards[top_picks_end:]:
        card["section"] = "allProps"
        card["featured"] = False

    print(
        f"✓ Categorized: {for_you_count} forYou (top 5), {top_picks_count} topPicks")

    # 8. Clear old props and write to Firestore
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

    # Write new prop cards
    batch = db.batch()
    written_count = 0

    for card in all_prop_cards:
        # Create unique document ID: playerId_statName
        doc_id = f"{card['player_id']}_{card['statName'].lower().replace(' ', '_')}"
        card["id"] = doc_id  # Add id field for iOS

        doc_ref = db.collection("props").document(doc_id)
        batch.set(doc_ref, card)
        written_count += 1

        if written_count % 400 == 0:
            batch.commit()
            batch = db.batch()

    if written_count % 400 != 0:
        batch.commit()

    print(f"\n{'='*60}")
    print(f"=== COMPLETE: Wrote {written_count} prop cards to Firestore ===")
    print(f"=== Top Picks: {top_picks_count}, For You: {for_you_count} ===")
    print("="*60 + "\n")

    return https_fn.Response(json.dumps({
        "status": "success",
        "message": f"Created {written_count} individual prop cards",
        "props_written": written_count,
        "top_picks": top_picks_count,
        "for_you": for_you_count,
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
    Creates individual prop cards (one document per prop).
    """
    print("\n" + "="*60)
    print("=== SCHEDULED REFRESH - UNDERDOG + ESPN ===")
    print(f"=== Time: {datetime.datetime.now().isoformat()} ===")
    print("="*60 + "\n")

    underdog_data = get_underdog_nba_props()
    if not underdog_data["players"]:
        print("No NBA props available")
        return

    espn_games = get_espn_nba_schedule()
    db = firestore.client()

    # Clear old props
    props_ref = db.collection("props")
    for doc in props_ref.stream():
        doc.reference.delete()

    # Build individual prop cards
    all_prop_cards = []
    priority_stats = ["Points", "Rebounds", "Assists",
                      "3-Pointers Made", "Pts + Rebs + Asts"]

    for player_data in underdog_data["players"]:
        player = player_data["player"]
        player_id = player.get("id", str(uuid.uuid4()))
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(
        )
        ud_game = player_data.get("game", {})
        team_abbr = player_data.get("team_abbr", "")
        if not team_abbr:
            abbr_title = ud_game.get("abbreviated_title", "")
            if " @ " in abbr_title:
                away, home = abbr_title.split(" @ ")
                team_abbr = away

        abbr_title = ud_game.get("abbreviated_title", "")
        opponent = abbr_title if abbr_title else ud_game.get(
            "short_title", "TBD")

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

        # Create individual prop cards for priority stats only
        for prop in player_data["props"]:
            stat_name = prop.get("stat_name", "")
            if stat_name not in priority_stats:
                continue

            # Calculate ranking score for this prop (no NBA stats in scheduled run)
            prop_score, edge, player_avg, urgency_score, recommended_direction = calculate_prop_ranking_score(
                prop, {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0}, game_time_utc
            )

            # Format stat name
            short_name = stat_name.replace(
                "Points", "Pts").replace("Rebounds", "Reb")
            short_name = short_name.replace(
                "Assists", "Ast").replace("3-Pointers Made", "3PM")
            short_name = short_name.replace("Pts + Rebs + Asts", "PRA")

            try:
                over_odds = int(
                    str(prop.get("over_american", "-110")).replace("+", ""))
            except:
                over_odds = -110
            try:
                under_odds = int(
                    str(prop.get("under_american", "-110")).replace("+", ""))
            except:
                under_odds = -110

            prop_card = {
                "player_id": str(player_id),
                "name": player_name,
                "teamAbbr": team_abbr,
                "position": player.get("position_name", "N/A"),
                "imageName": player.get("image_url", ""),
                "opponent": opponent,
                "gameTime": game_time,
                "gameTimeUTC": game_time_utc,
                "source": "underdog",
                "last_updated": datetime.datetime.now().isoformat(),
                "statName": short_name,
                "statNameFull": stat_name,
                "line": prop.get("line", 0),
                "overOdds": over_odds,
                "underOdds": under_odds,
                "propId": prop.get("id", str(uuid.uuid4())),
                "rankingScore": round(prop_score, 2),
                "edge": edge,
                "playerAverage": player_avg,
                "urgencyScore": urgency_score,
                "recommendedDirection": recommended_direction,
                # Empty for scheduled (no NBA API)
                "hitRate": {"hits": 0, "total": 0, "results": []},
                "section": "topPicks",
                "featured": False,
                "trending": "up",
                "ai_analysis": "",
                "playerAverages": {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0}
            }
            all_prop_cards.append(prop_card)

    # Sort and categorize
    all_prop_cards.sort(key=lambda x: x.get("rankingScore", 0), reverse=True)
    top_picks_count = min(15, len(all_prop_cards))

    for i, card in enumerate(all_prop_cards[:top_picks_count]):
        card["section"] = "topPicks"
        card["featured"] = True

    for_you_count = 0
    for card in all_prop_cards[top_picks_count:]:
        if card.get("urgencyScore", 0) >= 7 and for_you_count < 10:
            card["section"] = "forYou"
            card["featured"] = True
            for_you_count += 1
        else:
            card["section"] = "allProps"
            card["featured"] = False

    # Write to Firestore
    for card in all_prop_cards:
        doc_id = f"{card['player_id']}_{card['statName'].lower().replace(' ', '_')}"
        card["id"] = doc_id
        db.collection("props").document(doc_id).set(card)

    print(
        f"=== SCHEDULED REFRESH COMPLETE: {len(all_prop_cards)} props, {top_picks_count} topPicks, {for_you_count} forYou ===")
