"""
Test script to probe PrizePicks and ESPN APIs
Run this locally to discover current API structure
"""

import urllib.request
import json
import ssl


def fetch_json(url, headers=None, method="GET", data=None):
    """Fetch JSON from URL using urllib (built-in)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, method=method)
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    if data:
        req.data = json.dumps(data).encode('utf-8')

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')[:500]
        except:
            body = str(e)
        return e.code, body
    except Exception as e:
        return None, str(e)


def test_prizepicks_api():
    """Test PrizePicks API endpoints to discover current structure."""
    print("\n" + "="*60)
    print("TESTING PRIZEPICKS API")
    print("="*60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Various endpoints to try
    endpoints = [
        # Standard projections
        ("GET", "https://api.prizepicks.com/projections?per_page=100&single_stat=true"),
        # League-specific (7 is typically NBA)
        ("GET", "https://api.prizepicks.com/projections?league_id=7&per_page=100"),
        # Leagues endpoint to get league IDs
        ("GET", "https://api.prizepicks.com/leagues"),
        # GraphQL endpoint
        ("GET", "https://api.prizepicks.com/graphql"),
    ]

    for method, url in endpoints:
        print(f"\n>>> Testing ({method}): {url}")
        status, data = fetch_json(url, headers, method)
        print(f"    Status: {status}")

        if status == 200 and isinstance(data, dict):
            print(f"    Keys: {list(data.keys())}")
            with open("prizepicks_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"    ✓ Saved to prizepicks_response.json")
            return data
        else:
            response_str = str(data)[:200] if data else "No response"
            # Check if it's a captcha/bot block
            if "captcha" in response_str.lower() or "PX" in response_str:
                print(f"    ⚠️ Bot protection detected (PerimeterX)")
            else:
                print(f"    Response: {response_str}")

    return None


def test_underdog_api():
    """Test Underdog Fantasy API as alternative."""
    print("\n" + "="*60)
    print("TESTING UNDERDOG FANTASY API")
    print("="*60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    endpoints = [
        "https://api.underdogfantasy.com/v1/over_under_lines",
        "https://api.underdogfantasy.com/beta/v5/over_under_lines",
    ]

    for url in endpoints:
        print(f"\n>>> Testing: {url}")
        status, data = fetch_json(url, headers)
        print(f"    Status: {status}")

        if status == 200:
            print(f"    ✓ Success!")
            if isinstance(data, dict):
                print(f"    Keys: {list(data.keys())}")
            with open("underdog_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"    ✓ Saved to underdog_response.json")
            return data
        else:
            print(f"    Response: {str(data)[:200]}")

    return None


def test_espn_api():
    """Test ESPN hidden API endpoints."""
    print("\n" + "="*60)
    print("TESTING ESPN API")
    print("="*60)

    endpoints = {
        "scoreboard": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "teams": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams",
    }

    for name, url in endpoints.items():
        print(f"\n>>> Testing {name}: {url}")
        status, data = fetch_json(url)
        print(f"    Status: {status}")

        if status == 200 and isinstance(data, dict):
            with open(f"espn_{name}.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"    ✓ Saved to espn_{name}.json")

            if name == "scoreboard":
                events = data.get("events", [])
                print(f"    Found {len(events)} games today")
                for event in events[:3]:
                    print(f"      - {event.get('name', 'N/A')} ({event.get('status', {}).get('type', {}).get('description', 'N/A')})")
            elif name == "teams":
                teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
                print(f"    Found {len(teams)} teams")


def test_balldontlie_api():
    """Test BallDontLie API for NBA stats."""
    print("\n" + "="*60)
    print("TESTING BALLDONTLIE API (NBA Stats)")
    print("="*60)

    url = "https://api.balldontlie.io/v1/players?per_page=10"
    print(f"\n>>> Testing: {url}")
    status, data = fetch_json(url)
    print(f"    Status: {status}")

    if status == 200 and isinstance(data, dict):
        players = data.get("data", [])
        print(f"    Found {len(players)} players")
        if players:
            p = players[0]
            print(f"    Sample: {p.get('first_name', '')} {p.get('last_name', '')} - {p.get('team', {}).get('full_name', 'N/A')}")
    else:
        print(f"    Note: May require API key now")


if __name__ == "__main__":
    print("API Structure Discovery Script")
    print("Testing multiple data sources...\n")

    # Test all APIs
    test_prizepicks_api()
    test_underdog_api()
    test_espn_api()
    test_balldontlie_api()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("""
PrizePicks: Has bot protection (PerimeterX) - difficult to scrape directly
Underdog: May have similar protections
ESPN: Works great for schedules/scores (no auth needed)
BallDontLie: Good for player stats (may need free API key)

Options:
1. Use headless browser (Selenium/Playwright) for PrizePicks
2. Stick with The-Odds-API for props (your current approach)
3. Use ESPN for schedules + nba_api for stats (already working)
""")
