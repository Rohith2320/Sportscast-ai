from datetime import datetime, timedelta
import time
import pytz
from nba_api.stats.endpoints import scoreboardv2
from utils.logger import log_api_call
from utils.retry import with_retry


def get_eastern_date(days_ago: int = 0) -> datetime:
    """
    Get the correct NBA date accounting for Eastern timezone.
    NBA games are scheduled in Eastern time.
    """
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    target = now - timedelta(days=days_ago)
    return target.replace(tzinfo=None)


@with_retry(max_attempts=3, base_delay=2)
def fetch_games_for_date(date: datetime) -> list[dict]:
    """
    Fetch all completed NBA games for a specific date.
    """
    date_str = date.strftime("%m/%d/%Y")
    log_api_call("NBA Stats API", f"scoreboard/{date_str}")

    time.sleep(1)

    scoreboard = scoreboardv2.ScoreboardV2(
        game_date=date_str,
        timeout=60
    )

    games_df = scoreboard.game_header.get_data_frame()
    line_score_df = scoreboard.line_score.get_data_frame()

    if games_df.empty:
        return []

    games = []

    for _, game in games_df.iterrows():
        game_id = game["GAME_ID"]
        game_status = game["GAME_STATUS_TEXT"]

        # Only include completed games
        if "Final" not in str(game_status):
            continue

        game_scores = line_score_df[
            line_score_df["GAME_ID"] == game_id
        ]

        if len(game_scores) < 2:
            continue

        team1 = game_scores.iloc[0]
        team2 = game_scores.iloc[1]

        team1_score = int(team1["PTS"]) if team1["PTS"] else 0
        team2_score = int(team2["PTS"]) if team2["PTS"] else 0
        margin = abs(team1_score - team2_score)

        games.append({
            "game_id": game_id,
            "date": date.strftime("%B %d, %Y"),
            "date_raw": date.strftime("%Y-%m-%d"),
            "team1_name": team1["TEAM_CITY_NAME"] + " " + team1["TEAM_NAME"],
            "team1_abbr": team1["TEAM_ABBREVIATION"],
            "team1_score": team1_score,
            "team2_name": team2["TEAM_CITY_NAME"] + " " + team2["TEAM_NAME"],
            "team2_abbr": team2["TEAM_ABBREVIATION"],
            "team2_score": team2_score,
            "margin": margin,
            "winner": team1["TEAM_ABBREVIATION"] if team1_score > team2_score
                      else team2["TEAM_ABBREVIATION"],
            "status": "Final",
        })

    return games


def fetch_recent_games(max_days_back: int = 7) -> dict:
    """
    Fetch recent NBA games automatically.
    Looks back up to max_days_back days until it finds games.
    Always returns the most recent games available.

    Returns:
        Dictionary with 'latest', 'recent', and 'featured' game
    """

    print("Fetching recent NBA games...")

    all_games_by_day = {}

    for days_ago in range(max_days_back):
        date = get_eastern_date(days_ago)
        print(f"Checking {date.strftime('%B %d, %Y')}...")
        games = fetch_games_for_date(date)

        if games:
            all_games_by_day[days_ago] = games

        # Once we find two days with games, stop looking
        if len(all_games_by_day) >= 2:
            break

    if not all_games_by_day:
        return {
            "latest": [],
            "recent": [],
            "featured": None,
            "total": 0,
            "message": "No recent games found in the last 7 days"
        }

    # Most recent day with games
    most_recent_day = min(all_games_by_day.keys())
    latest_games = all_games_by_day[most_recent_day]

    # Previous days
    recent_games = []
    for days_ago, games in all_games_by_day.items():
        if days_ago != most_recent_day:
            recent_games.extend(games)

    # Sort by closest margin first
    latest_games.sort(key=lambda x: x["margin"])
    recent_games.sort(key=lambda x: x["margin"])

    # Featured game — most recent AND closest margin
    featured = latest_games[0] if latest_games else None

    return {
        "latest": latest_games,
        "recent": recent_games,
        "featured": featured,
        "total": len(latest_games) + len(recent_games),
        "message": None
    }


def format_game_card(game: dict) -> str:
    """Format a game as a readable string."""
    winner_indicator1 = "W" if game["winner"] == game["team1_abbr"] else " "
    winner_indicator2 = "W" if game["winner"] == game["team2_abbr"] else " "

    return (
        f"[{winner_indicator1}] {game['team1_name']} {game['team1_score']} "
        f"vs {game['team2_score']} {game['team2_name']} [{winner_indicator2}] "
        f"| Margin: {game['margin']} pts | {game['date']}"
    )