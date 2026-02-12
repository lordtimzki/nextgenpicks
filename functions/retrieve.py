import time
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, leaguedashteamstats, leaguedashplayerstats, leaguedashplayerbiostats, playerindex

# Get player data using nba api
async def get_player_data(player_name):
    print(f"DEBUG: Searching for {player_name} on NBA.com...")
    
    nba_players = players.find_players_by_full_name(player_name)
    if not nba_players:
        return None

    player = nba_players[0]
    player_id = player['id']
    full_name = player['full_name']
    
    # Image url
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

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
    if not last_10:
        # No games played - can't determine team, return None
        return None
    team_abbreviation = str(last_10[0]['MATCHUP'].split(" ")[0])

    team_full_name = ""

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
        "team_code": str(team_abbreviation),
        "team_name": str(team_full_name),
        "image": headshot_url,
        "averages": avg_stats,
        "last_10_games": recent_games
    }


# Bulk fetch stat-specific opponent stats (single API call for all 30 teams)
def get_all_team_opponent_stats() -> dict:
    """
    Fetch opponent (allowed) stats for all NBA teams in one API call.
    Returns dict keyed by team abbreviation with opp_pts_rank, opp_reb_rank,
    opp_ast_rank, opp_fg3m_rank (rank 1 = best defense, 30 = worst).
    """
    print("DEBUG: Fetching opponent stats for all 30 NBA teams...")

    try:
        time.sleep(0.5)
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season='2025-26',
            measure_type_detailed_defense='Opponent'
        )
        df = stats.get_data_frames()[0]

        opp_stats = {}
        for _, row in df.iterrows():
            team_id = int(row['TEAM_ID'])
            nba_team = teams.find_team_name_by_id(team_id)
            team_abbrev = nba_team['abbreviation'] if nba_team else ''

            if team_abbrev:
                opp_stats[team_abbrev] = {
                    "opp_pts_rank": int(row.get('OPP_PTS_RANK', 15)),
                    "opp_reb_rank": int(row.get('OPP_REB_RANK', 15)),
                    "opp_ast_rank": int(row.get('OPP_AST_RANK', 15)),
                    "opp_fg3m_rank": int(row.get('OPP_FG3M_RANK', 15)),
                }

        print(f"DEBUG: Fetched opponent stats for {len(opp_stats)} teams")
        return opp_stats

    except Exception as e:
        print(f"ERROR fetching opponent stats: {e}")
        return {}


# Bulk fetch Defense vs Position (DvP) stats — 3 API calls (G, F, C)
def get_dvp_stats() -> dict:
    """
    Fetch real Defense vs Position stats for all 30 teams.
    Makes 3 API calls: one per position group (Guard, Forward, Center).
    Returns dict keyed by (team_abbr, position_code) with stat-specific opp ranks.
    Example: dvp_cache[("BOS", "G")] = {"opp_pts_rank": 5, "opp_reb_rank": 20, ...}
    """
    print("DEBUG: Fetching Defense vs Position (DvP) stats (3 calls: G, F, C)...")

    dvp_cache = {}
    for pos in ["G", "F", "C"]:
        try:
            time.sleep(0.6)
            stats = leaguedashteamstats.LeagueDashTeamStats(
                season='2025-26',
                measure_type_detailed_defense='Opponent',
                player_position_abbreviation_nullable=pos
            )
            df = stats.get_data_frames()[0]

            for _, row in df.iterrows():
                team_id = int(row['TEAM_ID'])
                nba_team = teams.find_team_name_by_id(team_id)
                team_abbrev = nba_team['abbreviation'] if nba_team else ''
                if not team_abbrev:
                    continue

                dvp_cache[(team_abbrev, pos)] = {
                    "opp_pts_rank": int(row.get('OPP_PTS_RANK', 15)),
                    "opp_reb_rank": int(row.get('OPP_REB_RANK', 15)),
                    "opp_ast_rank": int(row.get('OPP_AST_RANK', 15)),
                    "opp_fg3m_rank": int(row.get('OPP_FG3M_RANK', 15)),
                }

            print(f"DEBUG: Fetched DvP for position '{pos}' — {sum(1 for k in dvp_cache if k[1] == pos)} teams")

        except Exception as e:
            print(f"ERROR fetching DvP stats for position {pos}: {e}")

    print(f"DEBUG: Total DvP entries: {len(dvp_cache)} (expected ~90)")
    return dvp_cache


# Bulk fetch all team defense stats (single API call for all 30 teams)
def get_all_team_defense_stats() -> dict:
    """
    Fetch defense stats for all NBA teams in one API call.
    Returns dict keyed by team abbreviation with def_rating, def_rank, pace, pace_rank.
    """
    print("DEBUG: Fetching defense stats for all 30 NBA teams...")

    try:
        # LeagueDashTeamStats returns all teams in one call
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season='2025-26',
            measure_type_detailed_defense='Advanced'
        )
        df = stats.get_data_frames()[0]

        team_stats = {}
        for _, row in df.iterrows():
            team_name = row['TEAM_NAME']
            team_id = int(row['TEAM_ID'])
            nba_team = teams.find_team_name_by_id(team_id)
            team_abbrev = nba_team['abbreviation'] if nba_team else ''

            if team_abbrev:
                team_stats[team_abbrev] = {
                    "name": str(team_name),
                    "def_rating": float(row['DEF_RATING']),
                    "def_rank": int(row['DEF_RATING_RANK']),
                    "pace": float(row['PACE']),
                    "pace_rank": int(row['PACE_RANK'])
                }

        if len(team_stats) < 30:
            print(f"WARNING: Only {len(team_stats)} teams cached, expected 30")
        print(f"DEBUG: Fetched defense stats for {len(team_stats)} teams")
        return team_stats

    except Exception as e:
        print(f"ERROR fetching all team stats: {e}")
        return {}


# Map compact position codes (from PlayerIndex) to full names for display/DvP
_POSITION_MAP = {
    "G": "Guard", "G-F": "Guard", "F-G": "Guard",
    "F": "Forward", "F-C": "Forward-Center", "C-F": "Forward-Center",
    "C": "Center",
}


# Bulk fetch player bio stats (single API call for position/team info)
def get_all_player_bio_stats() -> dict:
    """
    Fetch basic bio stats (Team, Position) for all players.
    Uses LeagueDashPlayerBioStats for team/stats + PlayerIndex for position.
    Returns dict keyed by PLAYER_ID.
    """
    print("DEBUG: Fetching player bio stats (Position, Team) for all players...")

    bio_stats = {}

    # 1. Fetch team and advanced bio data
    try:
        time.sleep(0.5)
        stats = leaguedashplayerbiostats.LeagueDashPlayerBioStats(
            season='2025-26'
        )
        df = stats.get_data_frames()[0]

        for _, row in df.iterrows():
            player_id = int(row['PLAYER_ID'])
            bio_stats[player_id] = {
                "team_abbr": str(row['TEAM_ABBREVIATION']),
                "position": "N/A",
                "name": str(row['PLAYER_NAME'])
            }

        print(f"DEBUG: Fetched bio stats for {len(bio_stats)} players")
    except Exception as e:
        print(f"ERROR fetching player bio stats: {e}")

    # 2. Fetch position data from PlayerIndex (has POSITION column)
    try:
        time.sleep(0.5)
        idx = playerindex.PlayerIndex(season='2025-26')
        idx_df = idx.get_data_frames()[0]

        pos_count = 0
        for _, row in idx_df.iterrows():
            player_id = int(row['PERSON_ID'])
            raw_pos = str(row.get('POSITION', ''))
            position = _POSITION_MAP.get(raw_pos, raw_pos) if raw_pos else "N/A"

            if player_id in bio_stats:
                bio_stats[player_id]["position"] = position
            else:
                # Player in index but not in bio stats — add with position + team
                bio_stats[player_id] = {
                    "team_abbr": str(row.get('TEAM_ABBREVIATION', '')),
                    "position": position,
                    "name": f"{row.get('PLAYER_FIRST_NAME', '')} {row.get('PLAYER_LAST_NAME', '')}".strip()
                }
            if position != "N/A":
                pos_count += 1

        print(f"DEBUG: Merged position data for {pos_count} players from PlayerIndex")
    except Exception as e:
        print(f"ERROR fetching PlayerIndex for positions: {e}")

    return bio_stats


# Bulk fetch player advanced stats (single API call for all ~500 players)
def get_all_player_advanced_stats() -> dict:
    """
    Fetch advanced stats for all NBA players in one API call.
    Returns dict keyed by PLAYER_ID (int) with usg_pct, ts_pct, reb_pct, ast_pct.
    """
    print("DEBUG: Fetching advanced stats for all NBA players...")

    try:
        time.sleep(1)  # Stagger after team defense call to avoid NBA API rate limit
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season='2025-26',
            measure_type_detailed_defense='Advanced'
        )
        df = stats.get_data_frames()[0]

        player_stats = {}
        for _, row in df.iterrows():
            player_id = int(row['PLAYER_ID'])
            player_stats[player_id] = {
                "usg_pct": float(row.get('USG_PCT', 0) or 0),
                "ts_pct": float(row.get('TS_PCT', 0) or 0),
                "reb_pct": float(row.get('REB_PCT', 0) or 0),
                "ast_pct": float(row.get('AST_PCT', 0) or 0),
            }

        print(f"DEBUG: Fetched advanced stats for {len(player_stats)} players")
        return player_stats

    except Exception as e:
        print(f"ERROR fetching player advanced stats: {e}")
        return {}


# Team stats using nba api
async def get_team_stats(team_name: str):
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
