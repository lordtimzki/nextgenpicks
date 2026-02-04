"""
Underdog Fantasy + ESPN Scraper for NextGenPicks
Fetches player props from Underdog Fantasy API (no auth required)
Uses ESPN for game schedules
"""

import urllib.request
import json
import ssl
import datetime
from datetime import timezone


def fetch_json(url, headers=None):
    """Fetch JSON from URL using urllib (built-in, no dependencies)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url)
    req.add_header(
        "User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
    req.add_header("Accept", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        print(f"Fetch error: {e}")
        return None, None


def get_underdog_nba_props() -> dict:
    """
    Fetch all NBA player props from Underdog Fantasy.
    Returns structured data ready for Firebase.
    """
    print("=== Fetching Underdog Fantasy Props ===")

    status, data = fetch_json(
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
    print(f"  Total games: {len(games)}")

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
    # player_id -> {player_info, props: [...], game_info}
    players_with_props = {}

    for line in lines:
        if line.get("status") != "active":
            continue

        ou = line.get("over_under", {})
        app_stat = ou.get("appearance_stat", {})
        app_id = app_stat.get("appearance_id", "")

        if app_id not in appearance_to_player:
            continue  # Not NBA

        player_id = appearance_to_player[app_id]
        player = nba_players[player_id]
        match_id = appearance_to_match.get(app_id)
        team_id = appearance_to_team_id.get(app_id, "")
        game = games_by_id.get(match_id, {})

        # Initialize player entry
        if player_id not in players_with_props:
            players_with_props[player_id] = {
                "player": player,
                "game": game,
                "team_id": team_id,
                "props": []
            }

        # Extract prop data
        stat_name = app_stat.get("display_stat", "Unknown")
        stat_value = float(line.get("stat_value", 0))

        # Get over/under options
        options = line.get("options", [])
        over_option = next(
            (o for o in options if o.get("choice") == "higher"), None)
        under_option = next(
            (o for o in options if o.get("choice") == "lower"), None)

        prop = {
            "id": line.get("id"),
            "stat_name": stat_name,
            "line": stat_value,
            "over_multiplier": float(over_option.get("payout_multiplier", 1)) if over_option else 1.0,
            "under_multiplier": float(under_option.get("payout_multiplier", 1)) if under_option else 1.0,
            "over_american": over_option.get("american_price", "-110") if over_option else "-110",
            "under_american": under_option.get("american_price", "-110") if under_option else "-110",
        }

        players_with_props[player_id]["props"].append(prop)

    print(f"  NBA players with props: {len(players_with_props)}")

    # Count total props
    total_props = sum(len(p["props"]) for p in players_with_props.values())
    print(f"  Total NBA props: {total_props}")

    return {
        "players": list(players_with_props.values()),
        "games": [g for g in games if g.get("sport_id") == "NBA"]
    }


def get_espn_nba_schedule() -> list:
    """
    Fetch today's NBA schedule from ESPN.
    Returns list of games with team info.
    """
    print("\n=== Fetching ESPN NBA Schedule ===")

    status, data = fetch_json(
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
            "home_team": {
                "id": home_team.get("team", {}).get("id"),
                "name": home_team.get("team", {}).get("displayName"),
                "abbreviation": home_team.get("team", {}).get("abbreviation"),
                "logo": home_team.get("team", {}).get("logo"),
                "score": home_team.get("score", "0"),
            },
            "away_team": {
                "id": away_team.get("team", {}).get("id"),
                "name": away_team.get("team", {}).get("displayName"),
                "abbreviation": away_team.get("team", {}).get("abbreviation"),
                "logo": away_team.get("team", {}).get("logo"),
                "score": away_team.get("score", "0"),
            },
            "venue": competition.get("venue", {}).get("fullName", ""),
            "broadcast": competition.get("broadcasts", [{}])[0].get("names", [""])[0] if competition.get("broadcasts") else "",
        }
        games.append(game)
        print(f"    {game['short_name']} - {game['status']}")

    return games


def format_for_firebase(underdog_data: dict, espn_games: list) -> list:
    """
    Format Underdog + ESPN data for Firebase storage.
    Matches the existing iOS app data structure.
    """
    print("\n=== Formatting for Firebase ===")

    # Create team name mapping from ESPN
    team_abbrev_map = {}
    for game in espn_games:
        team_abbrev_map[game["home_team"]
                        ["name"].lower()] = game["home_team"]["abbreviation"]
        team_abbrev_map[game["away_team"]
                        ["name"].lower()] = game["away_team"]["abbreviation"]

    # Create game lookup by team
    games_by_team = {}
    for game in espn_games:
        games_by_team[game["home_team"]["abbreviation"]] = game
        games_by_team[game["away_team"]["abbreviation"]] = game

    firebase_cards = []

    # Build team_id to abbreviation map from games
    team_id_to_abbr = {}
    for game in espn_games:
        # This is from ESPN, not Underdog, so skip
        pass

    # Build from Underdog games in the data
    for player_data in underdog_data["players"]:
        ud_game = player_data.get("game", {})
        abbr_title = ud_game.get("abbreviated_title", "")
        if " @ " in abbr_title:
            away_abbr, home_abbr = abbr_title.split(" @ ")
            away_team_id = ud_game.get("away_team_id")
            home_team_id = ud_game.get("home_team_id")
            if away_team_id:
                team_id_to_abbr[str(away_team_id)] = away_abbr
            if home_team_id:
                team_id_to_abbr[str(home_team_id)] = home_abbr

    for player_data in underdog_data["players"]:
        player = player_data["player"]
        props = player_data["props"]
        ud_game = player_data.get("game", {})
        player_team_id = player_data.get("team_id", "")

        if not props:
            continue

        # Extract player info
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(
        )
        position = player.get("position_name", "N/A")
        image_url = player.get("image_url", "")

        # Determine team abbreviation from team_id mapping
        team_abbr = team_id_to_abbr.get(str(player_team_id), "")

        # If team_abbr not found, try to extract from game's abbreviated_title
        if not team_abbr and ud_game:
            abbr_title = ud_game.get("abbreviated_title", "")
            if " @ " in abbr_title:
                away, home = abbr_title.split(" @ ")
                # Use away team as fallback (better than nothing)
                team_abbr = away

        opponent = "TBD"
        game_time = "Tonight"
        game_time_utc = None  # ISO timestamp for client-side local time conversion

        # Try to extract from Underdog game info
        if ud_game:
            scheduled = ud_game.get("scheduled_at", "")
            if scheduled:
                try:
                    game_dt = datetime.datetime.fromisoformat(
                        scheduled.replace('Z', '+00:00'))
                    game_time = game_dt.strftime("%I:%M %p UTC")
                    game_time_utc = game_dt.isoformat()  # Store ISO for client conversion
                except:
                    pass

            # Get abbreviated title like "NOP @ CHA" - show full matchup
            abbr_title = ud_game.get("abbreviated_title", "")
            if abbr_title:
                opponent = abbr_title  # e.g., "LAL @ BKN"

        # Format props for iOS
        ios_props = []
        seen_stats = set()

        # Prioritize main stats first
        priority_stats = ["Points", "Rebounds", "Assists",
                          "3-Pointers Made", "Pts + Rebs + Asts"]

        # Sort props by priority
        def prop_priority(p):
            stat = p["stat_name"]
            if stat in priority_stats:
                return priority_stats.index(stat)
            return 100

        sorted_props = sorted(props, key=prop_priority)

        for prop in sorted_props:
            stat_name = prop["stat_name"]

            # Skip duplicates and limit to avoid clutter
            if stat_name in seen_stats or len(ios_props) >= 6:
                continue
            seen_stats.add(stat_name)

            # Shorten stat names
            short_name = stat_name
            short_name = short_name.replace("Points", "Pts")
            short_name = short_name.replace("Rebounds", "Reb")
            short_name = short_name.replace("Assists", "Ast")
            short_name = short_name.replace("3-Pointers Made", "3PM")
            short_name = short_name.replace("Pts + Rebs + Asts", "PRA")
            short_name = short_name.replace("Fantasy Points", "FPTS")

            # Convert american odds to integer
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

        if not ios_props:
            continue

        # Build the card
        card = {
            "id": player.get("id", ""),
            "name": player_name,
            "teamAbbr": team_abbr,
            "position": position,
            "imageName": image_url,
            "props": ios_props,
            "opponent": opponent,
            "gameTime": game_time,
            "gameTimeUTC": game_time_utc,  # ISO timestamp for local time conversion
            "trending": "up",  # Default, can be updated by AI
            "ai_analysis": "",  # To be filled by Gemini
            "source": "underdog",
            "last_updated": datetime.datetime.now(timezone.utc).isoformat(),
        }

        firebase_cards.append(card)

    print(f"  Formatted {len(firebase_cards)} player cards")
    return firebase_cards


def main():
    """Main function to test the scraper locally."""
    print("="*60)
    print("UNDERDOG + ESPN SCRAPER TEST")
    print("="*60)

    # Fetch data
    underdog_data = get_underdog_nba_props()
    espn_games = get_espn_nba_schedule()

    # Format for Firebase
    cards = format_for_firebase(underdog_data, espn_games)

    # Save test output
    with open("firebase_test_output.json", "w") as f:
        json.dump(cards, f, indent=2)

    print(f"\n✓ Saved {len(cards)} cards to firebase_test_output.json")

    # Print sample
    if cards:
        print("\n=== Sample Card ===")
        print(json.dumps(cards[0], indent=2))

    # Print stat coverage
    all_stats = set()
    for card in cards:
        for prop in card["props"]:
            all_stats.add(prop["statName"])

    print(f"\n=== Stats Available ({len(all_stats)}) ===")
    for stat in sorted(all_stats):
        print(f"  - {stat}")


if __name__ == "__main__":
    main()
