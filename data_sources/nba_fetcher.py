from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import leaguegamefinder
from utils.state import SportsCastState
import time


def fetch_nba_match(match_id: str) -> dict:
    """
    Fetch post-match data for an NBA game using nba_api package.
    
    Args:
        match_id: NBA game ID (e.g., "0022300456")
    
    Returns:
        Dictionary containing full match data
    """
    
    # Small delay to avoid rate limiting
    time.sleep(1)
    
    # Fetch box score
    boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(
        game_id=match_id,
        timeout=60
    )
    
    # Convert to dictionary format
    data = {
        "game_id": match_id,
        "player_stats": boxscore.player_stats.get_dict(),
        "team_stats": boxscore.team_stats.get_dict(),
    }
    
    return data


def nba_fetch_node(state: SportsCastState) -> dict:
    """
    LangGraph node that fetches NBA match data.
    Reads match_id from state, writes raw_match_data to state.
    """
    
    match_id = state["match_id"]
    
    try:
        print(f"Fetching NBA match data for game ID: {match_id}")
        data = fetch_nba_match(match_id)
        print("NBA data fetched successfully")
        return {"raw_match_data": data}
    
    except Exception as e:
        print(f"Error fetching NBA data: {e}")
        return {"error": f"NBA data fetch failed: {str(e)}"}