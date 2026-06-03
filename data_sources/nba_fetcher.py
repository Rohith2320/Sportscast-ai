from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import leaguegamefinder
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry
import time

@with_retry(max_attempts=3, base_delay=2)
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
    start_time = log_agent_start("NBAFetchAgent")

    try:
        log_api_call("NBA Stats API", f"boxscore/{match_id}")
        data = fetch_nba_match(match_id)
        log_agent_complete("NBAFetchAgent", start_time)
        return {"raw_match_data": data}

    except Exception as e:
        log_error("NBAFetchAgent", str(e))
        return {"error": f"NBA data fetch failed: {str(e)}"}