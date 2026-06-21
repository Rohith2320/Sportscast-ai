import requests
import time
from datetime import datetime, timedelta
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def safe_fetch(url: str, label: str, params: dict = None) -> dict:
    """Safely fetch URL. Returns empty dict on failure."""
    try:
        log_api_call("MLB Stats API", label)
        time.sleep(0.3)
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: Could not fetch {label}: {e}")
        return {}


def get_recent_games(days_back: int = 3) -> list:
    """
    Find recent completed MLB games by checking
    the last few days of schedule.
    """
    games = []
    for i in range(days_back):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        data = safe_fetch(
            f"{MLB_BASE}/schedule",
            f"schedule/{date}",
            params={
                "sportId": 1,
                "date": date,
                "hydrate": "team,linescore,decisions"
            }
        )
        dates = data.get("dates", [])
        if dates:
            day_games = dates[0].get("games", [])
            completed = [
                g for g in day_games
                if g.get("status", {}).get("detailedState") == "Final"
            ]
            games.extend(completed)

        if games:
            break

    return games


@with_retry(max_attempts=3, base_delay=2)
def fetch_latest_game() -> dict:
    """Fetch the most recent completed MLB game."""
    games = get_recent_games(days_back=3)
    if not games:
        raise ValueError("No recent completed MLB games found")
    return _build_game(games[0])


@with_retry(max_attempts=3, base_delay=2)
def fetch_game_by_id(game_id: str) -> dict:
    """Fetch a specific game by MLB game ID."""
    return _build_game_by_id(int(game_id))


@with_retry(max_attempts=3, base_delay=2)
def fetch_team_latest_game(team_name: str) -> dict:
    """
    Find the most recent completed game for a specific team.
    Searches last 3 days of games.
    """
    games = get_recent_games(days_back=7)
    team_lower = team_name.lower()

    for game in games:
        away = game["teams"]["away"]["team"]["name"].lower()
        home = game["teams"]["home"]["team"]["name"].lower()
        if team_lower in away or team_lower in home:
            return _build_game(game)

    raise ValueError(
        f"No recent completed games found for '{team_name}'"
    )


def _build_game(game: dict) -> dict:
    """Build game dict from schedule data then fetch full box score."""
    game_id = game["gamePk"]
    game_date = (game.get("officialDate") or game.get("gameDate", ""))[:10]
    result = _build_game_by_id(game_id)
    if game_date:
        result["game_date"] = game_date
    return result


def _build_game_by_id(game_id: int) -> dict:
    """Fetch and build complete game data from box score + linescore."""

    # Box score
    box = safe_fetch(
        f"{MLB_BASE}/game/{game_id}/boxscore",
        f"game/{game_id}/boxscore"
    )

    # Linescore
    line = safe_fetch(
        f"{MLB_BASE}/game/{game_id}/linescore",
        f"game/{game_id}/linescore"
    )

    if not box or not line:
        raise ValueError(f"Could not fetch data for game {game_id}")

    teams = box.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_name = away.get("team", {}).get("name", "Away Team")
    home_name = home.get("team", {}).get("name", "Home Team")

    # Team batting stats
    away_batting = away.get("teamStats", {}).get("batting", {})
    home_batting = home.get("teamStats", {}).get("batting", {})

    # Team pitching stats
    away_pitching = away.get("teamStats", {}).get("pitching", {})
    home_pitching = home.get("teamStats", {}).get("pitching", {})

    # Individual batters
    away_batters = _extract_batters(away)
    home_batters = _extract_batters(home)

    # Individual pitchers
    away_pitchers = _extract_pitchers(away)
    home_pitchers = _extract_pitchers(home)

    # Linescore innings
    innings = line.get("innings", [])
    line_teams = line.get("teams", {})

    away_runs = line_teams.get("away", {}).get("runs", 0)
    home_runs = line_teams.get("home", {}).get("runs", 0)

    # Top performers
    top_performers = _extract_top_performers(box)

    # Determine winner
    winner = away_name if away_runs > home_runs else home_name

    return {
        "game_id": str(game_id),
        "away_team": away_name,
        "home_team": home_name,
        "away_runs": away_runs,
        "home_runs": home_runs,
        "away_hits": away_batting.get("hits", 0),
        "home_hits": home_batting.get("hits", 0),
        "away_errors": away_batting.get("errors", 0),
        "home_errors": home_batting.get("errors", 0),
        "away_strikeouts_batting": away_batting.get("strikeOuts", 0),
        "home_strikeouts_batting": home_batting.get("strikeOuts", 0),
        "away_walks": away_batting.get("baseOnBalls", 0),
        "home_walks": home_batting.get("baseOnBalls", 0),
        "away_left_on_base": away_batting.get("leftOnBase", 0),
        "home_left_on_base": home_batting.get("leftOnBase", 0),
        "away_pitching_strikeouts": away_pitching.get("strikeOuts", 0),
        "home_pitching_strikeouts": home_pitching.get("strikeOuts", 0),
        "away_era": away_pitching.get("era", "0.00"),
        "home_era": home_pitching.get("era", "0.00"),
        "away_batters": away_batters,
        "home_batters": home_batters,
        "away_pitchers": away_pitchers,
        "home_pitchers": home_pitchers,
        "innings": innings,
        "top_performers": top_performers,
        "winner": winner,
        "is_shutout": away_runs == 0 or home_runs == 0,
    }


def _extract_batters(team: dict) -> list:
    """Extract individual batter stats."""
    batter_ids = team.get("batters", [])
    players = team.get("players", {})
    batters = []

    for pid in batter_ids:
        player = players.get(f"ID{pid}", {})
        person = player.get("person", {})
        stats = player.get("stats", {}).get("batting", {})
        position = player.get("position", {}).get("abbreviation", "")

        if not stats:
            continue

        batters.append({
            "name": person.get("fullName", "Unknown"),
            "position": position,
            "summary": stats.get("summary", ""),
            "at_bats": stats.get("atBats", 0),
            "hits": stats.get("hits", 0),
            "runs": stats.get("runs", 0),
            "rbi": stats.get("rbi", 0),
            "home_runs": stats.get("homeRuns", 0),
            "strikeouts": stats.get("strikeOuts", 0),
            "walks": stats.get("baseOnBalls", 0),
            "stolen_bases": stats.get("stolenBases", 0),
        })

    return batters


def _extract_pitchers(team: dict) -> list:
    """Extract individual pitcher stats."""
    pitcher_ids = team.get("pitchers", [])
    players = team.get("players", {})
    pitchers = []

    for pid in pitcher_ids:
        player = players.get(f"ID{pid}", {})
        person = player.get("person", {})
        stats = player.get("stats", {}).get("pitching", {})

        if not stats:
            continue

        pitchers.append({
            "name": person.get("fullName", "Unknown"),
            "innings_pitched": stats.get("inningsPitched", "0.0"),
            "hits": stats.get("hits", 0),
            "runs": stats.get("runs", 0),
            "earned_runs": stats.get("earnedRuns", 0),
            "walks": stats.get("baseOnBalls", 0),
            "strikeouts": stats.get("strikeOuts", 0),
            "home_runs": stats.get("homeRuns", 0),
            "pitches": stats.get("numberOfPitches", 0),
        })

    return pitchers


def _extract_top_performers(box: dict) -> list:
    """Extract top performers from box score."""

    # Build player ID to team name mapping from box score
    teams = box.get("teams", {})
    away_name = teams.get("away", {}).get("team", {}).get("name", "")
    home_name = teams.get("home", {}).get("team", {}).get("name", "")

    away_player_ids = set(
        teams.get("away", {}).get("batters", []) +
        teams.get("away", {}).get("pitchers", [])
    )
    home_player_ids = set(
        teams.get("home", {}).get("batters", []) +
        teams.get("home", {}).get("pitchers", [])
    )

    performers = []
    for p in box.get("topPerformers", []):
        player = p.get("player", {})
        person = player.get("person", {})
        player_id = person.get("id", 0)

        # Resolve team name from box score player lists
        if player_id in away_player_ids:
            team_name = away_name
        elif player_id in home_player_ids:
            team_name = home_name
        else:
            team_name = ""

        performers.append({
            "name": person.get("fullName", "Unknown"),
            "team": team_name,
            "type": p.get("type", ""),
        })

    return performers


def format_mlb_data(raw_data: dict) -> str:
    """
    Format MLB game data for the LLM.
    Covers score, linescore, key batters, pitchers, and top performers.
    """

    lines = []

    # Header
    shutout = " [SHUTOUT]" if raw_data.get("is_shutout") else ""
    lines.append(
        f"=== {raw_data['away_team'].upper()} @ "
        f"{raw_data['home_team'].upper()}{shutout} ==="
    )
    lines.append(f"Game ID: {raw_data['game_id']}")
    lines.append("")

    # Final score
    lines.append("=== FINAL SCORE ===")
    lines.append(
        f"{raw_data['away_team']}: {raw_data['away_runs']} runs, "
        f"{raw_data['away_hits']} hits, {raw_data['away_errors']} errors"
    )
    lines.append(
        f"{raw_data['home_team']}: {raw_data['home_runs']} runs, "
        f"{raw_data['home_hits']} hits, {raw_data['home_errors']} errors"
    )
    lines.append(f"Winner: {raw_data['winner']}")
    lines.append("")

    # Linescore
    innings = raw_data.get("innings", [])
    if innings:
        lines.append("=== LINESCORE (runs per inning) ===")
        away_line = " | ".join([
            f"{i['ordinalNum']}: {i.get('away', {}).get('runs', 0)}"
            for i in innings
        ])
        home_line = " | ".join([
            f"{i['ordinalNum']}: {i.get('home', {}).get('runs', 0)}"
            for i in innings
        ])
        lines.append(f"{raw_data['away_team']}: {away_line}")
        lines.append(f"{raw_data['home_team']}: {home_line}")
        lines.append("")

    # Team batting summary
    lines.append("=== TEAM BATTING SUMMARY ===")
    lines.append(
        f"{raw_data['away_team']}: "
        f"SO={raw_data['away_strikeouts_batting']}, "
        f"BB={raw_data['away_walks']}, "
        f"LOB={raw_data['away_left_on_base']}"
    )
    lines.append(
        f"{raw_data['home_team']}: "
        f"SO={raw_data['home_strikeouts_batting']}, "
        f"BB={raw_data['home_walks']}, "
        f"LOB={raw_data['home_left_on_base']}"
    )
    lines.append("")

    # Starting pitchers
    away_pitchers = raw_data.get("away_pitchers", [])
    home_pitchers = raw_data.get("home_pitchers", [])

    if away_pitchers:
        lines.append(f"=== {raw_data['away_team'].upper()} PITCHING ===")
        for p in away_pitchers:
            lines.append(
                f"  {p['name']}: {p['innings_pitched']} IP, "
                f"{p['strikeouts']} K, {p['earned_runs']} ER, "
                f"{p['hits']} H, {p['walks']} BB"
                + (f", {p['pitches']} pitches" if p['pitches'] else "")
            )
        lines.append("")

    if home_pitchers:
        lines.append(f"=== {raw_data['home_team'].upper()} PITCHING ===")
        for p in home_pitchers:
            lines.append(
                f"  {p['name']}: {p['innings_pitched']} IP, "
                f"{p['strikeouts']} K, {p['earned_runs']} ER, "
                f"{p['hits']} H, {p['walks']} BB"
                + (f", {p['pitches']} pitches" if p['pitches'] else "")
            )
        lines.append("")

    # Key batters — only those with hits or RBI
    away_batters = [
        b for b in raw_data.get("away_batters", [])
        if b["hits"] > 0 or b["rbi"] > 0 or b["home_runs"] > 0
    ]
    home_batters = [
        b for b in raw_data.get("home_batters", [])
        if b["hits"] > 0 or b["rbi"] > 0 or b["home_runs"] > 0
    ]

    if away_batters:
        lines.append(f"=== {raw_data['away_team'].upper()} KEY BATTERS ===")
        for b in away_batters:
            hr_str = f", {b['home_runs']} HR" if b["home_runs"] else ""
            sb_str = f", {b['stolen_bases']} SB" if b["stolen_bases"] else ""
            lines.append(
                f"  {b['name']} ({b['position']}): "
                f"{b['hits']}-{b['at_bats']}, "
                f"{b['rbi']} RBI, {b['runs']} R"
                f"{hr_str}{sb_str}"
            )
        lines.append("")

    if home_batters:
        lines.append(f"=== {raw_data['home_team'].upper()} KEY BATTERS ===")
        for b in home_batters:
            hr_str = f", {b['home_runs']} HR" if b["home_runs"] else ""
            sb_str = f", {b['stolen_bases']} SB" if b["stolen_bases"] else ""
            lines.append(
                f"  {b['name']} ({b['position']}): "
                f"{b['hits']}-{b['at_bats']}, "
                f"{b['rbi']} RBI, {b['runs']} R"
                f"{hr_str}{sb_str}"
            )
        lines.append("")

    # Top performers
    top = raw_data.get("top_performers", [])
    if top:
        lines.append("=== TOP PERFORMERS ===")
        for p in top:
            lines.append(f"  {p['name']} ({p['team']}) - {p['type']}")
        lines.append("")

    return "\n".join(lines)


def mlb_fetch_node(state: SportsCastState) -> dict:
    """
    LangGraph node that fetches MLB game data.

    Accepts match_id as:
    - "latest" or empty — fetches most recent game
    - numeric game ID — fetches specific game
    - team name — fetches team's latest game
    """

    match_id = state["match_id"]
    start_time = log_agent_start("MLBFetchAgent")

    try:
        if not match_id or match_id == "latest":
            print("Fetching latest MLB game...")
            raw_data = fetch_latest_game()

        elif str(match_id).isdigit():
            print(f"Fetching MLB game ID: {match_id}")
            raw_data = fetch_game_by_id(match_id)

        else:
            print(f"Fetching latest game for: {match_id}")
            raw_data = fetch_team_latest_game(match_id)

        print(f"Fetched: {raw_data['away_team']} @ {raw_data['home_team']}")
        print(f"Score: {raw_data['away_runs']} - {raw_data['home_runs']}")
        print(f"Winner: {raw_data['winner']}")
        print(f"Pitchers: {len(raw_data['away_pitchers'])} + {len(raw_data['home_pitchers'])}")
        print(f"Key batters: {len([b for b in raw_data['away_batters'] if b['hits'] > 0])} + "
              f"{len([b for b in raw_data['home_batters'] if b['hits'] > 0])}")

        log_agent_complete("MLBFetchAgent", start_time)
        return {
            "raw_match_data": raw_data,
            "match_id": raw_data["game_id"]
        }

    except Exception as e:
        log_error("MLBFetchAgent", str(e))
        return {"error": f"MLB data fetch failed: {str(e)}"}