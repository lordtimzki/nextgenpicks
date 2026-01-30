from fastapi import FastAPI, HTTPException
from google import genai
from google.genai.errors import ClientError
from dotenv import load_dotenv
import os
import uvicorn
from datetime import datetime
import json
from retrieve import get_player_data, get_team_stats, get_odds_and_matchup

load_dotenv()
app = FastAPI()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in environment")

client = genai.Client(api_key=GOOGLE_API_KEY)

@app.get("/analyze/{player_name}")
async def analyze_player(player_name: str):
    # 1. Player Stats
    player_data = await get_player_data(player_name)
    if not player_data:
        raise HTTPException(status_code=404, detail=f"Player '{player_name}' not found")
    
    # 2. Betting Odds
    odds_data = await get_odds_and_matchup(player_data["name"])
    
    # 3. Opponent Analysis
    opponent_name = "Unknown"
    opponent_stats = None
    
    if odds_data.get("game_info"):
        game = odds_data["game_info"]
        player_team = player_data["team_name"]
        
        # Determine opponent
        if player_team.lower() in game["home"].lower():
            opponent_name = game["away"]
        else:
            opponent_name = game["home"]
        
        opponent_stats = await get_team_stats(opponent_name)
    
    # 4. Days Rest Calculation
    days_rest = "Unknown"
    if player_data.get("last_10_games"):
        last_game_date_str = player_data["last_10_games"][0]["date"]
        
        for fmt in ["%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]:
            try:
                last_game_date = datetime.strptime(last_game_date_str, fmt)
                days_rest = (datetime.now() - last_game_date).days
                break
            except ValueError:
                continue
    
    # Format available props for better readability
    formatted_props = []
    if odds_data.get('props'):
        for prop in odds_data['props']:
            # Create human-readable display
            market_name = prop['market'].replace('player_', '').replace('_', ' ').title()
            formatted_props.append({
                "display": f"{prop['type']} {prop['line']} {market_name} at {prop['odds']:+d} ({prop['book']})",
                "market": prop['market'],
                "type": prop['type'],
                "line": prop['line'],
                "odds": prop['odds'],
                "book": prop['book']
            })
    
    # 5. Build Gemini Prompt for Multi-Prop Analysis
    prompt = f"""
    Act as a professional NBA handicapper analyzing ALL available prop bets for this player.

    **PLAYER:** {player_data['name']} ({player_data['team_code']})
    **OPPONENT:** {opponent_name}
    **DAYS REST:** {days_rest}

    **PLAYER AVERAGES (Last 10 Games):**
    - Points: {player_data['averages']['pts']}
    - Rebounds: {player_data['averages']['reb']}
    - Assists: {player_data['averages']['ast']}

    **OPPONENT DEFENSIVE PROFILE:**
    {f"- Defense Rating: {opponent_stats['def_rating']} (Rank #{opponent_stats['def_rank']})" if opponent_stats else "- Defense: Not Available"}
    {f"- Pace: {opponent_stats['pace']} (Rank #{opponent_stats['pace_rank']})" if opponent_stats else "- Pace: Not Available"}
    *(Lower Defense Rating = Harder to Score Against | Lower Pace Rank = Faster Game = More Opportunities)*

    **RECENT GAME LOG (Last 5 Games):**
    {json.dumps(player_data['last_10_games'][:5], indent=2)}

    **AVAILABLE PROP BETS TO ANALYZE:**
    {json.dumps(formatted_props, indent=2) if formatted_props else "No props available"}

    **YOUR TASK:**
    1. Analyze EACH available prop bet individually
    2. Consider: recent form, opponent strength, pace, rest, trends
    3. Assign each prop an action (BET/PASS) and confidence level
    4. Rank all props by value/edge
    5. Identify your TOP RECOMMENDED play

    **CRITICAL RULES:**
    - If a prop line is ABOVE the player's average, favor UNDER
    - If a prop line is BELOW the player's average, favor OVER
    - Account for opponent defense/pace adjustments
    - PASS on marginal edges (<55% confidence)
    - Only BET when you see clear value (60%+ confidence)

    **OUTPUT FORMAT (VALID JSON ONLY):**
    {{
    "top_pick": {{
        "prop": "Over 25.5 Points at -110 (DraftKings)",
        "action": "BET",
        "confidence": "68%",
        "reasoning": "Brief 2-3 sentence explanation why this is the best play"
    }},
    "all_props_ranked": [
        {{
        "prop": "Over 25.5 Points at -110 (DraftKings)",
        "action": "BET",
        "confidence": "68%",
        "value_score": "8/10",
        "analysis": "Player averages 26.3, opponent allows 27.2 to position, trending over"
        }},
        {{
        "prop": "Under 6.5 Assists at -105 (FanDuel)",
        "action": "PASS",
        "confidence": "52%",
        "value_score": "5/10",
        "analysis": "Close to average of 6.2, opponent pace favors slightly under but not enough edge"
        }}
    ],
    "summary": "One sentence overall betting advice for this player tonight"
    }}

    **IMPORTANT:** 
    - Return ONLY valid JSON, no markdown formatting
    - Include ALL available props in "all_props_ranked"
    - Rank from best value to worst
    - Be honest about PASS recommendations when there's no edge
    """
    
    # 6. Call Gemini
    ai_analysis = None
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.3
            }
        )
        
        # Parse and validate JSON
        try:
            ai_analysis = json.loads(response.text)
            
            # Validate structure
            if "top_pick" not in ai_analysis or "all_props_ranked" not in ai_analysis:
                raise ValueError("Missing required fields in AI response")
                
        except (json.JSONDecodeError, ValueError) as e:
            ai_analysis = {
                "error": "Invalid AI response format",
                "details": str(e),
                "raw_response": response.text[:500]
            }
            
    except ClientError as e:
        ai_analysis = {
            "error": "Gemini API Error",
            "details": str(e),
            "suggestion": "Check your API key and quota"
        }
    except Exception as e:
        ai_analysis = {
            "error": "Unexpected error calling AI",
            "details": str(e)
        }
    
    # 7. Build Response
    return {
        "player": {
            "name": player_data["name"],
            "id": player_data["id"],
            "team": player_data["team_name"],
            "team_code": player_data["team_code"],
            "image": player_data["image"],
            "averages": player_data["averages"],
            "recent_games": player_data["last_10_games"][:5]
        },
        "matchup": {
            "opponent": opponent_name,
            "opponent_stats": opponent_stats,
            "game_info": odds_data.get("game_info"),
            "days_rest": days_rest
        },
        "props": {
            "available": formatted_props,
            "count": len(formatted_props)
        },
        "ai_analysis": ai_analysis,
        "metadata": {
            "analyzed_at": datetime.now().isoformat(),
            "data_sources": ["NBA API", "The Odds API", "Gemini AI"]
        }
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
