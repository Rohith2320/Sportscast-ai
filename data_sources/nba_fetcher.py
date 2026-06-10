import time
from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry


# Build team name to ID mapping once at module load
# This runs once when the file is imported - no repeated work
_ALL_TEAMS = teams.get_teams()
TEAM_NAME_TO_ID = {}

for team in _ALL_TEAMS:
    # Map full name: "Los Angeles Lakers" -> ID
    TEAM_NAME_TO_ID[team["full_name"].lower()] = team["id"]
    # Map nickname: "lakers" -> ID
    TEAM_NAME_TO_ID[team["nickname"].lower()] = team["id"]
    # Map abbreviation: "lal" -> ID
    TEAM_NAME_TO_ID[team["abbreviation"].lower()] = team["id"]


def find_team_id(team_name: str) -> int:
    """
    Convert a team name string to NBA team ID.
    Accepts full name, nickname, or abbreviation.

    Args:
        team_name: e.g. "Lakers", "Los Angeles Lakers", "LAL"

    Returns:
        NBA team ID integer

    Raises:
        ValueError if team not found
    """
    search = team_name.lower().strip()

    if search in TEAM_NAME_TO_ID:
        return TEAM_NAME_TO_ID[search]

    # Partial match fallback - "lake" matches "lakers"
    for key, team_id in TEAM_NAME_TO_ID.items():
        if search in key:
            return team_id

    raise ValueError(
        f"Team '{team_name}' not found. "
        f"Try full name (e.g. 'Los Angeles Lakers'), "
        f"nickname (e.g. 'Lakers'), or abbreviation (e.g. 'LAL')"
    )


@with_retry(max_attempts=3, base_delay=2)
def find_recent_game_id(team_name: str) -> tuple[str, str]:
    """
    Find the most recent completed game for a team.

    Args:
        team_name: Team name string

    Returns:
        Tuple of (game_id, game_description)
        e.g. ("0022300456", "PHX vs POR - Jan 15 2024")
    """
    team_id = find_team_id(team_name)

    time.sleep(1)

    log_api_call("NBA Stats API", f"leaguegamefinder/team/{team_id}")

    # Find recent games for this team
    gamefinder = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        timeout=60
    )

    games = gamefinder.get_data_frames()[0]

    if games.empty:
        raise ValueError(f"No recent games found for {team_name}")

    # Get most recent game
    most_recent = games.iloc[0]

    game_id = most_recent["GAME_ID"]
    game_date = most_recent["GAME_DATE"]
    matchup = most_recent["MATCHUP"]

    description = f"{matchup} on {game_date}"

    return game_id, description


@with_retry(max_attempts=3, base_delay=2)
def fetch_nba_match(match_id: str) -> dict:
    """
    Fetch post-match data for an NBA game using nba_api package.

    Args:
        match_id: NBA game ID (e.g. "0022300456")

    Returns:
        Dictionary containing full match data
    """

    time.sleep(1)

    log_api_call("NBA Stats API", f"boxscore/{match_id}")

    boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(
        game_id=match_id,
        timeout=60
    )

    data = {
        "game_id": match_id,
        "player_stats": boxscore.player_stats.get_dict(),
        "team_stats": boxscore.team_stats.get_dict(),
    }

    return data


@with_retry(max_attempts=3, base_delay=2)
def find_latest_nba_game() -> tuple[str, str]:
    """
    Find the most recent completed NBA game across ALL teams.
    Used when match_id == "latest".

    Returns:
        Tuple of (game_id, description)
    """
    from data_sources.nba_recent_games import fetch_recent_games
    result = fetch_recent_games(max_days_back=7)
    featured = result.get("featured")
    if not featured:
        # Fall back to any game from 'latest'
        latest = result.get("latest", [])
        if not latest:
            raise ValueError(
                "NBA 2025-26 season has ended. Next season starts October 2026. "
                "Browse the cached playoff analyses on the home page, or try a team "
                "name like 'Knicks' or 'Celtics'."
            )
        featured = latest[0]

    game_id = featured["game_id"]
    description = (
        f"{featured['team1_name']} vs {featured['team2_name']} — {featured['date']}"
    )
    return game_id, description


def nba_fetch_node(state: SportsCastState) -> dict:
    """
    LangGraph node that fetches NBA match data.

    Accepts:
    - "latest" → finds the most recently completed game automatically
    - A direct game ID (e.g. "0022300456")
    - A team name (e.g. "Lakers") → finds their most recent game
    """

    match_id = state["match_id"]
    start_time = log_agent_start("NBAFetchAgent")

    try:
        # "latest" keyword → find the most recent NBA game automatically
        if match_id.lower().strip() == "latest":
            print("Finding most recent NBA game...")
            game_id, description = find_latest_nba_game()
            print(f"Found: {description}")
            match_id = game_id

        # Check if match_id looks like a real game ID
        # NBA game IDs are 10-digit strings starting with "002"
        elif not match_id.startswith("00") or len(match_id) != 10:
            # Treat as team name - find their most recent game
            print(f"Searching for most recent game: {match_id}...")
            game_id, description = find_recent_game_id(match_id)
            print(f"Found: {description}")
            match_id = game_id

        print(f"Fetching NBA match data for game ID: {match_id}")
        data = fetch_nba_match(match_id)

        log_agent_complete("NBAFetchAgent", start_time)
        return {
            "raw_match_data": data,
            "match_id": match_id  # Update state with real game ID
        }

    except Exception as e:
        log_error("NBAFetchAgent", str(e))
        return {"error": f"NBA data fetch failed: {str(e)}"}