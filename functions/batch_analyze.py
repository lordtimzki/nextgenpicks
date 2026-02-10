"""
Batch Analyze Cloud Function - Underdog Fantasy + ESPN Version
Fetches player props from Underdog Fantasy (free API, no auth required)
Uses ESPN for game schedules
"""

from firebase_functions import https_fn, scheduler_fn
from firebase_admin import firestore
import httpx
import json
import datetime
import uuid
from datetime import timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from retrieve import get_all_team_defense_stats, get_all_player_advanced_stats, get_all_player_bio_stats, get_all_team_opponent_stats

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
        "UTAH": "UTA", "WSH": "WAS"
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
        "UTAH": "UTA", "WSH": "WAS"
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
        "UTAH": "UTA", "WSH": "WAS"
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



def calculate_prop_ranking_score(prop: dict, averages: dict, game_time_utc: str,
                                  lineup_status: str = "", hit_rate: dict = None,
                                  trend_data: dict = None,
                                  opp_def_rank: int = None,
                                  opp_pace_rank: int = None,
                                  player_advanced: dict = None,
                                  is_home: bool = None,
                                  game_log: list = None,
                                  usage_vacuum_modifier: float = 1.0,
                                  opp_stat_rank: int = None) -> tuple:
    """
    Calculate ranking score for a SINGLE prop.
    Returns (total_score, edge_value, player_average_for_stat, urgency_score,
             recommended_direction, ha_modifier, min_modifier)

    Formula v6: 
    - Scale-invariant Edge Scoring
    - Direction-aware modifiers (minutes, lineup, usage vacuum)
    - Matchup weighting (v5 base)
    """
    stat = prop.get("stat_name", "")
    line = float(prop.get("line", 0))

    # Determine which average to use for this prop
    stat_key = _resolve_stat_key(stat)
    if stat_key == "pra":
        player_avg = averages.get("pts", 0) + averages.get("reb", 0) + averages.get("ast", 0)
    elif stat_key:
        player_avg = averages.get(stat_key, 0)
    else:
        player_avg = 0

    # Early exit: OUT players get score 0
    if lineup_status == "OUT":
        return 0.0, 0.0, round(player_avg, 1), 0.0, None, 1.0, 1.0

    # 1. Edge Score - Scale-Invariant (Percentage based)
    edge = player_avg - line if player_avg > 0 else 0
    
    # Avoid division by zero
    safe_line = line if line > 0.1 else 1.0
    pct_edge = abs(edge) / safe_line
    
    # 25% edge = 10.0 score. (0.25 * 40 = 10)
    edge_score = min(10.0, pct_edge * 40.0)

    # Determine recommendation
    recommended_direction = None
    if player_avg > 0:
        recommended_direction = "Over" if player_avg > line else "Under"

    # 2. Hit Rate Score
    hit_rate_score = 5.0  # default neutral
    if hit_rate and hit_rate.get("total", 0) > 0:
        weighted_pct = hit_rate.get("weightedPct", hit_rate["hits"] / hit_rate["total"])
        directional_pct = (1.0 - weighted_pct) if recommended_direction == "Under" else weighted_pct
        hit_rate_score = directional_pct * 10.0

    # 3. Player Efficiency Score
    efficiency_score = calculate_player_efficiency_score(stat, player_advanced)

    # 4. Urgency Score
    urgency_score = calculate_urgency_score(game_time_utc)

    # 5. Odds Value Score
    over_odds_val = _parse_odds(prop.get("over_american", "-110"))
    under_odds_val = _parse_odds(prop.get("under_american", "-110"))
    relevant_odds = under_odds_val if recommended_direction == "Under" else over_odds_val
    odds_score = _odds_tier_score(relevant_odds)

    # 6. Matchup Score (stat-specific when available)
    matchup_score = calculate_matchup_score(opp_def_rank, opp_pace_rank, recommended_direction, opp_stat_rank=opp_stat_rank)

    # Boost matchup weight if extreme outlier (redistribute from edge to keep sum = 1.0)
    # Use stat-specific rank for boost check when available
    effective_def_rank = opp_stat_rank if opp_stat_rank is not None else opp_def_rank
    matchup_weight = 0.20
    edge_weight = 0.35
    if (effective_def_rank and effective_def_rank >= 28 and recommended_direction == "Over") or \
       (effective_def_rank and effective_def_rank <= 3 and recommended_direction == "Under"):
        matchup_weight = 0.25
        edge_weight = 0.30

    # Calculate base total score (v6 weights)
    # Base: Edge 35%, HitRate 20%, Matchup 20%, Odds 15%, Eff 10%
    # Extreme matchup: Edge 30%, Matchup 25% (sum stays 1.0)
    total = (edge_score * edge_weight) + (matchup_score * matchup_weight) + (hit_rate_score * 0.20) + (efficiency_score * 0.10) + (odds_score * 0.15)

    # Apply lineup modifiers - DIRECTION AWARE
    if lineup_status == "GTD":
        total *= 0.4
    elif lineup_status == "STARTING":
        if recommended_direction == "Over":
            total = min(10.0, total * 1.1) # Boost Over for starters
        else:
            total *= 0.95 # Slight penalty for Under for starters (more minutes risk)

    # Apply trend modifier
    if trend_data:
        trend = trend_data.get("trend", "stable")
        if trend == "declining":
            decline_pct = trend_data.get("decline_pct", 0)
            penalty = min(0.30, decline_pct / 100.0)
            if recommended_direction == "Over":
                total *= (1.0 - penalty)
            else:
                total *= (1.0 + (penalty * 0.5)) # Slight boost for Under if declining
        elif trend == "surging":
            if recommended_direction == "Over":
                total = min(10.0, total * 1.05)
            else:
                total *= 0.95

    # Apply home/away modifier (0.92 - 1.08), direction-aware
    raw_ha_mod = calculate_home_away_modifier(game_log or [], stat, is_home)
    if recommended_direction == "Under":
        # If player performs BETTER at venue (raw > 1.0), it's BAD for Under (penalty < 1.0)
        # If player performs WORSE at venue (raw < 1.0), it's GOOD for Under (boost > 1.0)
        ha_modifier = max(0.92, min(1.08, 1.0 / raw_ha_mod if raw_ha_mod > 0.5 else 1.0))
    else:
        ha_modifier = raw_ha_mod
    total *= ha_modifier

    # Apply minutes confidence modifier - DIRECTION AWARE
    raw_min_mod, avg_min = calculate_minutes_confidence(game_log or [])
    if recommended_direction == "Under":
        # High minutes is BAD for Under (penalty < 1.0)
        # Low minutes is GOOD for Under (boost > 1.0)
        min_modifier = max(0.90, min(1.10, 1.0 / raw_min_mod if raw_min_mod > 0.5 else 1.0))
    else:
        min_modifier = raw_min_mod
            
    total *= min_modifier
    
    # Apply Usage Vacuum Modifier (Teammates OUT)
    # usage_vacuum_modifier > 1.0 means teammates are out
    if usage_vacuum_modifier != 1.0:
        if recommended_direction == "Over":
            total *= usage_vacuum_modifier
        else:
            # Penalty for Under if usage opens up
            total *= (1.0 / usage_vacuum_modifier)

    # Apply Consistency Modifier (CV-based)
    consistency_mod, _ = calculate_consistency_modifier(game_log or [], stat, recommended_direction)
    total *= consistency_mod

    # Apply Rest Modifier (days since last game)
    rest_days_val = calculate_rest_days(game_log or [], game_time_utc)
    rest_mod = calculate_rest_modifier(rest_days_val, recommended_direction)
    total *= rest_mod

    # Apply Sample Size Confidence (LAST — scales the fully-adjusted score)
    sample_conf = calculate_sample_size_confidence(game_log or [])
    total *= sample_conf

    # Final clamp
    total = max(0.0, min(10.0, total))

    return total, round(edge, 2), round(player_avg, 1), urgency_score, recommended_direction, round(ha_modifier, 3), round(min_modifier, 3)


def calculate_matchup_score(opp_def_rank: int = None, opp_pace_rank: int = None,
                            direction: str = None, opp_stat_rank: int = None) -> float:
    """
    Calculate direction-aware matchup score (0-10) using opponent defense + pace.

    For Over: weak defense (high rank) + fast pace (low rank) = favorable (high score)
    For Under: strong defense (low rank) + slow pace (high rank) = favorable (high score)
    Defense weighted 60%, pace 40%.
    When opp_stat_rank is provided, it replaces opp_def_rank for stat-specific accuracy.
    Returns 5.0 (neutral) if direction unknown or data missing.
    """
    if direction is None or (opp_def_rank is None and opp_pace_rank is None and opp_stat_rank is None):
        return 5.0

    # Use stat-specific rank when available, fall back to generic defense rank
    def_rank = opp_stat_rank if opp_stat_rank is not None else (opp_def_rank if opp_def_rank is not None else 15)
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

    # Combined stats MUST be checked first — "Pts + Rebs + Asts" contains "pts"/"reb"/"ast"
    if "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        # PRA: weighted blend
        pts_score = (normalize(usg, 0.10, 0.35) * 0.60) + (normalize(ts, 0.45, 0.70) * 0.40)
        reb_score = normalize(reb, 0.03, 0.20)
        ast_score = normalize(ast, 0.03, 0.45)
        return round((pts_score * 0.50) + (reb_score * 0.25) + (ast_score * 0.25), 2)

    elif "3-pointer" in stat_lower or "3pm" in stat_lower or "point" in stat_lower or "pts" in stat_lower:
        # Points / 3PM: usage rate + shooting efficiency
        usg_score = normalize(usg, 0.10, 0.35)
        ts_score = normalize(ts, 0.45, 0.70)
        return round((usg_score * 0.60) + (ts_score * 0.40), 2)

    elif "rebound" in stat_lower or "reb" in stat_lower:
        return round(normalize(reb, 0.03, 0.20), 2)

    elif "assist" in stat_lower or "ast" in stat_lower:
        return round(normalize(ast, 0.03, 0.45), 2)

    return 5.0


def calculate_usage_vacuum_score(team_abbr: str, injuries_cache: dict, team_rosters: dict) -> float:
    """
    Calculate a modifier based on missing teammate usage (Usage Vacuum).
    If high-usage players are OUT, remaining players get a boost.
    Returns modifier 1.0 - 1.2.
    """
    if not team_abbr or team_abbr not in team_rosters:
        return 1.0

    missing_usage = 0.0
    roster = team_rosters[team_abbr] # List of {id, usg}
    
    # Get list of injured names/status for this team
    team_injuries = injuries_cache.get(team_abbr, [])
    # Map injury names to lower for matching
    injured_map = {i.get("name", "").lower(): i.get("status", "") for i in team_injuries}

    # We need to match roster IDs to names to check injuries...
    # Actually `team_rosters` should probably contain names or we need a way to link them.
    # The `injuries_cache` uses names (e.g. "LeBron James").
    # `team_rosters` is built from bio_stats which has ID but maybe not full name?
    # We should ensure `team_rosters` has names.
    
    for player in roster:
        p_name = player.get("name", "").lower()
        p_usg = player.get("usg", 0.0)
        
        # Check if this player is OUT
        if p_name in injured_map:
            status = injured_map[p_name].lower()
            if "out" in status:
                missing_usage += p_usg

    # Calculate modifier
    if missing_usage >= 0.40:
        return 1.20
    elif missing_usage >= 0.30:
        return 1.15
    elif missing_usage >= 0.20:
        return 1.05
    elif missing_usage >= 0.15:
        return 1.02
        
    return 1.0


def calculate_ranking_score(player_data: dict, props: list, game_time_utc: str,
                            lineup_status: str = "", last5_games: list = None,
                            usage_vacuum_modifier: float = 1.0,
                            is_home: bool = None,
                            game_log: list = None,
                            opp_def_rank: int = None,
                            opp_pace_rank: int = None,
                            player_advanced: dict = None) -> tuple:
    """
    Calculate ranking score for a player (finds best prop score).
    Returns (total_score, component_scores)
    """
    averages = player_data.get("averages", {"pts": 0, "reb": 0, "ast": 0})

    best_score = 0
    best_components = {"edge": 0, "efficiency": 0, "odds": 0}

    # Use full game log for hit rate (up to 10 games with recency weighting)
    games_for_hit_rate = game_log or last5_games or []

    for prop in props:
        stat_name = prop.get("stat_name", "")
        line = float(prop.get("line", 0))

        # Calculate hit rate and trend for this prop
        hit_rate = calculate_hit_rate(games_for_hit_rate, stat_name, line)
        trend_data = calculate_trend_score(games_for_hit_rate, stat_name)

        score, edge, player_avg, urgency, recommended_direction, _, _ = calculate_prop_ranking_score(
            prop, averages, game_time_utc,
            lineup_status=lineup_status,
            hit_rate=hit_rate,
            trend_data=trend_data,
            usage_vacuum_modifier=usage_vacuum_modifier,
            is_home=is_home,
            game_log=game_log,
            opp_def_rank=opp_def_rank,
            opp_pace_rank=opp_pace_rank,
            player_advanced=player_advanced
        )
        if score > best_score:
            best_score = score
            # Normalize edge for display component (0-10 scale approximation)
            display_edge = min(10.0, (abs(edge) / (line if line > 0 else 1)) * 40.0)

            best_components = {
                "edge": round(display_edge, 2),
                "efficiency": round(calculate_player_efficiency_score(stat_name, player_advanced), 2),
                "odds": 5.0
            }

    return best_score, best_components


def calculate_home_away_modifier(games: list, stat_name: str, is_home_tonight: bool = None) -> float:
    """
    Compare player's home vs away avg for a stat and return a modifier.
    Returns multiplier in [0.92, 1.08] — max 8% swing.
    Requires 2+ home AND 2+ away games to activate; otherwise returns 1.0.
    """
    if is_home_tonight is None or not games:
        return 1.0

    stat_key = _resolve_stat_key(stat_name)
    if not stat_key:
        return 1.0

    home_vals = []
    away_vals = []

    for game in games:
        matchup = game.get("matchup", "")
        value = _game_stat_value(game, stat_key)
        if "vs." in matchup:
            home_vals.append(value)
        elif "@" in matchup:
            away_vals.append(value)

    # Need at least 2 of each to be meaningful
    if len(home_vals) < 2 or len(away_vals) < 2:
        return 1.0

    home_avg = sum(home_vals) / len(home_vals)
    away_avg = sum(away_vals) / len(away_vals)
    overall_avg = (sum(home_vals) + sum(away_vals)) / (len(home_vals) + len(away_vals))

    if overall_avg == 0:
        return 1.0

    # How much better the player does in tonight's venue vs overall
    venue_avg = home_avg if is_home_tonight else away_avg
    raw_modifier = venue_avg / overall_avg

    # Clamp to [0.92, 1.08]
    return max(0.92, min(1.08, raw_modifier))


def calculate_minutes_confidence(games: list) -> tuple:
    """
    Compute average minutes from game log and return (modifier, avg_minutes).
    >=32 MPG → 1.05, 28-32 → 1.02, 22-28 → 1.0, 16-22 → 0.97, <16 → 0.93
    """
    if not games:
        return 1.0, 0.0

    minutes = [g.get("min", 0) for g in games if g.get("min", 0) > 0]
    if not minutes:
        return 1.0, 0.0

    avg_min = sum(minutes) / len(minutes)

    if avg_min >= 32:
        modifier = 1.05
    elif avg_min >= 28:
        modifier = 1.02
    elif avg_min >= 22:
        modifier = 1.0
    elif avg_min >= 16:
        modifier = 0.97
    else:
        modifier = 0.93

    return modifier, round(avg_min, 1)


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


def get_player_stats_quick(player_name: str, bio_cache: dict = None) -> dict | None:
    """Get basic player stats from NBA API including last 5 games for hit rate."""
    import time
    try:
        from nba_api.stats.static import players, teams
        from nba_api.stats.endpoints import playergamelog, commonplayerinfo

        player = _fuzzy_find_player(player_name)
        if not player:
            print(f"  ⚠️ No NBA match for: {player_name}")
            return None

        player_id = player['id']

        # Small delay to avoid NBA API rate limiting (429s / connection drops)
        if not bio_cache:
            time.sleep(0.6)

        position = "N/A"
        current_team = ""
        
        # Optimization: Use bio_cache if available
        if bio_cache and player_id in bio_cache:
            position = bio_cache[player_id].get("position", "N/A")
            current_team = bio_cache[player_id].get("team_abbr", "")
        else:
            try:
                player_info = commonplayerinfo.CommonPlayerInfo(
                    player_id=player_id)
                info = player_info.get_normalized_dict()['CommonPlayerInfo']
                if info:
                    position = str(info[0].get('POSITION', 'N/A'))
                    current_team = str(info[0].get('TEAM_ABBREVIATION', ''))
            except Exception:
                pass

        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id, season='2025-26')
            all_games = log.get_normalized_dict()['PlayerGameLog'][:10]

            if all_games:
                game_log_team = str(all_games[0]['MATCHUP'].split(" ")[0])
                # Prefer CommonPlayerInfo team (updated faster after trades)
                team_code = current_team if current_team else game_log_team
                nba_team = teams.find_team_by_abbreviation(team_code)
                team_name = nba_team['full_name'] if nba_team else "Unknown"

                # Averages from first 5 games (recent form for edge scoring)
                recent5 = all_games[:5]
                avg_pts = sum(g['PTS'] for g in recent5) / len(recent5)
                avg_reb = sum(g['REB'] for g in recent5) / len(recent5)
                avg_ast = sum(g['AST'] for g in recent5) / len(recent5)
                avg_fg3m = sum(g['FG3M'] for g in recent5) / len(recent5)

                # Build full game log (up to 10 games) with minutes
                game_log = []
                for g in all_games:
                    # Parse minutes: NBA API MIN field is "MM:SS" or "MM" string
                    raw_min = g.get('MIN', '0')
                    try:
                        if ':' in str(raw_min):
                            parts = str(raw_min).split(':')
                            minutes = int(parts[0]) + int(parts[1]) / 60.0
                        else:
                            minutes = float(raw_min)
                    except (ValueError, TypeError):
                        minutes = 0.0

                    game_log.append({
                        "pts": g['PTS'],
                        "reb": g['REB'],
                        "ast": g['AST'],
                        "fg3m": g['FG3M'],
                        "min": round(minutes, 1),
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
                    "last5Games": game_log[:5],
                    "gameLog": game_log,
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


def _parse_odds(odds_str: str) -> int:
    """Parse American odds string to int. Returns -110 on failure."""
    try:
        return int(str(odds_str).replace("+", ""))
    except (ValueError, TypeError):
        return -110


def _odds_tier_score(odds_val: int) -> float:
    """Convert American odds int to a 0-10 tiered score."""
    if odds_val >= 100:
        return 10.0
    elif odds_val >= -105:
        return 8.0
    elif odds_val >= -110:
        return 5.0
    elif odds_val >= -120:
        return 3.0
    return 2.0


def _resolve_stat_key(stat_name: str) -> str | None:
    """Map a display stat name to its game-log dict key."""
    stat_lower = stat_name.lower()
    # Combined stats MUST be checked first — "Pts + Rebs + Asts" contains "pts"/"reb"/"ast"
    if "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        return "pra"
    elif "3-pointer" in stat_lower or "3pm" in stat_lower:
        return "fg3m"
    elif "point" in stat_lower or "pts" in stat_lower:
        return "pts"
    elif "rebound" in stat_lower or "reb" in stat_lower:
        return "reb"
    elif "assist" in stat_lower or "ast" in stat_lower:
        return "ast"
    return None


def _game_stat_value(game: dict, stat_key: str) -> float:
    """Extract the stat value from a game dict given a resolved stat key."""
    if stat_key == "pra":
        return game.get("pts", 0) + game.get("reb", 0) + game.get("ast", 0)
    return game.get(stat_key, 0)


def _resolve_opponent_stat_rank(stat_name: str, opp_stats: dict) -> int | None:
    """
    Map a stat name to the stat-specific opponent rank.
    Returns the rank (1=best D, 30=worst) or None if unmapped.
    """
    if not opp_stats:
        return None

    stat_lower = stat_name.lower()

    # Combined stats first
    if "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        pts_r = opp_stats.get("opp_pts_rank", 15)
        reb_r = opp_stats.get("opp_reb_rank", 15)
        ast_r = opp_stats.get("opp_ast_rank", 15)
        return int(pts_r * 0.5 + reb_r * 0.25 + ast_r * 0.25)
    elif "3-pointer" in stat_lower or "3pm" in stat_lower:
        return opp_stats.get("opp_fg3m_rank")
    elif "point" in stat_lower or "pts" in stat_lower:
        return opp_stats.get("opp_pts_rank")
    elif "rebound" in stat_lower or "reb" in stat_lower:
        return opp_stats.get("opp_reb_rank")
    elif "assist" in stat_lower or "ast" in stat_lower:
        return opp_stats.get("opp_ast_rank")

    return None


def calculate_consistency_modifier(game_log: list, stat_name: str, recommended_direction: str) -> tuple:
    """
    Calculate consistency modifier based on coefficient of variation.
    Consistent players get a boost for Over, volatile players get a boost for Under.
    Returns (modifier, cv_value). Requires >= 4 games, else (1.0, 0.0).
    """
    if not game_log or len(game_log) < 4:
        return 1.0, 0.0

    stat_key = _resolve_stat_key(stat_name)
    if not stat_key:
        return 1.0, 0.0

    values = [_game_stat_value(game, stat_key) for game in game_log]
    mean = sum(values) / len(values)
    if mean == 0:
        return 1.0, 0.0

    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5
    cv = std_dev / mean

    if cv < 0.20:
        # Consistent player
        modifier = 1.06 if recommended_direction == "Over" else 0.94
    elif cv > 0.35:
        # Volatile player
        modifier = 0.94 if recommended_direction == "Over" else 1.06
    else:
        modifier = 1.0

    return modifier, round(cv, 3)


def calculate_sample_size_confidence(game_log: list) -> float:
    """
    Calculate confidence multiplier based on number of games available.
    5+ games: 1.0 (full confidence), fewer games are penalized proportionally.
    Returns multiplier in [0.0, 1.0].
    """
    if not game_log:
        return 0.0
    num_games = len(game_log)
    return min(1.0, num_games / 5.0)


def calculate_rest_days(game_log: list, game_time_utc: str) -> int:
    """
    Calculate days since last game from game log.
    Parses game_log[0].date (e.g. "Apr 11, 2025" or "2025-04-11T...") and tonight's date.
    Returns days diff (0=B2B, 1=normal). -1 on failure.
    """
    if not game_log or not game_time_utc:
        return -1

    last_game_date_str = game_log[0].get("date", "")
    if not last_game_date_str:
        return -1

    try:
        # Try ISO format first (2025-04-11 or 2025-04-11T...)
        try:
            last_date = datetime.datetime.strptime(last_game_date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            # Try "Apr 11, 2025" format
            last_date = datetime.datetime.strptime(last_game_date_str, "%b %d, %Y").date()

        # Parse tonight's game time
        game_dt = datetime.datetime.fromisoformat(game_time_utc.replace('Z', '+00:00'))
        tonight_date = game_dt.date()

        diff = (tonight_date - last_date).days
        # Subtract 1 because "1 day between games" means B2B (played yesterday)
        rest = max(0, diff - 1)
        return rest
    except Exception:
        return -1


def calculate_rest_modifier(rest_days: int, recommended_direction: str) -> float:
    """
    Calculate modifier based on days of rest.
    B2B (0): penalizes Over, boosts Under.
    Extra rest (2+): boosts Over, penalizes Under.
    Returns multiplier.
    """
    if rest_days < 0:
        return 1.0

    if rest_days == 0:
        # B2B
        return 0.95 if recommended_direction == "Over" else 1.03
    elif rest_days == 1:
        # Normal rest
        return 1.0
    elif rest_days == 2:
        return 1.03 if recommended_direction == "Over" else 0.97
    else:
        # 3+ days rest
        return 1.05 if recommended_direction == "Over" else 0.95


def calculate_hit_rate(last5_games: list, stat_name: str, line: float) -> dict:
    """
    Calculate hit rate for a specific stat against a line.
    Returns dict with hits, total, and individual game results.
    """
    if not last5_games:
        return {"hits": 0, "total": 0, "results": [], "weightedPct": 0.0}

    stat_key = _resolve_stat_key(stat_name)
    if not stat_key:
        return {"hits": 0, "total": 0, "results": [], "weightedPct": 0.0}

    hits = 0
    results = []
    weighted_hits = 0.0
    total_weight = 0.0
    num_games = len(last5_games)

    for i, game in enumerate(last5_games):
        value = _game_stat_value(game, stat_key)
        hit = value > line
        if hit:
            hits += 1

        # Recency weight: most recent (i=0) = 1.0, oldest = 0.5, linear decay
        weight = 1.0 - (i / max(num_games - 1, 1)) * 0.5 if num_games > 1 else 1.0
        weighted_hits += weight if hit else 0.0
        total_weight += weight

        results.append({
            "value": value,
            "hit": hit,
            "date": game.get("date", ""),
            "matchup": game.get("matchup", "")
        })

    weighted_pct = round(weighted_hits / total_weight, 3) if total_weight > 0 else 0.0

    return {
        "hits": hits,
        "total": num_games,
        "results": results,
        "weightedPct": weighted_pct,
    }


def calculate_trend_score(last5_games: list, stat_name: str) -> dict:
    """
    Compare last 2 games vs 5-game avg for a stat.
    Detects declining or surging usage patterns.
    Returns dict with trend direction, percentages, and recent average.
    """
    if len(last5_games) < 3:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": 0, "full_avg": 0}

    stat_key = _resolve_stat_key(stat_name)
    if not stat_key:
        return {"trend": "stable", "decline_pct": 0, "surge_pct": 0, "recent_avg": 0, "full_avg": 0}

    # Get values for all games
    values = [_game_stat_value(game, stat_key) for game in last5_games]

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



def _determine_trending_status(prop_score: float, trend_data: dict, hit_rate: dict) -> str:
    """
    Determine trending badge status for a prop card.

    HOT: prop_score >= 7.5 AND trend == "surging" AND weightedPct >= 0.60
    FADE: trend == "declining" with decline_pct >= 25 AND weightedPct < 0.35
    UP: everything else (default)
    """
    trend = trend_data.get("trend", "stable")
    weighted_pct = hit_rate.get("weightedPct", 0.0)
    decline_pct = trend_data.get("decline_pct", 0)

    if prop_score >= 7.5 and trend == "surging" and weighted_pct >= 0.60:
        return "hot"
    elif trend == "declining" and decline_pct >= 25 and weighted_pct < 0.35:
        return "fade"
    return "up"


def _run_analysis_pipeline(source: str, max_enrich: int = 0) -> dict | None:
    """
    Core analysis pipeline shared by HTTP and scheduled triggers.

    Args:
        source: "batch_analyze" or "scheduled_refresh" (for metadata)
        max_enrich: Max players to enrich (0 = no limit)

    Returns:
        dict with props_written, top_picks, for_you, espn_games_today
        or None if no props found.
    """
    print("\n" + "="*60)
    print(f"=== {source.upper()} ===")
    print(f"=== Time: {datetime.datetime.now().isoformat()} ===")
    print("="*60 + "\n")

    # 1. Fetch props from Underdog Fantasy (no API key needed!)
    underdog_data = get_underdog_nba_props()

    if not underdog_data["players"]:
        print("No NBA props available")
        return None

    # 2. Fetch ESPN schedule for additional game context
    espn_games = get_espn_nba_schedule()

    # 3. Fetch team defense stats for matchup analysis (single API call for all 30 teams)
    print("\n📊 Fetching team defense stats for matchup analysis...")
    team_defense_cache = get_all_team_defense_stats()
    print(f"✓ Cached defense stats for {len(team_defense_cache)} teams")

    # 3b. Fetch stat-specific opponent stats (e.g. OPP_PTS_RANK, OPP_FG3M_RANK)
    print("📊 Fetching stat-specific opponent stats...")
    opponent_stats_cache = get_all_team_opponent_stats()
    print(f"✓ Cached opponent stats for {len(opponent_stats_cache)} teams")

    # 4. Fetch player advanced stats (single API call for all ~500 players)
    print("📊 Fetching player advanced stats...")
    player_advanced_cache = get_all_player_advanced_stats()
    print(f"✓ Cached advanced stats for {len(player_advanced_cache)} players")

    # 5. Fetch player bio stats (Position, Team) for roster mapping
    print("📊 Fetching player bio stats...")
    bio_cache = get_all_player_bio_stats()
    print(f"✓ Cached bio stats for {len(bio_cache)} players")

    # Build team rosters for Usage Vacuum calculation
    team_rosters = {}
    for pid, bio in bio_cache.items():
        team = bio.get("team_abbr")
        if not team:
            continue
        if team not in team_rosters:
            team_rosters[team] = []

        usg = 0.0
        if pid in player_advanced_cache:
            usg = player_advanced_cache[pid].get("usg_pct", 0.0)

        team_rosters[team].append({
            "id": pid,
            "name": bio.get("name"),
            "usg": usg
        })

    # 6. Fetch injury reports, back-to-back info, and lineup confirmations
    injuries_cache = get_nba_injuries()
    b2b_cache = get_yesterdays_games()
    lineup_cache = get_todays_lineups()

    print(
        f"\nProcessing {len(underdog_data['players'])} players with props...\n")

    # 7. Enrich with NBA stats (parallel) - SMART SELECTION BY ODDS VALUE
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

    # Apply enrichment cap if specified
    if max_enrich > 0 and len(players_by_odds_value) > max_enrich:
        print(f"  ⚠️ Capping enrichment from {len(players_by_odds_value)} to {max_enrich} players")
        players_to_enrich = players_by_odds_value[:max_enrich]
    else:
        players_to_enrich = players_by_odds_value

    print(
        f"  Will enrich {len(players_to_enrich)} players with NBA API")

    enriched_players = []

    def enrich_player(player_data):
        player = player_data["player"]
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        nba_stats = get_player_stats_quick(player_name, bio_cache=bio_cache)

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

    # 8. Calculate ranking scores for all players
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
            except Exception:
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

        # Calculate Usage Vacuum Modifier
        usage_vacuum = calculate_usage_vacuum_score(team_abbr_for_lineup, injuries_cache, team_rosters)
        ep["usage_vacuum"] = usage_vacuum

        # Determine if player is home tonight for ranking
        is_home_tonight_rank = None
        if team_abbr_for_lineup and lineup_abbr and " @ " in lineup_abbr:
            _, home_l_check = lineup_abbr.split(" @ ")
            is_home_tonight_rank = (team_abbr_for_lineup == home_l_check.strip())

        # Look up opponent defense stats and player advanced stats for ranking
        rank_opponent_abbr = get_opponent_abbrev(lineup_abbr, team_abbr_for_lineup) if lineup_abbr and team_abbr_for_lineup else ""
        rank_opp_def_stats = team_defense_cache.get(rank_opponent_abbr, {})
        rank_player_adv = None
        rank_player_id = nba_stats.get("id") if nba_stats else None
        if isinstance(rank_player_id, int):
            rank_player_adv = player_advanced_cache.get(rank_player_id)
        elif isinstance(rank_player_id, str) and rank_player_id.isdigit():
            rank_player_adv = player_advanced_cache.get(int(rank_player_id))

        # Calculate ranking score with full context
        ranking_score, score_components = calculate_ranking_score(
            {"averages": averages},
            ep["underdog_props"],
            game_time_utc,
            lineup_status=ep_lineup_status,
            last5_games=last5_games,
            usage_vacuum_modifier=usage_vacuum,
            is_home=is_home_tonight_rank,
            game_log=nba_stats.get("gameLog", []),
            opp_def_rank=rank_opp_def_stats.get("def_rank"),
            opp_pace_rank=rank_opp_def_stats.get("pace_rank"),
            player_advanced=rank_player_adv
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

    # 9. Build individual prop cards (one document per prop)
    print("📊 Building individual prop cards...")
    all_prop_cards = []

    # Cache per-team context so teammates reuse the same lookups
    team_context_cache = {}
    priority_stats = ["Points", "Rebounds", "Assists",
                      "3-Pointers Made", "Pts + Rebs + Asts"]

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
            except Exception:
                pass

        # Get game log (up to 10 games) and last 5 for trend
        game_log = nba_stats.get("gameLog", []) if nba_stats else []
        last5_games = nba_stats.get("last5Games", []) if nba_stats else []

        # Determine if player is home tonight
        is_home_tonight = None
        if team_abbr and abbr_title and " @ " in abbr_title:
            _, home_t_check = abbr_title.split(" @ ")
            is_home_tonight = (team_abbr == home_t_check.strip())

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

            # Calculate hit rate (full game log) and trend (last 5) BEFORE ranking
            line = float(prop.get("line", 0))
            hit_rate = calculate_hit_rate(game_log if game_log else last5_games, stat_name, line)
            trend_data = calculate_trend_score(last5_games, stat_name)

            # Get opponent defense stats for matchup scoring
            opp_def_stats = team_defense_cache.get(opponent_abbr, {})

            # Resolve stat-specific opponent rank (e.g. OPP_FG3M_RANK for 3PM props)
            opp_opp_stats = opponent_stats_cache.get(opponent_abbr, {})
            opp_stat_rank = _resolve_opponent_stat_rank(stat_name, opp_opp_stats)

            # Calculate ranking score with all context (v6)
            prop_score, edge, player_avg, urgency_score, recommended_direction, ha_modifier, min_modifier = calculate_prop_ranking_score(
                prop, player_averages, game_time_utc,
                lineup_status=lineup_status,
                hit_rate=hit_rate,
                trend_data=trend_data,
                opp_def_rank=opp_def_stats.get("def_rank"),
                opp_pace_rank=opp_def_stats.get("pace_rank"),
                player_advanced=player_adv,
                is_home=is_home_tonight,
                game_log=game_log,
                usage_vacuum_modifier=ep.get("usage_vacuum", 1.0),
                opp_stat_rank=opp_stat_rank
            )

            # Calculate matchup score for prop card (informational)
            matchup_score = calculate_matchup_score(
                opp_def_stats.get("def_rank"),
                opp_def_stats.get("pace_rank"),
                recommended_direction,
                opp_stat_rank=opp_stat_rank
            )

            # Calculate efficiency score for prop card (informational)
            eff_score = calculate_player_efficiency_score(stat_name, player_adv)

            # Minutes confidence (informational)
            _, avg_minutes = calculate_minutes_confidence(game_log)

            # Format stat name
            short_name = stat_name.replace(
                "Points", "Pts").replace("Rebounds", "Reb")
            short_name = short_name.replace(
                "Assists", "Ast").replace("3-Pointers Made", "3PM")
            short_name = short_name.replace("Pts + Rebs + Asts", "PRA")

            try:
                over_odds = int(
                    str(prop.get("over_american", "-110")).replace("+", ""))
            except Exception:
                over_odds = -110
            try:
                under_odds = int(
                    str(prop.get("under_american", "-110")).replace("+", ""))
            except Exception:
                under_odds = -110

            # Determine HOT/FADE/UP trending status
            trending_status = _determine_trending_status(prop_score, trend_data, hit_rate)

            # Compute new modifiers for Firestore storage
            consistency_mod, cv_value = calculate_consistency_modifier(game_log, stat_name, recommended_direction)
            rest_days_val = calculate_rest_days(game_log, game_time_utc)
            rest_mod = calculate_rest_modifier(rest_days_val, recommended_direction)
            sample_conf = calculate_sample_size_confidence(game_log)

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
                "oppStatRank": opp_stat_rank,
                # Efficiency data (player advanced stats)
                "efficiencyScore": eff_score,
                "playerAdvanced": {
                    "usgPct": round(player_adv["usg_pct"] * 100, 1) if player_adv else None,
                    "tsPct": round(player_adv["ts_pct"] * 100, 1) if player_adv else None,
                    "rebPct": round(player_adv["reb_pct"] * 100, 1) if player_adv else None,
                    "astPct": round(player_adv["ast_pct"] * 100, 1) if player_adv else None,
                } if player_adv else None,
                # Hit rate data (up to 10 games, recency-weighted)
                "hitRate": {
                    "hits": hit_rate["hits"],
                    "total": hit_rate["total"],
                    "results": hit_rate["results"],
                    "weightedPct": hit_rate.get("weightedPct", 0.0),
                },
                # Trend data
                "trendData": {
                    "trend": trend_data.get("trend", "stable"),
                    "declinePct": trend_data.get("decline_pct", 0),
                    "surgePct": trend_data.get("surge_pct", 0),
                    "recentAvg": trend_data.get("recent_avg", 0),
                    "fullAvg": trend_data.get("full_avg", 0),
                },
                # v5 modifiers
                "isHome": is_home_tonight,
                "homeAwayModifier": ha_modifier,
                "minutesConfidence": min_modifier,
                "avgMinutes": avg_minutes,
                "usageVacuum": ep.get("usage_vacuum", 1.0),
                # v6 modifiers
                "consistencyModifier": round(consistency_mod, 3),
                "coefficientOfVariation": cv_value,
                "restModifier": round(rest_mod, 3),
                "restDays": rest_days_val,
                "sampleSizeConfidence": round(sample_conf, 2),
                "gamesPlayed": len(game_log),
                # Will be set after sorting
                "section": "topPicks",
                "featured": False,
                # HOT/FADE badge status (computed from trend + score + hit rate)
                "trending": trending_status,
                "isFade": trending_status == "fade",
                # Player averages for context
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
                "lineupStatus": lineup_status,
            }

            all_prop_cards.append(prop_card)

    print(f"📊 Created {len(all_prop_cards)} individual prop cards")

    # 10. Sort and categorize props
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

    for card in all_prop_cards[top_picks_start:top_picks_end]:
        card["section"] = "topPicks"
        card["featured"] = True

    # Mark remaining cards as allProps
    for card in all_prop_cards[top_picks_end:]:
        card["section"] = "allProps"
        card["featured"] = False

    # Count trending badges
    hot_count = sum(1 for c in all_prop_cards if c["trending"] == "hot")
    fade_count = sum(1 for c in all_prop_cards if c["trending"] == "fade")
    print(f"✓ Categorized: {for_you_count} forYou, {top_picks_count} topPicks")
    print(f"🔥 HOT badges: {hot_count}, ⚠️ FADE badges: {fade_count}")

    # 11. Clear old props and write to Firestore (batched)
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

    # Write new prop cards (batched)
    write_batch = db.batch()
    written_count = 0

    for card in all_prop_cards:
        doc_id = f"{card['player_id']}_{card['statName'].lower().replace(' ', '_')}"
        card["id"] = doc_id

        doc_ref = db.collection("props").document(doc_id)
        write_batch.set(doc_ref, card)
        written_count += 1

        if written_count % 400 == 0:
            write_batch.commit()
            write_batch = db.batch()

    if written_count % 400 != 0:
        write_batch.commit()

    print(f"\n{'='*60}")
    print(f"=== DATA SAVED: Wrote {written_count} prop cards to Firestore ===")
    print("="*60 + "\n")

    # 12. Write refresh metadata
    db.collection("metadata").document("lastRefresh").set({
        "completedAt": firestore.SERVER_TIMESTAMP,
        "propsWritten": written_count,
        "topPicks": top_picks_count,
        "forYou": for_you_count,
        "hotProps": hot_count,
        "fadeProps": fade_count,
        "source": source,
    })

    return {
        "props_written": written_count,
        "top_picks": top_picks_count,
        "for_you": for_you_count,
        "espn_games_today": len(espn_games),
    }


# ============================================================
# HTTP FUNCTION - Manually triggered via HTTP request
# ============================================================

@https_fn.on_request(timeout_sec=540, memory=2048)
def batch_analyze(req: https_fn.Request) -> https_fn.Response:
    """
    Fetch NBA player props from Underdog Fantasy and rank with data-driven scoring.
    Uses ESPN for schedule data and nba_api for player stats enrichment.
    """
    result = _run_analysis_pipeline(source="batch_analyze", max_enrich=60)

    if result is None:
        return https_fn.Response(json.dumps({
            "status": "error",
            "message": "No NBA player props found from Underdog Fantasy",
            "note": "This may happen if no NBA games are scheduled today"
        }), status=404, mimetype='application/json')

    return https_fn.Response(json.dumps({
        "status": "success",
        "message": f"Created {result['props_written']} individual prop cards",
        "props_written": result["props_written"],
        "top_picks": result["top_picks"],
        "for_you": result["for_you"],
        "source": "underdog_fantasy",
        "espn_games_today": result["espn_games_today"]
    }), mimetype='application/json')


# ============================================================
# SCHEDULED FUNCTION - Runs automatically via Cloud Scheduler
# ============================================================

@scheduler_fn.on_schedule(
    schedule="0 0-1,6-23 * * *",
    timezone=scheduler_fn.Timezone("America/Los_Angeles"),
    timeout_sec=540,
    memory=2048,
)
def scheduled_refresh(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Automatically refresh all player props hourly.
    Enriches all players (no cap) with NBA stats.
    """
    _run_analysis_pipeline(source="scheduled_refresh", max_enrich=0)
