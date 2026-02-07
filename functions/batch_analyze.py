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
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from retrieve import get_all_team_defense_stats, get_all_player_advanced_stats

# Note: Firebase is initialized in main.py which imports this module


# ============================================================
# INJURY & REST DAY FUNCTIONS
# ============================================================

def get_nba_injuries() -> dict:
    """
    Fetch current NBA injuries from ESPN.
    Returns dict mapping team abbreviation to list of injured players.
    """
    print("\n🏥 Fetching NBA injury report...")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                print(f"  ⚠️ Injury API returned {resp.status_code}")
                return {}

            data = resp.json()
    except Exception as e:
        print(f"  ⚠️ Failed to fetch injuries: {e}")
        return {}

    # ESPN abbreviation mapping (ESPN uses some different abbrevs)
    espn_to_standard = {
        "GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP",
        "UTAH": "UTA", "PHX": "PHO", "WSH": "WAS"
    }

    injuries_by_team = {}

    for team_data in data.get("injuries", []):
        team_info = team_data.get("team", {})
        team_abbr = team_info.get("abbreviation", "")
        team_abbr = espn_to_standard.get(team_abbr, team_abbr)

        team_injuries = []
        for injury in team_data.get("injuries", []):
            athlete = injury.get("athlete", {})
            player_name = athlete.get("displayName", "")
            status = injury.get("status", "")  # Out, Day-To-Day, Questionable
            injury_type = injury.get("type", {}).get("description", "")

            if player_name and status:
                team_injuries.append({
                    "name": player_name,
                    "status": status,
                    "injury": injury_type,
                })

        if team_injuries:
            injuries_by_team[team_abbr] = team_injuries

    total_injured = sum(len(v) for v in injuries_by_team.values())
    print(
        f"  ✓ Found {total_injured} injured players across {len(injuries_by_team)} teams")

    return injuries_by_team


def get_yesterdays_games() -> dict:
    """
    Fetch yesterday's NBA games to detect back-to-backs.
    Returns dict mapping team abbreviation to game info if they played.
    """
    print("\n📅 Checking for back-to-back games...")

    # Use Eastern Time (NBA's official timezone) to determine "yesterday"
    # UTC can be off by a day depending on when the scheduler fires
    eastern = ZoneInfo("America/New_York")
    now_eastern = datetime.datetime.now(eastern)
    yesterday = now_eastern - datetime.timedelta(days=1)
    date_str = yesterday.strftime("%Y%m%d")
    print(f"  📅 Today (ET): {now_eastern.strftime('%Y-%m-%d %H:%M')}, checking yesterday: {yesterday.strftime('%Y-%m-%d')}")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                print(f"  ⚠️ Schedule API returned {resp.status_code}")
                return {}

            data = resp.json()
    except Exception as e:
        print(f"  ⚠️ Failed to fetch yesterday's games: {e}")
        return {}

    espn_to_standard = {
        "GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP",
        "UTAH": "UTA", "PHX": "PHO", "WSH": "WAS"
    }

    teams_played_yesterday = {}

    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])

        for team in competitors:
            team_info = team.get("team", {})
            abbr = team_info.get("abbreviation", "")
            abbr = espn_to_standard.get(abbr, abbr)

            # Get minutes played by key players if available
            teams_played_yesterday[abbr] = {
                "played_yesterday": True,
                "opponent": "",
                "result": ""
            }

            # Try to get opponent
            other_team = next((t for t in competitors if t != team), None)
            if other_team:
                opp_abbr = other_team.get("team", {}).get("abbreviation", "")
                teams_played_yesterday[abbr]["opponent"] = espn_to_standard.get(
                    opp_abbr, opp_abbr)

            # Get result
            score = team.get("score", "0")
            winner = team.get("winner", False)
            teams_played_yesterday[abbr]["result"] = "W" if winner else "L"

    print(
        f"  ✓ {len(teams_played_yesterday)} teams played yesterday (back-to-back)")

    return teams_played_yesterday


def get_todays_lineups() -> dict:
    """
    Fetch today's NBA lineups/starters from ESPN.
    Returns dict mapping player name to lineup status.
    ESPN provides projected starters closer to game time.
    """
    print("\n📋 Fetching lineup confirmations...")

    try:
        with httpx.Client(timeout=15.0) as client:
            # Get today's scoreboard with lineup info
            resp = client.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                print(f"  ⚠️ Scoreboard API returned {resp.status_code}")
                return {}

            data = resp.json()
    except Exception as e:
        print(f"  ⚠️ Failed to fetch lineups: {e}")
        return {}

    espn_to_standard = {
        "GS": "GSW", "SA": "SAS", "NY": "NYK", "NO": "NOP",
        "UTAH": "UTA", "PHX": "PHO", "WSH": "WAS"
    }

    lineup_info = {}  # player_name -> {status, team, is_starter}

    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        game_status = event.get("status", {}).get("type", {}).get("name", "")

        for team_data in competitors:
            team_info = team_data.get("team", {})
            team_abbr = team_info.get("abbreviation", "")
            team_abbr = espn_to_standard.get(team_abbr, team_abbr)

            # Get roster/lineup info if available
            roster = team_data.get("roster", [])
            for player in roster:
                player_name = player.get("displayName", "")
                if not player_name:
                    continue

                # Check if player is starter
                is_starter = player.get("starter", False)
                player_status = player.get("status", {}).get("type", "active")

                lineup_info[player_name.lower()] = {
                    "team": team_abbr,
                    "is_starter": is_starter,
                    "status": player_status,
                    "game_status": game_status,  # scheduled, in_progress, final
                }

            # Also check probables/lineups from competition data
            probables = competition.get("probables", [])
            for probable in probables:
                player_name = probable.get(
                    "athlete", {}).get("displayName", "")
                if player_name:
                    lineup_info[player_name.lower()] = {
                        "team": team_abbr,
                        "is_starter": True,
                        "status": "confirmed",
                        "game_status": game_status,
                    }

    confirmed_starters = sum(
        1 for v in lineup_info.values() if v.get("is_starter"))
    print(
        f"  ✓ Found lineup data for {len(lineup_info)} players ({confirmed_starters} confirmed starters)")

    return lineup_info


def get_player_lineup_status(player_name: str, lineup_cache: dict, injuries_cache: dict, team_abbr: str) -> str:
    """
    Get lineup status for a player.
    Returns: "STARTING", "DNP RISK", "QUESTIONABLE", or ""
    """
    player_key = player_name.lower()

    # Check lineup cache first
    if player_key in lineup_cache:
        info = lineup_cache[player_key]
        if info.get("is_starter"):
            return "STARTING"
        if info.get("status") == "inactive":
            return "OUT"

    # Check injury list
    team_injuries = injuries_cache.get(team_abbr, [])
    for injury in team_injuries:
        if injury.get("name", "").lower() == player_key:
            status = injury.get("status", "").lower()
            if "out" in status:
                return "OUT"
            elif "questionable" in status or "doubtful" in status:
                return "GTD"
            elif "day" in status:
                return "GTD"

    return ""


def get_team_injuries_summary(team_abbr: str, injuries_by_team: dict) -> str:
    """
    Get a summary of key injuries for a team.
    Returns string like "OUT: LeBron James, Anthony Davis (DTD)" or empty string.
    """
    if not team_abbr or team_abbr not in injuries_by_team:
        return ""

    injuries = injuries_by_team.get(team_abbr, [])
    if not injuries:
        return ""

    out_players = []
    dtd_players = []

    for inj in injuries:
        name = inj.get("name", "")
        status = inj.get("status", "").lower()

        # Shorten name to "F. Last" format
        name_parts = name.split()
        if len(name_parts) >= 2:
            short_name = f"{name_parts[0][0]}. {name_parts[-1]}"
        else:
            short_name = name

        if "out" in status:
            out_players.append(short_name)
        elif "day" in status or "questionable" in status:
            dtd_players.append(short_name)

    parts = []
    if out_players:
        parts.append(f"OUT: {', '.join(out_players[:3])}")  # Max 3
    if dtd_players:
        parts.append(f"GTD: {', '.join(dtd_players[:2])}")  # Max 2

    return " | ".join(parts) if parts else ""


def get_player_rest_status(team_abbr: str, teams_played_yesterday: dict) -> str:
    """
    Get rest status for a player's team.
    Returns "B2B" or "B2B vs OPP (W/L)" for back-to-back, or empty string.
    """
    if not team_abbr:
        return ""

    if team_abbr in teams_played_yesterday:
        info = teams_played_yesterday[team_abbr]
        opp = info.get("opponent", "")
        result = info.get("result", "")
        if opp and result:
            return f"B2B vs {opp} ({result})"
        return "B2B"

    return ""


# ============================================================
# RANKING SYSTEM FUNCTIONS
# ============================================================

def get_opponent_abbrev(matchup: str, player_team: str) -> str:
    """
    Extract opponent abbreviation from matchup string.
    Matchup formats: "LAL @ BKN" or "PHX vs DEN"
    Returns the team that isn't the player's team.
    """
    if not matchup or not player_team:
        return ""

    # Handle "AWAY @ HOME" format
    if " @ " in matchup:
        away, home = matchup.split(" @ ")
        away = away.strip()
        home = home.strip()
        if player_team == away:
            return home
        elif player_team == home:
            return away
        # If player_team doesn't match, try to figure it out
        return home if away == player_team else away

    # Handle "HOME vs AWAY" format (less common)
    if " vs " in matchup.lower():
        parts = matchup.lower().split(" vs ")
        if len(parts) == 2:
            team1 = parts[0].strip().upper()
            team2 = parts[1].strip().upper()
            if player_team.upper() == team1:
                return team2
            elif player_team.upper() == team2:
                return team1

    return ""


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


def calculate_prop_ranking_score(prop: dict, averages: dict, game_time_utc: str,
                                  lineup_status: str = "", hit_rate: dict = None,
                                  trend_data: dict = None,
                                  opp_def_rank: int = None,
                                  opp_pace_rank: int = None,
                                  player_advanced: dict = None) -> tuple:
    """
    Calculate ranking score for a SINGLE prop.
    Returns (total_score, edge_value, player_average_for_stat, urgency_score, recommended_direction)

    Formula v4: (edge * 0.35) + (matchup * 0.20) + (hitRate * 0.20) + (efficiency * 0.10) + (odds * 0.15)
    Then apply lineup and trend modifiers.
    """
    stat = prop.get("stat_name", "").lower()
    line = float(prop.get("line", 0))

    # Determine which average to use for this prop
    player_avg = 0
    stat_lower = stat.lower()

    if "3-pointer" in stat_lower or "3pm" in stat_lower:
        player_avg = averages.get("fg3m", 0)
    elif "point" in stat_lower or "pts" in stat_lower:
        player_avg = averages.get("pts", 0)
    elif "rebound" in stat_lower or "reb" in stat_lower:
        player_avg = averages.get("reb", 0)
    elif "assist" in stat_lower or "ast" in stat_lower:
        player_avg = averages.get("ast", 0)
    elif "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        player_avg = averages.get(
            "pts", 0) + averages.get("reb", 0) + averages.get("ast", 0)

    # Early exit: OUT players get score 0
    if lineup_status == "OUT":
        return 0.0, 0.0, round(player_avg, 1), 0.0, None

    # 1. Edge Score - how much player avg exceeds the line
    edge = player_avg - line if player_avg > 0 else 0
    edge_score = min(10.0, max(0.0, (edge / 5.0) * 10.0))

    # Determine recommendation
    recommended_direction = None
    if player_avg > 0:
        recommended_direction = "Over" if player_avg > line else "Under"

    # 2. Hit Rate Score - consistency in last 5 games
    hit_rate_score = 5.0  # default neutral
    if hit_rate and hit_rate.get("total", 0) > 0:
        hit_pct = hit_rate["hits"] / hit_rate["total"]
        hit_rate_score = hit_pct * 10.0  # 5/5 = 10, 0/5 = 0

    # 3. Player Efficiency Score - stat-aware using advanced stats
    efficiency_score = calculate_player_efficiency_score(stat, player_advanced)

    # 4. Urgency Score (returned but not in formula)
    urgency_score = calculate_urgency_score(game_time_utc)

    # 5. Odds Value Score
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

    # 6. Matchup Score - direction-aware opponent quality
    matchup_score = calculate_matchup_score(opp_def_rank, opp_pace_rank, recommended_direction)

    # Calculate base total score (v4 weights)
    total = (edge_score * 0.35) + (matchup_score * 0.20) + (hit_rate_score * 0.20) + (efficiency_score * 0.10) + (odds_score * 0.15)

    # Apply lineup modifiers
    if lineup_status == "GTD":
        total *= 0.4
    elif lineup_status == "STARTING":
        total = min(10.0, total * 1.1)

    # Apply trend modifier
    if trend_data:
        trend = trend_data.get("trend", "stable")
        if trend == "declining":
            decline_pct = trend_data.get("decline_pct", 0)
            # Penalty up to 30% proportional to decline magnitude
            penalty = min(0.30, decline_pct / 100.0)
            total *= (1.0 - penalty)
        elif trend == "surging":
            total = min(10.0, total * 1.05)

    return total, round(edge, 2), round(player_avg, 1), urgency_score, recommended_direction


def calculate_matchup_score(opp_def_rank: int = None, opp_pace_rank: int = None,
                            direction: str = None) -> float:
    """
    Calculate direction-aware matchup score (0-10) using opponent defense + pace.

    For Over: weak defense (high rank) + fast pace (low rank) = favorable (high score)
    For Under: strong defense (low rank) + slow pace (high rank) = favorable (high score)
    Defense weighted 60%, pace 40%.
    Returns 5.0 (neutral) if direction unknown or data missing.
    """
    if direction is None or (opp_def_rank is None and opp_pace_rank is None):
        return 5.0

    # Default to mid-rank if one is missing
    def_rank = opp_def_rank if opp_def_rank is not None else 15
    pace_rank = opp_pace_rank if opp_pace_rank is not None else 15

    if direction == "Over":
        # Over: high def_rank (weak D) = good, low pace_rank (fast) = good
        defense_component = (def_rank / 30.0) * 10.0
        pace_component = ((31 - pace_rank) / 30.0) * 10.0
    elif direction == "Under":
        # Under: low def_rank (strong D) = good, high pace_rank (slow) = good
        defense_component = ((31 - def_rank) / 30.0) * 10.0
        pace_component = (pace_rank / 30.0) * 10.0
    else:
        return 5.0

    return round((defense_component * 0.60) + (pace_component * 0.40), 2)


def calculate_player_efficiency_score(stat_name: str, player_advanced: dict = None) -> float:
    """
    Calculate stat-aware player efficiency score (0-10) using advanced stats.
    Replaces crude star_score with stat-specific efficiency.

    Points/3PM: USG_PCT (60%) + TS_PCT (40%) — high usage + efficient = high score
    Rebounds:    REB_PCT — high rebound share = high score
    Assists:     AST_PCT — high assist share = high score
    PRA:         Blend: pts(50%) + reb(25%) + ast(25%)

    Returns 5.0 (neutral) if no advanced data available.
    """
    if not player_advanced:
        return 5.0

    def normalize(value, low, high):
        """Normalize value from [low, high] range to [0, 10]."""
        clamped = max(low, min(high, value))
        return ((clamped - low) / (high - low)) * 10.0

    usg = player_advanced.get("usg_pct", 0)
    ts = player_advanced.get("ts_pct", 0)
    reb = player_advanced.get("reb_pct", 0)
    ast = player_advanced.get("ast_pct", 0)

    stat_lower = stat_name.lower()

    if "3-pointer" in stat_lower or "3pm" in stat_lower or "point" in stat_lower or "pts" in stat_lower:
        # Points / 3PM: usage rate + shooting efficiency
        usg_score = normalize(usg, 0.10, 0.35)
        ts_score = normalize(ts, 0.45, 0.70)
        return round((usg_score * 0.60) + (ts_score * 0.40), 2)

    elif "rebound" in stat_lower or "reb" in stat_lower:
        return round(normalize(reb, 0.03, 0.20), 2)

    elif "assist" in stat_lower or "ast" in stat_lower:
        return round(normalize(ast, 0.03, 0.45), 2)

    elif "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        # PRA: weighted blend
        pts_score = (normalize(usg, 0.10, 0.35) * 0.60) + (normalize(ts, 0.45, 0.70) * 0.40)
        reb_score = normalize(reb, 0.03, 0.20)
        ast_score = normalize(ast, 0.03, 0.45)
        return round((pts_score * 0.50) + (reb_score * 0.25) + (ast_score * 0.25), 2)

    return 5.0


def calculate_ranking_score(player_data: dict, props: list, game_time_utc: str,
                            lineup_status: str = "", last5_games: list = None) -> tuple:
    """
    Calculate ranking score for a player (legacy - finds best prop score).
    Returns (total_score, component_scores)
    """
    averages = player_data.get("averages", {"pts": 0, "reb": 0, "ast": 0})

    best_score = 0
    best_components = {"edge": 0, "efficiency": 0, "odds": 0}

    for prop in props:
        stat_name = prop.get("stat_name", "")
        line = float(prop.get("line", 0))

        # Calculate hit rate and trend for this prop
        hit_rate = calculate_hit_rate(last5_games or [], stat_name, line)
        trend_data = calculate_trend_score(last5_games or [], stat_name)

        score, edge, player_avg, urgency, recommended_direction = calculate_prop_ranking_score(
            prop, averages, game_time_utc,
            lineup_status=lineup_status,
            hit_rate=hit_rate,
            trend_data=trend_data
        )
        if score > best_score:
            best_score = score
            best_components = {
                "edge": round(min(10.0, max(0.0, (edge / 5.0) * 10.0)), 2),
                "efficiency": round(calculate_player_efficiency_score(stat_name), 2),
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
    Fetch NBA-ONLY player props from Underdog Fantasy.
    Optimized to filter NBA data early and skip non-NBA processing.
    """
    print("=== Fetching Underdog Fantasy Props (NBA ONLY) ===")

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

    print(f"  Total players (all sports): {len(players_raw)}")
    print(f"  Total lines (all sports): {len(lines)}")

    # EARLY FILTER: Only NBA players
    nba_players = {
        p["id"]: p for p in players_raw if p.get("sport_id") == "NBA"}
    print(f"  NBA players: {len(nba_players)}")

    if not nba_players:
        print("  No NBA players found!")
        return {"players": [], "games": []}

    # EARLY FILTER: Only NBA games
    nba_games = {g["id"]: g for g in games if g.get("sport_id") == "NBA"}
    print(f"  NBA games: {len(nba_games)}")

    # Create appearance -> player mapping (NBA only)
    nba_player_ids = set(nba_players.keys())
    appearance_to_player = {}
    appearance_to_match = {}
    appearance_to_team_id = {}

    for app in appearances:
        player_id = app.get("player_id")
        if player_id in nba_player_ids:
            appearance_to_player[app["id"]] = player_id
            appearance_to_match[app["id"]] = app.get("match_id")
            appearance_to_team_id[app["id"]] = app.get("team_id", "")

    # Build team_id -> abbreviation mapping (NBA games only)
    team_id_to_abbr = {}
    for game in nba_games.values():
        abbr_title = game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away_abbr, home_abbr = abbr_title.split(" @ ")
            away_team_id = game.get("away_team_id")
            home_team_id = game.get("home_team_id")
            if away_team_id:
                team_id_to_abbr[str(away_team_id)] = away_abbr
            if home_team_id:
                team_id_to_abbr[str(home_team_id)] = home_abbr

    # Pre-filter: get NBA appearance IDs for fast lookup
    nba_appearance_ids = set(appearance_to_player.keys())

    # Group lines by player (skip non-NBA lines early)
    players_with_props = {}
    lines_processed = 0
    lines_skipped = 0

    for line in lines:
        if line.get("status") != "active":
            lines_skipped += 1
            continue

        ou = line.get("over_under", {})
        app_stat = ou.get("appearance_stat", {})
        app_id = app_stat.get("appearance_id", "")

        # Skip non-NBA lines immediately
        if app_id not in nba_appearance_ids:
            lines_skipped += 1
            continue

        lines_processed += 1
        player_id = appearance_to_player[app_id]
        player = nba_players[player_id]
        match_id = appearance_to_match.get(app_id)
        team_id = appearance_to_team_id.get(app_id, "")
        game = nba_games.get(match_id, {})

        if player_id not in players_with_props:
            team_abbr = team_id_to_abbr.get(str(team_id), "")
            if not team_abbr and game:
                abbr_title = game.get("abbreviated_title", "")
                if " @ " in abbr_title:
                    away, home = abbr_title.split(" @ ")
                    team_abbr = ""
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

    print(f"  Lines processed (NBA): {lines_processed}")
    print(f"  Lines skipped (non-NBA/inactive): {lines_skipped}")
    print(f"  NBA players with props: {len(players_with_props)}")
    total_props = sum(len(p["props"]) for p in players_with_props.values())
    print(f"  Total NBA props: {total_props}")

    return {
        "players": list(players_with_props.values()),
        "games": list(nba_games.values())
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


def _fuzzy_find_player(player_name: str) -> dict | None:
    """Find an NBA player by name with fuzzy matching fallbacks."""
    from nba_api.stats.static import players as nba_players_db

    # 1. Exact full name match
    results = nba_players_db.find_players_by_full_name(player_name)
    if results:
        return results[0]

    # 2. Try last name only (handles "Nic" vs "Nicolas" etc.)
    parts = player_name.strip().split()
    if len(parts) >= 2:
        last_name = parts[-1]
        first_initial = parts[0][0].lower()
        candidates = nba_players_db.find_players_by_last_name(last_name)
        # Filter to active players whose first name starts with same letter
        active = [p for p in candidates if p.get("is_active") and
                  p["full_name"].split()[0][0].lower() == first_initial]
        if len(active) == 1:
            return active[0]
        # If multiple, try substring match on first name
        if len(active) > 1:
            first_name_lower = parts[0].lower()
            for p in active:
                p_first = p["full_name"].split()[0].lower()
                if p_first.startswith(first_name_lower) or first_name_lower.startswith(p_first):
                    return p

    # 3. Try without suffixes (Jr., III, II, etc.)
    cleaned = player_name.replace(" Jr.", "").replace(" Sr.", "").replace(" III", "").replace(" II", "").replace(" IV", "").strip()
    if cleaned != player_name:
        results = nba_players_db.find_players_by_full_name(cleaned)
        if results:
            return results[0]

    # 4. Try with common suffixes added
    for suffix in [" Jr.", " III", " II"]:
        results = nba_players_db.find_players_by_full_name(player_name + suffix)
        if results:
            return results[0]

    return None


def get_player_stats_quick(player_name: str) -> dict | None:
    """Get basic player stats from NBA API including last 5 games for hit rate."""
    try:
        from nba_api.stats.static import players, teams
        from nba_api.stats.endpoints import playergamelog, commonplayerinfo

        player = _fuzzy_find_player(player_name)
        if not player:
            print(f"  ⚠️ No NBA match for: {player_name}")
            return None

        player_id = player['id']

        position = "N/A"
        current_team = ""
        try:
            player_info = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id)
            info = player_info.get_normalized_dict()['CommonPlayerInfo']
            if info:
                position = str(info[0].get('POSITION', 'N/A'))
                current_team = str(info[0].get('TEAM_ABBREVIATION', ''))
        except:
            pass

        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id, season='2025-26')
            games = log.get_normalized_dict()['PlayerGameLog'][:5]

            if games:
                game_log_team = str(games[0]['MATCHUP'].split(" ")[0])
                # Prefer CommonPlayerInfo team (updated faster after trades)
                team_code = current_team if current_team else game_log_team
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
                    "current_team": current_team,
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
            "team_code": current_team,
            "current_team": current_team,
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


def calculate_trend_score(last5_games: list, stat_name: str) -> dict:
    """
    Compare last 2 games vs 5-game avg for a stat.
    Detects declining or surging usage patterns.
    Returns dict with trend direction, percentages, and recent average.
    """
    if len(last5_games) < 3:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": 0, "full_avg": 0}

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
        stat_key = "pra"

    if not stat_key:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": 0, "full_avg": 0}

    # Get values for all games
    values = []
    for game in last5_games:
        if stat_key == "pra":
            values.append(game.get("pts", 0) + game.get("reb", 0) + game.get("ast", 0))
        else:
            values.append(game.get(stat_key, 0))

    full_avg = sum(values) / len(values) if values else 0
    # Last 2 games (most recent)
    recent_values = values[:2]
    recent_avg = sum(recent_values) / len(recent_values) if recent_values else 0

    if full_avg == 0:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": round(recent_avg, 1), "full_avg": round(full_avg, 1)}

    change_pct = ((recent_avg - full_avg) / full_avg) * 100

    if change_pct <= -20:
        return {"trend": "declining", "decline_pct": round(abs(change_pct), 1), "surge_pct": 0, "recent_avg": round(recent_avg, 1), "full_avg": round(full_avg, 1)}
    elif change_pct >= 20:
        return {"trend": "surging", "decline_pct": 0, "surge_pct": round(change_pct, 1), "recent_avg": round(recent_avg, 1), "full_avg": round(full_avg, 1)}
    else:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": round(recent_avg, 1), "full_avg": round(full_avg, 1)}


def validate_hot_label(card: dict, summary: dict, ai_direction: str) -> str:
    """Cross-check Gemini's 'Strong' confidence against actual data.
    Returns 'hot' only if no counter-signals exist, otherwise 'up'."""

    direction = ai_direction.lower().strip()
    opp_pace_rank = summary.get("opp_pace_rank") or 15
    opp_def_rank = summary.get("opp_def_rank") or 15
    trend = summary.get("trend", "stable")
    edge_pct = summary.get("edge_pct", 0)

    # Parse hit_rate string like "4/5"
    hit_rate_str = summary.get("hit_rate", "0/0")
    try:
        hits, total = hit_rate_str.split("/")
        hits, total = int(hits), int(total)
    except (ValueError, AttributeError):
        hits, total = 0, 0

    if direction == "over":
        if opp_pace_rank > 20:
            return "up"  # slow pace game
        if opp_def_rank < 10:
            return "up"  # elite defense
        if trend == "declining":
            return "up"  # recent production dropping
        if edge_pct < 5:
            return "up"  # not enough edge
        if total > 0 and hits / total < 3 / 5:
            return "up"  # hasn't been clearing line

    elif direction == "under":
        if opp_pace_rank < 10:
            return "up"  # fast pace game
        if opp_def_rank > 20:
            return "up"  # weak defense
        if trend == "surging":
            return "up"  # recent production rising
        if edge_pct > -5:
            return "up"  # not enough under-edge
        if total > 0 and hits / total > 2 / 5:
            return "up"  # has been clearing line

    return "hot"


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

    WORKFLOW:
    1. Scrape all props from Underdog Fantasy
    2. Enrich with NBA API stats
    3. Calculate ranking scores for all props
    4. Build prop cards and WRITE TO FIRESTORE FIRST (ensures data is saved)
    5. Call Gemini 3 Pro for top 10 props only
    6. Update those 10 docs with AI analysis
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

    # 2.5. Fetch team defense stats for matchup analysis (single API call for all 30 teams)
    print("\n📊 Fetching team defense stats for matchup analysis...")
    team_defense_cache = get_all_team_defense_stats()
    print(f"✓ Cached defense stats for {len(team_defense_cache)} teams")

    # 2.55. Fetch player advanced stats (single API call for all ~500 players)
    print("📊 Fetching player advanced stats...")
    player_advanced_cache = get_all_player_advanced_stats()
    print(f"✓ Cached advanced stats for {len(player_advanced_cache)} players")

    # 2.6. Fetch injury reports, back-to-back info, and lineup confirmations
    injuries_cache = get_nba_injuries()
    b2b_cache = get_yesterdays_games()
    lineup_cache = get_todays_lineups()

    print(
        f"\nProcessing {len(underdog_data['players'])} players with props...\n")

    # 3. Enrich with NBA stats (parallel) - SMART SELECTION BY ODDS VALUE
    # Instead of just taking players with most props, prioritize players whose props have good odds
    # This ensures a role player with a +100 line gets enriched over a star with standard -110
    players_to_process = underdog_data["players"]

    # Score all props by odds value and find unique players with best opportunities
    all_props_scored = []
    for player_data in players_to_process:
        player_id = player_data["player"].get("id")
        for prop in player_data.get("props", []):
            try:
                over_odds = int(
                    str(prop.get("over_american", "-110")).replace("+", ""))
            except (ValueError, TypeError):
                over_odds = -110

            # Score: plus money = 100+, near-even = 90-99, standard = 50, bad = 0-49
            if over_odds >= 100:
                odds_score = 100 + over_odds  # +150 = 250 score
            elif over_odds >= -105:
                odds_score = 95
            elif over_odds >= -110:
                odds_score = 50
            elif over_odds >= -115:
                odds_score = 30
            else:
                odds_score = 10

            all_props_scored.append({
                "player_id": player_id,
                "player_data": player_data,
                "odds_score": odds_score,
                "prop": prop
            })

    # Sort by odds value (best opportunities first)
    all_props_scored.sort(key=lambda x: x["odds_score"], reverse=True)

    # Get unique players from best props (preserving order)
    seen_player_ids = set()
    players_by_odds_value = []
    for item in all_props_scored:
        if item["player_id"] not in seen_player_ids:
            seen_player_ids.add(item["player_id"])
            players_by_odds_value.append(item["player_data"])

    # Enrich ALL players with NBA API stats for accurate edge/ranking calculations
    players_to_enrich = players_by_odds_value

    print(
        f"  Will enrich {len(players_to_enrich)} players with NBA API")

    enriched_players = []

    def enrich_player(player_data):
        player = player_data["player"]
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        nba_stats = get_player_stats_quick(player_name)

        return {
            "underdog_player": player,
            "underdog_props": player_data["props"],
            "underdog_game": player_data.get("game", {}),
            "underdog_team_abbr": player_data.get("team_abbr", ""),
            "nba_stats": nba_stats,
            "name": player_name,
        }

    # Enrich all players with NBA API (4 workers to avoid rate limiting)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(enrich_player, p): p["player"].get(
            "id") for p in players_to_enrich}
        for future in as_completed(futures):
            try:
                result = future.result()
                enriched_players.append(result)
                if result.get("nba_stats"):
                    print(f"✓ Enriched {result['name']}")
                else:
                    print(f"○ No NBA data for {result['name']}")
            except Exception as e:
                print(f"✗ Error: {e}")

    print(
        f"\n📊 Processed {len(enriched_players)} total players\n")

    # 4. Calculate ranking scores for all players
    print("📊 Calculating ranking scores...")
    for ep in enriched_players:
        nba_stats = ep.get("nba_stats") or {}
        averages = nba_stats.get(
            "averages", {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0})
        last5_games = nba_stats.get("last5Games", [])
        ud_game = ep.get("underdog_game", {})
        game_time_utc = None
        if ud_game.get("scheduled_at"):
            try:
                game_dt = datetime.datetime.fromisoformat(
                    ud_game["scheduled_at"].replace('Z', '+00:00'))
                game_time_utc = game_dt.isoformat()
            except:
                pass

        # Get lineup status for player-level ranking
        player_name_for_lineup = ep.get("name", "")
        team_abbr_for_lineup = ep.get("underdog_team_abbr", "")
        if nba_stats and nba_stats.get("team_code"):
            team_abbr_for_lineup = nba_stats["team_code"]
        # Validate team against game (handles traded players)
        ud_game_for_lineup = ep.get("underdog_game", {})
        lineup_abbr = ud_game_for_lineup.get("abbreviated_title", "")
        if team_abbr_for_lineup and lineup_abbr and " @ " in lineup_abbr:
            away_l, home_l = lineup_abbr.split(" @ ")
            away_l, home_l = away_l.strip(), home_l.strip()
            if team_abbr_for_lineup not in (away_l, home_l):
                ct = nba_stats.get("current_team", "") if nba_stats else ""
                if ct and ct in (away_l, home_l):
                    team_abbr_for_lineup = ct
        ep_lineup_status = get_player_lineup_status(
            player_name_for_lineup, lineup_cache, injuries_cache, team_abbr_for_lineup)

        # Calculate ranking score with lineup and trend context
        ranking_score, score_components = calculate_ranking_score(
            {"averages": averages},
            ep["underdog_props"],
            game_time_utc,
            lineup_status=ep_lineup_status,
            last5_games=last5_games
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

    # 5. Build individual prop cards (one document per prop)
    # We build these FIRST before AI analysis so data is saved even if Gemini times out
    print("📊 Building individual prop cards...")
    all_prop_cards = []

    # Cache per-team context so teammates reuse the same lookups
    team_context_cache = {}  # team_abbr -> {opponent_abbr, team_injuries, opp_injuries, rest_status, opp_def_stats}

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

        # Validate team_abbr matches the game (handles traded players)
        abbr_title = ud_game.get("abbreviated_title", "")
        if team_abbr and abbr_title and " @ " in abbr_title:
            away_t, home_t = abbr_title.split(" @ ")
            away_t, home_t = away_t.strip(), home_t.strip()
            if team_abbr not in (away_t, home_t):
                # Player's team doesn't match the game - likely traded mid-season
                ct = nba_stats.get("current_team", "") if nba_stats else ""
                if ct and ct in (away_t, home_t):
                    print(f"  ⚠️ Trade fix: {player_name} {team_abbr}->{ct} (game: {abbr_title})")
                    team_abbr = ct
                else:
                    print(f"  ⚠️ Cannot resolve team for {player_name} (team={team_abbr}, game={abbr_title})")
                    team_abbr = away_t

        # Show full matchup
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

        # Create individual prop cards for priority stats only
        priority_stats = ["Points", "Rebounds", "Assists",
                          "3-Pointers Made", "Pts + Rebs + Asts"]

        # Get last 5 games for hit rate calculation
        last5_games = []
        if nba_stats:
            last5_games = nba_stats.get("last5Games", [])

        # Get team context from cache or compute once per team
        if team_abbr and team_abbr in team_context_cache:
            tc = team_context_cache[team_abbr]
            opponent_abbr = tc["opponent_abbr"]
            team_injuries = tc["team_injuries"]
            opp_injuries = tc["opp_injuries"]
            rest_status = tc["rest_status"]
        else:
            opponent_abbr = get_opponent_abbrev(opponent, team_abbr)
            team_injuries = get_team_injuries_summary(team_abbr, injuries_cache)
            opp_injuries = get_team_injuries_summary(opponent_abbr, injuries_cache)
            rest_status = get_player_rest_status(team_abbr, b2b_cache)
            if team_abbr:
                team_context_cache[team_abbr] = {
                    "opponent_abbr": opponent_abbr,
                    "team_injuries": team_injuries,
                    "opp_injuries": opp_injuries,
                    "rest_status": rest_status,
                }

        # Lineup status is always per-player
        lineup_status = get_player_lineup_status(
            player_name, lineup_cache, injuries_cache, team_abbr)

        # Skip OUT players entirely - no prop cards created
        if lineup_status == "OUT":
            continue

        # Look up player advanced stats (type-safe int key)
        player_adv = None
        if isinstance(player_id, int):
            player_adv = player_advanced_cache.get(player_id)
        elif isinstance(player_id, str) and player_id.isdigit():
            player_adv = player_advanced_cache.get(int(player_id))

        for prop in ud_props:
            stat_name = prop.get("stat_name", "")
            # Only include priority stats for cleaner feed
            if stat_name not in priority_stats:
                continue

            # Calculate hit rate and trend BEFORE ranking (needed as inputs)
            line = float(prop.get("line", 0))
            hit_rate = calculate_hit_rate(last5_games, stat_name, line)
            trend_data = calculate_trend_score(last5_games, stat_name)

            # Get opponent defense stats for matchup scoring
            opp_def_stats = team_defense_cache.get(opponent_abbr, {})

            # Calculate ranking score with all context
            prop_score, edge, player_avg, urgency_score, recommended_direction = calculate_prop_ranking_score(
                prop, player_averages, game_time_utc,
                lineup_status=lineup_status,
                hit_rate=hit_rate,
                trend_data=trend_data,
                opp_def_rank=opp_def_stats.get("def_rank"),
                opp_pace_rank=opp_def_stats.get("pace_rank"),
                player_advanced=player_adv
            )

            # Calculate matchup score for prop card (informational)
            matchup_score = calculate_matchup_score(
                opp_def_stats.get("def_rank"),
                opp_def_stats.get("pace_rank"),
                recommended_direction
            )

            # Calculate efficiency score for prop card (informational)
            eff_score = calculate_player_efficiency_score(stat_name, player_adv)

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
                # Matchup data
                "matchupScore": matchup_score,
                "oppDefRank": opp_def_stats.get("def_rank"),
                "oppPaceRank": opp_def_stats.get("pace_rank"),
                # Efficiency data (player advanced stats)
                "efficiencyScore": eff_score,
                "playerAdvanced": {
                    "usgPct": round(player_adv["usg_pct"] * 100, 1) if player_adv else None,
                    "tsPct": round(player_adv["ts_pct"] * 100, 1) if player_adv else None,
                    "rebPct": round(player_adv["reb_pct"] * 100, 1) if player_adv else None,
                    "astPct": round(player_adv["ast_pct"] * 100, 1) if player_adv else None,
                } if player_adv else None,
                # Hit rate data (last 5 games)
                "hitRate": {
                    "hits": hit_rate["hits"],
                    "total": hit_rate["total"],
                    "results": hit_rate["results"]
                },
                # Trend data
                "trendData": {
                    "trend": trend_data.get("trend", "stable"),
                    "declinePct": trend_data.get("decline_pct", 0),
                    "surgePct": trend_data.get("surge_pct", 0),
                    "recentAvg": trend_data.get("recent_avg", 0),
                    "fullAvg": trend_data.get("full_avg", 0),
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
                },
                # Injury and rest data
                "restStatus": rest_status,  # "B2B" or ""
                "teamInjuries": team_injuries,  # "OUT: J. Embiid | GTD: T. Maxey"
                "oppInjuries": opp_injuries,
                "opponentAbbr": opponent_abbr,
                "lineupStatus": lineup_status,  # "STARTING", "GTD", or ""
            }

            all_prop_cards.append(prop_card)

    print(f"📊 Created {len(all_prop_cards)} individual prop cards")

    # 6. Sort and categorize props
    # Sort by ranking score (highest first)
    all_prop_cards.sort(key=lambda x: x.get("rankingScore", 0), reverse=True)

    # "forYou" section: top 5 best-ranked props for 5-leg parlay builders
    for_you_count = min(5, len(all_prop_cards))
    for i, card in enumerate(all_prop_cards[:for_you_count]):
        card["section"] = "forYou"
        card["featured"] = True

    # "topPicks" section: props 6-20 (next best after forYou)
    top_picks_start = for_you_count
    top_picks_end = min(20, len(all_prop_cards))
    top_picks_count = top_picks_end - top_picks_start

    for i, card in enumerate(all_prop_cards[top_picks_start:top_picks_end]):
        card["section"] = "topPicks"
        card["featured"] = True

    # Mark remaining cards as allProps
    for card in all_prop_cards[top_picks_end:]:
        card["section"] = "allProps"
        card["featured"] = False

    print(
        f"✓ Categorized: {for_you_count} forYou (top 5), {top_picks_count} topPicks")

    # 7. Clear old props and write to Firestore FIRST (before AI analysis)
    # This ensures all data is saved even if Gemini times out
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
    print(f"=== DATA SAVED: Wrote {written_count} prop cards to Firestore ===")
    print("="*60 + "\n")

    # 8. NOW run Gemini AI analysis on top 6 props (reduced for quality)
    # This happens AFTER data is saved, so even if it times out, props are preserved
    # Using gemini-2.5-pro for reliability. Change to "gemini-2.5-pro-preview-05-06" for latest.
    google_api_key = os.getenv("GOOGLE_API_KEY")
    ai_updated_count = 0

    if google_api_key:
        try:
            print("🤖 Running Gemini 2.5 Pro analysis on top 6 props...")

            # Get top 6 props for AI analysis (reduced from 10 for quality)
            top_6_cards = all_prop_cards[:6]

            # Build enriched summaries for Gemini with matchup data
            prop_summaries = []
            for card in top_6_cards:
                player_team = card["teamAbbr"]
                # Format: "LAL @ BKN" or similar
                matchup_str = card["opponent"]

                # Extract opponent abbreviation from matchup
                opponent_abbrev = get_opponent_abbrev(matchup_str, player_team)

                # Get opponent defense stats from cache
                opp_stats = team_defense_cache.get(opponent_abbrev, {})

                # Build enriched summary with matchup context + trend data + advanced stats
                trend_info = card.get("trendData", {})
                adv = card.get("playerAdvanced")
                summary = {
                    "player": card["name"],
                    "team": player_team,
                    "stat": card["statNameFull"],
                    "line": card["line"],
                    "player_avg": card["playerAverage"],
                    "recent_avg": trend_info.get("recentAvg", card["playerAverage"]),
                    "edge_pct": round(((card["playerAverage"] - card["line"]) / card["line"]) * 100, 1) if card["line"] > 0 else 0,
                    "hit_rate": f"{card['hitRate']['hits']}/{card['hitRate']['total']}",
                    "trend": trend_info.get("trend", "stable"),
                    "decline_pct": trend_info.get("declinePct", 0),
                    "opponent": opponent_abbrev if opponent_abbrev else matchup_str,
                    "opp_def_rank": opp_stats.get("def_rank"),
                    "opp_pace_rank": opp_stats.get("pace_rank"),
                    # Player advanced stats
                    "usg_pct": adv.get("usgPct") if adv else None,
                    "ts_pct": adv.get("tsPct") if adv else None,
                    "reb_pct": adv.get("rebPct") if adv else None,
                    "ast_pct": adv.get("astPct") if adv else None,
                    # Injury and rest data
                    "rest_status": card.get("restStatus", ""),
                    "team_injuries": card.get("teamInjuries", ""),
                    "opp_injuries": card.get("oppInjuries", ""),
                    "lineup_status": card.get("lineupStatus", ""),
                }
                prop_summaries.append(summary)

            client = genai.Client(api_key=google_api_key)
            prompt = f"""You are an elite NBA handicapper. Analyze each prop using the DECISION FRAMEWORK below.

IMPORTANT: The team data provided below is current and accurate. Players may have been traded recently - trust the team assignments in this data over your training data.

**PROP DATA:**
{json.dumps(prop_summaries, indent=2)}

**METRICS REFERENCE:**
- edge_pct: How much player_avg exceeds line (positive = over edge, negative = under edge)
- recent_avg: Player's average over last 2 games (compare to player_avg to see trend)
- hit_rate: Games over line in last 5 (e.g., "4/5" = hit 4 times)
- trend: "declining" (last 2 games >20% below avg), "surging" (>20% above), or "stable"
- decline_pct: How much production has dropped in recent games (0 if not declining)
- opp_def_rank: 1-30 (1=best defense/hardest, 30=worst defense/easiest)
- opp_pace_rank: 1-30 (1=fastest pace/more possessions, 30=slowest)
- usg_pct: Usage rate % — share of team possessions used while on court (avg ~20%, elite scorers 28-35%)
- ts_pct: True shooting % — scoring efficiency including FTs and 3s (avg ~56%, elite 62%+)
- reb_pct: Rebound % — share of available rebounds grabbed (avg ~10%, elite bigs 18-22%)
- ast_pct: Assist % — share of teammate FGs assisted (avg ~12%, elite playmakers 35-45%)
- rest_status: "B2B" = back-to-back game (fatigue risk), "" = normal rest
- lineup_status: "STARTING" = confirmed starter, "GTD" = game-time decision, "OUT" = ruled out
- team_injuries: Key injuries on player's team (may increase usage if star out)
- opp_injuries: Key injuries on opponent (defensive anchor out = easier matchup)

**DECISION FRAMEWORK - Apply these rules strictly:**

OVER signals:
- edge_pct > 10% = Strong over indicator
- hit_rate 4/5 or 5/5 = Strong recent form
- opp_def_rank 20-30 = Weak defense (boost scoring/counting stats)
- opp_pace_rank 1-10 = Fast pace (more possessions = more stats)
- For Points/3PM: usg_pct > 28% = high-volume scorer, supports Over
- For Rebounds: reb_pct > 15% = dominant rebounder, supports Over
- For Assists: ast_pct > 30% = primary playmaker, supports Over
- opp_injuries contains key defender OUT = easier matchup
- team_injuries shows teammate OUT = potential increased usage
- lineup_status = "STARTING" = confirmed to play

UNDER signals:
- edge_pct < -10% = Strong under indicator
- hit_rate 0/5 or 1/5 = Poor recent form
- opp_def_rank 1-10 = Elite defense (suppresses stats)
- opp_pace_rank 20-30 = Slow pace (fewer possessions)
- For Points/3PM: usg_pct < 18% = low-volume role player, supports Under
- For Rebounds: reb_pct < 8% = not a natural rebounder, supports Under (even if raw avg looks decent)
- For Assists: ast_pct < 10% = not a playmaker, supports Under
- rest_status = "B2B" = fatigue factor (especially for older players or high-minute guys)
- trend = "declining" with decline_pct > 25% = production dropping significantly

CAUTION signals:
- lineup_status = "GTD" = risky, check latest news
- lineup_status = "OUT" = skip this prop entirely
- CRITICAL: When trend = "declining" AND teammates are returning from injury, usage is likely dropping. Use recent_avg instead of player_avg for edge assessment.
- When recent_avg is significantly lower than player_avg (>20% gap), the season average is misleading. Weight recent_avg more heavily.
- When lineup_status = "" (unknown) AND player_avg < 15 pts (low production), be skeptical - bench players may not play starter minutes.
- ROSTER CHANGES: Use your knowledge of recent trades and acquisitions. A new teammate at the same position or role can cannibalize stats (e.g., a new center reduces rebounding shares for wings, a new ball-handler reduces assists for existing guards). If a recent roster addition likely impacts the stat being propped, factor that into your direction and confidence.
- INDIVIDUAL MATCHUPS: Consider the likely primary defender based on position. A player going against an elite perimeter defender (e.g., for 3PM/Points props) or a strong interior defender (e.g., for Rebounds props) is a counter-signal for Over, even if the team defense rank is weak overall. Mention the specific defender in your analysis when relevant.

CONFIDENCE LEVELS:
- "Strong": 3+ signals align in same direction AND NO significant counter-signals (e.g., recommending Over but pace is slow, or defense is elite) AND player confirmed to play. If any counter-signal exists, use "Lean" instead.
- "Lean": 2 signals align, or edge_pct > 15%
- "Fade": Signals conflict OR edge_pct between -5% and 5% OR lineup uncertain OR trend is declining with high decline_pct

**OUTPUT (JSON):**
{{
    "props": [
        {{
            "player": "Exact Player Name",
            "stat": "Points|Rebounds|Assists|3-Pointers Made|Pts + Rebs + Asts",
            "direction": "Over" or "Under",
            "confidence": "Strong" or "Lean" or "Fade",
            "analysis": "[2-3 sentences citing specific numbers. Mention trend/recent_avg, lineup status, and roster changes (trades/new teammates) if they impact the stat. End with clear verdict.]"
        }}
    ]
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                }
            )
            ai_results = json.loads(response.text)
            ai_props = ai_results.get("props", [])
            print(
                f"✓ Gemini analysis complete - received {len(ai_props)} analyses")

            # Helper to normalize stat names for flexible matching
            def normalize_stat(stat: str) -> str:
                stat = stat.lower().strip()
                if stat in ["pts", "points", "point"]:
                    return "points"
                if stat in ["reb", "rebs", "rebounds", "rebound"]:
                    return "rebounds"
                if stat in ["ast", "asts", "assists", "assist"]:
                    return "assists"
                if stat in ["3pm", "3-pointers made", "3-pointers", "threes", "3 pointers made"]:
                    return "3-pointers made"
                if stat in ["pra", "pts + rebs + asts", "points + rebounds + assists"]:
                    return "pts + rebs + asts"
                return stat

            # Build lookup dict from prop_summaries for hot label validation
            summary_lookup = {}
            for s in prop_summaries:
                key = (s["player"].lower().strip(), normalize_stat(s["stat"]))
                summary_lookup[key] = s

            # Update the top props in Firestore with AI analysis
            for p in ai_props:
                player_name = p.get("player", "").lower().strip()
                stat_name = normalize_stat(p.get("stat", ""))
                analysis = p.get("analysis", "")

                # Find matching card and update in Firestore
                matched = False
                for card in top_6_cards:
                    card_player = card["name"].lower().strip()
                    card_stat = normalize_stat(card["statNameFull"])

                    if card_player == player_name and card_stat == stat_name:
                        doc_id = card["id"]
                        ai_direction = p.get("direction", "Over")
                        ai_confidence = p.get("confidence", "Lean")

                        # Map confidence to trending with cross-check validation
                        if ai_confidence == "Strong":
                            summary = summary_lookup.get((player_name, stat_name), {})
                            trending = validate_hot_label(card, summary, ai_direction)
                        elif ai_confidence == "Fade":
                            trending = "fade"
                        else:
                            trending = "up"

                        update_data = {
                            "trending": trending,
                            "ai_analysis": analysis,
                            "aiRecommended": ai_direction,
                            "aiConfidence": ai_confidence,
                            "isFade": ai_confidence == "Fade",
                        }

                        db.collection("props").document(
                            doc_id).update(update_data)
                        ai_updated_count += 1
                        matched = True
                        print(
                            f"  ✓ Updated: {card['name']} - {card['statNameFull']} ({ai_confidence} {ai_direction})")
                        break

                if not matched:
                    print(
                        f"  ✗ No match: {player_name} / {p.get('stat', 'unknown')}")

            print(
                f"✓ AI analysis matched {ai_updated_count}/{len(ai_props)} props")

        except Exception as e:
            print(f"⚠️ Gemini error (props already saved without AI): {e}")

    print(f"\n{'='*60}")
    print(
        f"=== COMPLETE: {written_count} props, {ai_updated_count} with AI ===")
    print(f"=== Top Picks: {top_picks_count}, For You: {for_you_count} ===")
    print("="*60 + "\n")

    # Write refresh metadata so iOS app knows when data was last updated
    db.collection("metadata").document("lastRefresh").set({
        "completedAt": firestore.SERVER_TIMESTAMP,
        "propsWritten": written_count,
        "aiAnalyzed": ai_updated_count,
        "topPicks": top_picks_count,
        "forYou": for_you_count,
        "source": "batch_analyze",
    })

    return https_fn.Response(json.dumps({
        "status": "success",
        "message": f"Created {written_count} individual prop cards",
        "props_written": written_count,
        "top_picks": top_picks_count,
        "for_you": for_you_count,
        "ai_analyzed": ai_updated_count,
        "source": "underdog_fantasy",
        "espn_games_today": len(espn_games)
    }), mimetype='application/json')


# ============================================================
# SCHEDULED FUNCTION - Runs automatically via Cloud Scheduler
# ============================================================

@scheduler_fn.on_schedule(
    schedule="0 0-1,6-23 * * *",
    timezone=scheduler_fn.Timezone("America/Los_Angeles"),
    secrets=["GOOGLE_API_KEY"],
    timeout_sec=540,
    memory=1024
)
def scheduled_refresh(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Automatically refresh all player props hourly.
    Includes player stat enrichment, team defense stats, and AI analysis.
    Creates individual prop cards (one document per prop).
    """
    print("\n" + "="*60)
    print("=== SCHEDULED REFRESH - UNDERDOG + ESPN + AI ===")
    print(f"=== Time: {datetime.datetime.now().isoformat()} ===")
    print("="*60 + "\n")

    underdog_data = get_underdog_nba_props()
    if not underdog_data["players"]:
        print("No NBA props available")
        return

    espn_games = get_espn_nba_schedule()

    # Fetch team defense stats for matchup analysis (single API call)
    print("\n📊 Fetching team defense stats for matchup analysis...")
    team_defense_cache = get_all_team_defense_stats()
    print(f"✓ Cached defense stats for {len(team_defense_cache)} teams")

    # Fetch player advanced stats (single API call for all ~500 players)
    print("📊 Fetching player advanced stats...")
    player_advanced_cache = get_all_player_advanced_stats()
    print(f"✓ Cached advanced stats for {len(player_advanced_cache)} players")

    # Fetch injury reports, back-to-back info, and lineup confirmations
    injuries_cache = get_nba_injuries()
    b2b_cache = get_yesterdays_games()
    lineup_cache = get_todays_lineups()

    db = firestore.client()

    # Enrich players with NBA stats - SMART SELECTION BY ODDS VALUE
    # Prioritize players whose props have good odds (plus money or near-even)
    print(
        f"\nProcessing {len(underdog_data['players'])} players with props...")
    players_to_process = underdog_data["players"]

    # Score all props by odds value and find unique players with best opportunities
    all_props_scored = []
    for player_data in players_to_process:
        player_id = player_data["player"].get("id")
        for prop in player_data.get("props", []):
            try:
                over_odds = int(
                    str(prop.get("over_american", "-110")).replace("+", ""))
            except (ValueError, TypeError):
                over_odds = -110

            # Score: plus money = 100+, near-even = 90-99, standard = 50, bad = 0-49
            if over_odds >= 100:
                odds_score = 100 + over_odds
            elif over_odds >= -105:
                odds_score = 95
            elif over_odds >= -110:
                odds_score = 50
            elif over_odds >= -115:
                odds_score = 30
            else:
                odds_score = 10

            all_props_scored.append({
                "player_id": player_id,
                "player_data": player_data,
                "odds_score": odds_score
            })

    # Sort by odds value (best opportunities first)
    all_props_scored.sort(key=lambda x: x["odds_score"], reverse=True)

    # Get unique players from best props
    seen_player_ids = set()
    players_by_odds_value = []
    for item in all_props_scored:
        if item["player_id"] not in seen_player_ids:
            seen_player_ids.add(item["player_id"])
            players_by_odds_value.append(item["player_data"])

    # Enrich ALL players with NBA API stats
    players_to_enrich = players_by_odds_value

    print(
        f"  Will enrich {len(players_to_enrich)} players with NBA API")

    enriched_players = []

    def enrich_player(player_data):
        player = player_data["player"]
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        nba_stats = get_player_stats_quick(player_name)
        return {
            "underdog_player": player,
            "underdog_props": player_data["props"],
            "underdog_game": player_data.get("game", {}),
            "underdog_team_abbr": player_data.get("team_abbr", ""),
            "nba_stats": nba_stats,
            "name": player_name,
        }

    # Enrich all players with NBA API (4 workers to avoid rate limiting)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(enrich_player, p): p["player"].get(
            "id") for p in players_to_enrich}
        for future in as_completed(futures):
            try:
                result = future.result()
                enriched_players.append(result)
                if result.get("nba_stats"):
                    print(f"✓ Enriched {result['name']}")
                else:
                    print(f"○ No NBA data for {result['name']}")
            except Exception as e:
                print(f"✗ Error: {e}")

    print(f"\n📊 Processed {len(enriched_players)} total players\n")

    # Calculate ranking scores
    for ep in enriched_players:
        nba_stats = ep.get("nba_stats") or {}
        averages = nba_stats.get(
            "averages", {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0})
        last5_games = nba_stats.get("last5Games", [])
        ud_game = ep.get("underdog_game", {})
        game_time_utc = None
        if ud_game.get("scheduled_at"):
            try:
                game_dt = datetime.datetime.fromisoformat(
                    ud_game["scheduled_at"].replace('Z', '+00:00'))
                game_time_utc = game_dt.isoformat()
            except:
                pass

        # Get lineup status for player-level ranking
        player_name_for_lineup = ep.get("name", "")
        team_abbr_for_lineup = ep.get("underdog_team_abbr", "")
        if nba_stats and nba_stats.get("team_code"):
            team_abbr_for_lineup = nba_stats["team_code"]
        # Validate team against game (handles traded players)
        lineup_abbr = ud_game.get("abbreviated_title", "")
        if team_abbr_for_lineup and lineup_abbr and " @ " in lineup_abbr:
            away_l, home_l = lineup_abbr.split(" @ ")
            away_l, home_l = away_l.strip(), home_l.strip()
            if team_abbr_for_lineup not in (away_l, home_l):
                ct = nba_stats.get("current_team", "") if nba_stats else ""
                if ct and ct in (away_l, home_l):
                    team_abbr_for_lineup = ct
        ep_lineup_status = get_player_lineup_status(
            player_name_for_lineup, lineup_cache, injuries_cache, team_abbr_for_lineup)

        ranking_score, score_components = calculate_ranking_score(
            {"averages": averages}, ep["underdog_props"], game_time_utc,
            lineup_status=ep_lineup_status, last5_games=last5_games)
        ep["ranking_score"] = ranking_score
        ep["player_averages"] = averages

    # Sort by ranking score
    enriched_players.sort(key=lambda x: x.get(
        "ranking_score", 0), reverse=True)

    # Build individual prop cards
    all_prop_cards = []
    priority_stats = ["Points", "Rebounds", "Assists",
                      "3-Pointers Made", "Pts + Rebs + Asts"]

    # Cache per-team context so teammates reuse the same lookups
    team_context_cache = {}

    for ep in enriched_players:
        ud_player = ep["underdog_player"]
        ud_props = ep["underdog_props"]
        ud_game = ep.get("underdog_game", {})
        nba_stats = ep.get("nba_stats")
        player_averages = ep.get(
            "player_averages", {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0})

        # Get player info
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
            if not team_abbr:
                abbr_title = ud_game.get("abbreviated_title", "")
                if " @ " in abbr_title:
                    away, home = abbr_title.split(" @ ")
                    team_abbr = away
            position = ud_player.get("position_name", "N/A")
            image_url = ud_player.get("image_url", "")
            if nba_stats and nba_stats.get("image"):
                image_url = nba_stats["image"]

        # Validate team_abbr matches the game (handles traded players)
        abbr_title = ud_game.get("abbreviated_title", "")
        if team_abbr and abbr_title and " @ " in abbr_title:
            away_t, home_t = abbr_title.split(" @ ")
            away_t, home_t = away_t.strip(), home_t.strip()
            if team_abbr not in (away_t, home_t):
                ct = nba_stats.get("current_team", "") if nba_stats else ""
                if ct and ct in (away_t, home_t):
                    print(f"  ⚠️ Trade fix: {player_name} {team_abbr}->{ct} (game: {abbr_title})")
                    team_abbr = ct
                else:
                    print(f"  ⚠️ Cannot resolve team for {player_name} (team={team_abbr}, game={abbr_title}), using {away_t}")
                    team_abbr = away_t

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

        # Get last 5 games for hit rate
        last5_games = nba_stats.get("last5Games", []) if nba_stats else []

        # Get team context from cache or compute once per team
        if team_abbr and team_abbr in team_context_cache:
            tc = team_context_cache[team_abbr]
            opponent_abbr = tc["opponent_abbr"]
            team_injuries = tc["team_injuries"]
            opp_injuries = tc["opp_injuries"]
            rest_status = tc["rest_status"]
        else:
            opponent_abbr = get_opponent_abbrev(opponent, team_abbr)
            team_injuries = get_team_injuries_summary(team_abbr, injuries_cache)
            opp_injuries = get_team_injuries_summary(opponent_abbr, injuries_cache)
            rest_status = get_player_rest_status(team_abbr, b2b_cache)
            if team_abbr:
                team_context_cache[team_abbr] = {
                    "opponent_abbr": opponent_abbr,
                    "team_injuries": team_injuries,
                    "opp_injuries": opp_injuries,
                    "rest_status": rest_status,
                }

        # Lineup status is always per-player
        lineup_status = get_player_lineup_status(
            player_name, lineup_cache, injuries_cache, team_abbr)

        # Skip OUT players entirely - no prop cards created
        if lineup_status == "OUT":
            continue

        # Look up player advanced stats (type-safe int key)
        player_adv = None
        if isinstance(player_id, int):
            player_adv = player_advanced_cache.get(player_id)
        elif isinstance(player_id, str) and player_id.isdigit():
            player_adv = player_advanced_cache.get(int(player_id))

        for prop in ud_props:
            stat_name = prop.get("stat_name", "")
            if stat_name not in priority_stats:
                continue

            # Calculate hit rate and trend BEFORE ranking (needed as inputs)
            line = float(prop.get("line", 0))
            hit_rate = calculate_hit_rate(last5_games, stat_name, line)
            trend_data = calculate_trend_score(last5_games, stat_name)

            # Get opponent defense stats for matchup scoring
            opp_def_stats = team_defense_cache.get(opponent_abbr, {})

            # Calculate ranking score with all context
            prop_score, edge, player_avg, urgency_score, recommended_direction = calculate_prop_ranking_score(
                prop, player_averages, game_time_utc,
                lineup_status=lineup_status,
                hit_rate=hit_rate,
                trend_data=trend_data,
                opp_def_rank=opp_def_stats.get("def_rank"),
                opp_pace_rank=opp_def_stats.get("pace_rank"),
                player_advanced=player_adv
            )

            # Calculate matchup score for prop card (informational)
            matchup_score = calculate_matchup_score(
                opp_def_stats.get("def_rank"),
                opp_def_stats.get("pace_rank"),
                recommended_direction
            )

            # Calculate efficiency score for prop card (informational)
            eff_score = calculate_player_efficiency_score(stat_name, player_adv)

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
                # Matchup data
                "matchupScore": matchup_score,
                "oppDefRank": opp_def_stats.get("def_rank"),
                "oppPaceRank": opp_def_stats.get("pace_rank"),
                # Efficiency data (player advanced stats)
                "efficiencyScore": eff_score,
                "playerAdvanced": {
                    "usgPct": round(player_adv["usg_pct"] * 100, 1) if player_adv else None,
                    "tsPct": round(player_adv["ts_pct"] * 100, 1) if player_adv else None,
                    "rebPct": round(player_adv["reb_pct"] * 100, 1) if player_adv else None,
                    "astPct": round(player_adv["ast_pct"] * 100, 1) if player_adv else None,
                } if player_adv else None,
                "hitRate": {"hits": hit_rate["hits"], "total": hit_rate["total"], "results": hit_rate["results"]},
                # Trend data
                "trendData": {
                    "trend": trend_data.get("trend", "stable"),
                    "declinePct": trend_data.get("decline_pct", 0),
                    "surgePct": trend_data.get("surge_pct", 0),
                    "recentAvg": trend_data.get("recent_avg", 0),
                    "fullAvg": trend_data.get("full_avg", 0),
                },
                "section": "topPicks",
                "featured": False,
                "trending": "up",
                "ai_analysis": "",
                "playerAverages": {
                    "pts": player_averages.get("pts", 0),
                    "reb": player_averages.get("reb", 0),
                    "ast": player_averages.get("ast", 0),
                    "fg3m": player_averages.get("fg3m", 0)
                },
                # Injury and rest data
                "restStatus": rest_status,
                "teamInjuries": team_injuries,
                "oppInjuries": opp_injuries,
                "opponentAbbr": opponent_abbr,
                "lineupStatus": lineup_status,  # "STARTING", "GTD", or ""
            }
            all_prop_cards.append(prop_card)

    print(f"📊 Created {len(all_prop_cards)} individual prop cards")

    # Sort and categorize
    all_prop_cards.sort(key=lambda x: x.get("rankingScore", 0), reverse=True)

    for_you_count = min(5, len(all_prop_cards))
    for i, card in enumerate(all_prop_cards[:for_you_count]):
        card["section"] = "forYou"
        card["featured"] = True

    top_picks_start = for_you_count
    top_picks_end = min(20, len(all_prop_cards))
    top_picks_count = top_picks_end - top_picks_start

    for card in all_prop_cards[top_picks_start:top_picks_end]:
        card["section"] = "topPicks"
        card["featured"] = True

    for card in all_prop_cards[top_picks_end:]:
        card["section"] = "allProps"
        card["featured"] = False

    # Clear old props and write new ones
    print("🗑️  Clearing old props collection...")
    props_ref = db.collection("props")
    old_docs = list(props_ref.stream())
    for doc in old_docs:
        doc.reference.delete()
    print(f"🗑️  Deleted {len(old_docs)} old documents")

    # Write to Firestore
    for card in all_prop_cards:
        doc_id = f"{card['player_id']}_{card['statName'].lower().replace(' ', '_')}"
        card["id"] = doc_id
        db.collection("props").document(doc_id).set(card)

    print(f"\n{'='*60}")
    print(f"=== DATA SAVED: Wrote {len(all_prop_cards)} prop cards ===")
    print("="*60 + "\n")

    # Run Gemini AI analysis on top 6 props
    google_api_key = os.getenv("GOOGLE_API_KEY")
    ai_updated_count = 0

    if google_api_key:
        try:
            print("🤖 Running Gemini 2.5 Pro analysis on top 6 props...")

            top_6_cards = all_prop_cards[:6]

            prop_summaries = []
            for card in top_6_cards:
                player_team = card["teamAbbr"]
                matchup_str = card["opponent"]
                opponent_abbrev = get_opponent_abbrev(matchup_str, player_team)
                opp_stats = team_defense_cache.get(opponent_abbrev, {})

                trend_info = card.get("trendData", {})
                adv = card.get("playerAdvanced")
                summary = {
                    "player": card["name"],
                    "team": player_team,
                    "stat": card["statNameFull"],
                    "line": card["line"],
                    "player_avg": card["playerAverage"],
                    "recent_avg": trend_info.get("recentAvg", card["playerAverage"]),
                    "edge_pct": round(((card["playerAverage"] - card["line"]) / card["line"]) * 100, 1) if card["line"] > 0 else 0,
                    "hit_rate": f"{card['hitRate']['hits']}/{card['hitRate']['total']}",
                    "trend": trend_info.get("trend", "stable"),
                    "decline_pct": trend_info.get("declinePct", 0),
                    "opponent": opponent_abbrev if opponent_abbrev else matchup_str,
                    "opp_def_rank": opp_stats.get("def_rank"),
                    "opp_pace_rank": opp_stats.get("pace_rank"),
                    # Player advanced stats
                    "usg_pct": adv.get("usgPct") if adv else None,
                    "ts_pct": adv.get("tsPct") if adv else None,
                    "reb_pct": adv.get("rebPct") if adv else None,
                    "ast_pct": adv.get("astPct") if adv else None,
                    # Injury and rest data
                    "rest_status": card.get("restStatus", ""),
                    "team_injuries": card.get("teamInjuries", ""),
                    "opp_injuries": card.get("oppInjuries", ""),
                    "lineup_status": card.get("lineupStatus", ""),
                }
                prop_summaries.append(summary)

            client = genai.Client(api_key=google_api_key)
            prompt = f"""You are an elite NBA handicapper. Analyze each prop using the DECISION FRAMEWORK below.

IMPORTANT: The team data provided below is current and accurate. Players may have been traded recently - trust the team assignments in this data over your training data.

**PROP DATA:**
{json.dumps(prop_summaries, indent=2)}

**METRICS REFERENCE:**
- edge_pct: How much player_avg exceeds line (positive = over edge, negative = under edge)
- recent_avg: Player's average over last 2 games (compare to player_avg to see trend)
- hit_rate: Games over line in last 5 (e.g., "4/5" = hit 4 times)
- trend: "declining" (last 2 games >20% below avg), "surging" (>20% above), or "stable"
- decline_pct: How much production has dropped in recent games (0 if not declining)
- opp_def_rank: 1-30 (1=best defense/hardest, 30=worst defense/easiest)
- opp_pace_rank: 1-30 (1=fastest pace/more possessions, 30=slowest)
- usg_pct: Usage rate % — share of team possessions used while on court (avg ~20%, elite scorers 28-35%)
- ts_pct: True shooting % — scoring efficiency including FTs and 3s (avg ~56%, elite 62%+)
- reb_pct: Rebound % — share of available rebounds grabbed (avg ~10%, elite bigs 18-22%)
- ast_pct: Assist % — share of teammate FGs assisted (avg ~12%, elite playmakers 35-45%)
- rest_status: "B2B" = back-to-back game (fatigue risk), "" = normal rest
- lineup_status: "STARTING" = confirmed starter, "GTD" = game-time decision, "OUT" = ruled out
- team_injuries: Key injuries on player's team (may increase usage if star out)
- opp_injuries: Key injuries on opponent (defensive anchor out = easier matchup)

**DECISION FRAMEWORK - Apply these rules strictly:**

OVER signals:
- edge_pct > 10% = Strong over indicator
- hit_rate 4/5 or 5/5 = Strong recent form
- opp_def_rank 20-30 = Weak defense (boost scoring/counting stats)
- opp_pace_rank 1-10 = Fast pace (more possessions = more stats)
- For Points/3PM: usg_pct > 28% = high-volume scorer, supports Over
- For Rebounds: reb_pct > 15% = dominant rebounder, supports Over
- For Assists: ast_pct > 30% = primary playmaker, supports Over
- opp_injuries contains key defender OUT = easier matchup
- team_injuries shows teammate OUT = potential increased usage
- lineup_status = "STARTING" = confirmed to play

UNDER signals:
- edge_pct < -10% = Strong under indicator
- hit_rate 0/5 or 1/5 = Poor recent form
- opp_def_rank 1-10 = Elite defense (suppresses stats)
- opp_pace_rank 20-30 = Slow pace (fewer possessions)
- For Points/3PM: usg_pct < 18% = low-volume role player, supports Under
- For Rebounds: reb_pct < 8% = not a natural rebounder, supports Under (even if raw avg looks decent)
- For Assists: ast_pct < 10% = not a playmaker, supports Under
- rest_status = "B2B" = fatigue factor (especially for older players or high-minute guys)
- trend = "declining" with decline_pct > 25% = production dropping significantly

CAUTION signals:
- lineup_status = "GTD" = risky, check latest news
- lineup_status = "OUT" = skip this prop entirely
- CRITICAL: When trend = "declining" AND teammates are returning from injury, usage is likely dropping. Use recent_avg instead of player_avg for edge assessment.
- When recent_avg is significantly lower than player_avg (>20% gap), the season average is misleading. Weight recent_avg more heavily.
- When lineup_status = "" (unknown) AND player_avg < 15 pts (low production), be skeptical - bench players may not play starter minutes.
- ROSTER CHANGES: Use your knowledge of recent trades and acquisitions. A new teammate at the same position or role can cannibalize stats (e.g., a new center reduces rebounding shares for wings, a new ball-handler reduces assists for existing guards). If a recent roster addition likely impacts the stat being propped, factor that into your direction and confidence.
- INDIVIDUAL MATCHUPS: Consider the likely primary defender based on position. A player going against an elite perimeter defender (e.g., for 3PM/Points props) or a strong interior defender (e.g., for Rebounds props) is a counter-signal for Over, even if the team defense rank is weak overall. Mention the specific defender in your analysis when relevant.

CONFIDENCE LEVELS:
- "Strong": 3+ signals align in same direction AND NO significant counter-signals (e.g., recommending Over but pace is slow, or defense is elite) AND player confirmed to play. If any counter-signal exists, use "Lean" instead.
- "Lean": 2 signals align, or edge_pct > 15%
- "Fade": Signals conflict OR edge_pct between -5% and 5% OR lineup uncertain OR trend is declining with high decline_pct

**OUTPUT (JSON):**
{{
    "props": [
        {{
            "player": "Exact Player Name",
            "stat": "Points|Rebounds|Assists|3-Pointers Made|Pts + Rebs + Asts",
            "direction": "Over" or "Under",
            "confidence": "Strong" or "Lean" or "Fade",
            "analysis": "[2-3 sentences citing specific numbers. Mention trend/recent_avg, lineup status, and roster changes (trades/new teammates) if they impact the stat. End with clear verdict.]"
        }}
    ]
}}"""

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                }
            )
            ai_results = json.loads(response.text)
            ai_props = ai_results.get("props", [])
            print(
                f"✓ Gemini analysis complete - received {len(ai_props)} analyses")

            def normalize_stat(stat: str) -> str:
                stat = stat.lower().strip()
                if stat in ["pts", "points", "point"]:
                    return "points"
                if stat in ["reb", "rebs", "rebounds", "rebound"]:
                    return "rebounds"
                if stat in ["ast", "asts", "assists", "assist"]:
                    return "assists"
                if stat in ["3pm", "3-pointers made", "3-pointers", "threes", "3 pointers made"]:
                    return "3-pointers made"
                if stat in ["pra", "pts + rebs + asts", "points + rebounds + assists"]:
                    return "pts + rebs + asts"
                return stat

            # Build lookup dict from prop_summaries for hot label validation
            summary_lookup = {}
            for s in prop_summaries:
                key = (s["player"].lower().strip(), normalize_stat(s["stat"]))
                summary_lookup[key] = s

            for p in ai_props:
                player_name = p.get("player", "").lower().strip()
                stat_name = normalize_stat(p.get("stat", ""))
                analysis = p.get("analysis", "")

                for card in top_6_cards:
                    card_player = card["name"].lower().strip()
                    card_stat = normalize_stat(card["statNameFull"])

                    if card_player == player_name and card_stat == stat_name:
                        doc_id = card["id"]
                        ai_direction = p.get("direction", "Over")
                        ai_confidence = p.get("confidence", "Lean")

                        # Map confidence to trending with cross-check validation
                        if ai_confidence == "Strong":
                            summary = summary_lookup.get((player_name, stat_name), {})
                            trending = validate_hot_label(card, summary, ai_direction)
                        elif ai_confidence == "Fade":
                            trending = "fade"
                        else:
                            trending = "up"

                        update_data = {
                            "trending": trending,
                            "ai_analysis": analysis,
                            "aiRecommended": ai_direction,
                            "aiConfidence": ai_confidence,
                            "isFade": ai_confidence == "Fade",
                        }

                        db.collection("props").document(
                            doc_id).update(update_data)
                        ai_updated_count += 1
                        print(
                            f"  ✓ Updated: {card['name']} - {card['statNameFull']} ({ai_confidence} {ai_direction})")
                        break

            print(
                f"✓ AI analysis matched {ai_updated_count}/{len(ai_props)} props")

        except Exception as e:
            print(f"⚠️ Gemini error (props already saved without AI): {e}")

    print(f"\n{'='*60}")
    print(
        f"=== SCHEDULED REFRESH COMPLETE: {len(all_prop_cards)} props, {ai_updated_count} with AI ===")
    print(f"=== Top Picks: {top_picks_count}, For You: {for_you_count} ===")
    print("="*60 + "\n")

    # Write refresh metadata so iOS app knows when data was last updated
    db.collection("metadata").document("lastRefresh").set({
        "completedAt": firestore.SERVER_TIMESTAMP,
        "propsWritten": len(all_prop_cards),
        "aiAnalyzed": ai_updated_count,
        "topPicks": top_picks_count,
        "forYou": for_you_count,
        "source": "scheduled_refresh",
    })
