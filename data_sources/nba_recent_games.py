from datetime import datetime, timedelta
import time
import pytz
from nba_api.stats.endpoints import leaguegamefinder
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
def fetch_recent_games(max_days_back: int = 7) -> dict:
    """
    Fetch recent completed NBA games using LeagueGameFinder.
    Works for both regular season and playoffs/Finals.

    Returns:
        Dictionary with 'latest', 'recent', and 'featured' game
    """
    print("Fetching recent NBA games...")

    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    date_from = (now - timedelta(days=max_days_back)).strftime("%m/%d/%Y")
    date_to = now.strftime("%m/%d/%Y")

    log_api_call("NBA Stats API", f"leaguegamefinder/dates/{date_from}-{date_to}")
    time.sleep(1)

    gf = leaguegamefinder.LeagueGameFinder(
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        timeout=60
    )
    df = gf.get_data_frames()[0]

    if df.empty:
        return {"latest": [], "recent": [], "featured": None, "total": 0}

    # Deduplicate by game_id (each game appears twice — one row per team)
    seen = set()
    games_by_date = {}

    for _, row in df.iterrows():
        gid = row["GAME_ID"]
        if gid in seen:
            continue
        seen.add(gid)

        game_date_str = str(row["GAME_DATE"])  # "2026-06-10"
        try:
            game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        # Get both teams for this game
        both = df[df["GAME_ID"] == gid]
        if len(both) < 2:
            continue
        team1 = both.iloc[0]
        team2 = both.iloc[1]

        t1_score = int(team1.get("PTS", 0) or 0)
        t2_score = int(team2.get("PTS", 0) or 0)

        winner_abbr = team1["TEAM_ABBREVIATION"] if t1_score > t2_score else team2["TEAM_ABBREVIATION"]

        game = {
            "game_id": gid,
            "date": game_date.strftime("%B %d, %Y"),
            "date_raw": game_date_str,
            "team1_name": team1["TEAM_NAME"],
            "team1_abbr": team1["TEAM_ABBREVIATION"],
            "team1_score": t1_score,
            "team2_name": team2["TEAM_NAME"],
            "team2_abbr": team2["TEAM_ABBREVIATION"],
            "team2_score": t2_score,
            "margin": abs(t1_score - t2_score),
            "winner": winner_abbr,
            "status": "Final",
        }
        games_by_date.setdefault(game_date_str, []).append(game)

    if not games_by_date:
        return {"latest": [], "recent": [], "featured": None, "total": 0}

    # Most recent date
    most_recent_date = max(games_by_date.keys())
    latest_games = games_by_date[most_recent_date]

    recent_games = []
    for date_key, games in games_by_date.items():
        if date_key != most_recent_date:
            recent_games.extend(games)

    # Sort by closest margin
    latest_games.sort(key=lambda x: x["margin"])
    recent_games.sort(key=lambda x: x["margin"])

    featured = latest_games[0] if latest_games else None

    return {
        "latest": latest_games,
        "recent": recent_games,
        "featured": featured,
        "total": len(latest_games) + len(recent_games),
        "message": None,
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
