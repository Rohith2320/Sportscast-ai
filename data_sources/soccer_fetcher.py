import os
import requests
import time
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
V2_BASE = "https://sports.bzzoiro.com/api/v2"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

LEAGUE_IDS = {
    "premier_league": 1,
    "epl": 1,
    "la_liga": 3,
    "bundesliga": 5,
    "serie_a": 4,
    "ligue_1": 6,
    "champions_league": 7,
    "world_cup": 27,
    "wc": 27,
    "fifa_world_cup": 27,
}


def safe_fetch(url: str, label: str, params: dict = None) -> dict:
    """Safely fetch URL. Returns empty dict on failure."""
    try:
        log_api_call("BSD API", label)
        time.sleep(0.3)
        response = requests.get(
            url, headers=HEADERS, params=params, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: Could not fetch {label}: {e}")
        return {}


@with_retry(max_attempts=3, base_delay=2)
def fetch_latest_match(league: str = "premier_league") -> dict:
    """Fetch most recent completed match for a league."""

    league_id = LEAGUE_IDS.get(league.lower())
    if not league_id:
        if str(league).isdigit():
            league_id = int(league)
        else:
            raise ValueError(f"Unknown league: {league}")

    data = safe_fetch(
        f"{V2_BASE}/events/",
        f"events/league/{league_id}/latest",
        params={"status": "finished", "league_id": league_id, "limit": 1}
    )

    matches = data.get("results", [])
    if not matches:
        raise ValueError(f"No finished matches found for {league}")

    return _build_match(matches[0])


@with_retry(max_attempts=3, base_delay=2)
def fetch_match_by_id(match_id: str) -> dict:
    """Fetch specific match by BSD event ID."""
    data = safe_fetch(
        f"{V2_BASE}/events/{match_id}/",
        f"events/{match_id}"
    )
    if not data:
        raise ValueError(f"Match {match_id} not found")
    return _build_match(data)


def _build_match(match: dict) -> dict:
    """
    Build clean match dict with core fields only.
    Fetches incidents and lineups as enrichment.
    """

    match_id = match["id"]
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    home_score = match.get("home_score", 0)
    away_score = match.get("away_score", 0)

    # Fetch incidents
    incidents_data = safe_fetch(
        f"{V2_BASE}/events/{match_id}/incidents/",
        f"events/{match_id}/incidents"
    )
    raw_incidents = incidents_data.get("incidents", [])
    incidents = [
        i for i in raw_incidents
        if i.get("type") in ["goal", "yellowCard", "redCard", "substitution"]
    ]

    # Fetch lineups
    lineup_data = safe_fetch(
        f"{V2_BASE}/events/{match_id}/lineups/",
        f"events/{match_id}/lineups"
    )
    lineups = lineup_data.get("lineups", {})

    home_coach = (match.get("home_coach") or {}).get("name", "")
    away_coach = (match.get("away_coach") or {}).get("name", "")

    return {
        "match_id": str(match_id),
        "league": match.get("league", {}).get("name", ""),
        "league_country": match.get("league", {}).get("country", ""),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "home_score_ht": match.get("home_score_ht", 0),
        "away_score_ht": match.get("away_score_ht", 0),
        "date": str(match.get("event_date", ""))[:10],
        "round": match.get("round_name", ""),
        "is_derby": match.get("is_local_derby", False),
        "home_xg": match.get("actual_home_xg"),
        "away_xg": match.get("actual_away_xg"),
        "home_coach": home_coach,
        "away_coach": away_coach,
        "odds_home": match.get("odds_home"),
        "odds_draw": match.get("odds_draw"),
        "odds_away": match.get("odds_away"),
        "incidents": incidents,
        "lineups": lineups,
        "winner": _get_winner(home_team, away_team, home_score, away_score),
    }


def _get_winner(home_team, away_team, home_score, away_score) -> str:
    if home_score > away_score:
        return home_team
    elif away_score > home_score:
        return away_team
    return "Draw"


def format_soccer_data(raw_data: dict) -> str:
    """
    Format clean soccer match data for the LLM.
    Focuses on: score, incidents, formations, odds context.
    """

    lines = []

    derby = " [LOCAL DERBY]" if raw_data.get("is_derby") else ""
    lines.append(
        f"=== {raw_data['home_team'].upper()} vs "
        f"{raw_data['away_team'].upper()}{derby} ==="
    )
    lines.append(f"Competition: {raw_data['league']} ({raw_data['league_country']})")
    lines.append(f"Date: {raw_data['date']}")
    if raw_data.get("round"):
        lines.append(f"Round: {raw_data['round']}")
    lines.append("")

    # Score
    lines.append("=== RESULT ===")
    lines.append(
        f"Full Time: {raw_data['home_team']} {raw_data['home_score']} - "
        f"{raw_data['away_score']} {raw_data['away_team']}"
    )
    lines.append(
        f"Half Time: {raw_data['home_team']} {raw_data['home_score_ht']} - "
        f"{raw_data['away_score_ht']} {raw_data['away_team']}"
    )
    lines.append(f"Winner: {raw_data['winner']}")

    if raw_data.get("home_xg") is not None:
        lines.append(
            f"xG: {raw_data['home_team']} {raw_data['home_xg']} - "
            f"{raw_data['away_xg']} {raw_data['away_team']}"
        )
    lines.append("")

    # Odds context
    if raw_data.get("odds_home"):
        lines.append("=== PRE-MATCH ODDS ===")
        lines.append(
            f"{raw_data['home_team']} win: {raw_data['odds_home']} | "
            f"Draw: {raw_data['odds_draw']} | "
            f"{raw_data['away_team']} win: {raw_data['odds_away']}"
        )
        try:
            home_odds = float(raw_data['odds_home'])
            away_odds = float(raw_data['odds_away'])
            winner = raw_data['winner']
            if winner == raw_data['home_team'] and home_odds > 2.5:
                lines.append("Result: HOME UPSET")
            elif winner == raw_data['away_team'] and away_odds > 2.5:
                lines.append("Result: AWAY UPSET")
            elif winner == "Draw":
                lines.append("Result: DRAW")
            else:
                lines.append("Result: EXPECTED OUTCOME")
        except (ValueError, TypeError):
            pass
        lines.append("")

    # Managers
    if raw_data.get("home_coach") or raw_data.get("away_coach"):
        lines.append("=== MANAGERS ===")
        lines.append(f"{raw_data['home_team']}: {raw_data.get('home_coach', 'N/A')}")
        lines.append(f"{raw_data['away_team']}: {raw_data.get('away_coach', 'N/A')}")
        lines.append("")

    # Incidents
    incidents = raw_data.get("incidents", [])
    if incidents:
        lines.append("=== MATCH INCIDENTS ===")
        for inc in incidents:
            inc_type = inc.get("type", "")
            minute = inc.get("minute", "?")
            is_home = inc.get("is_home", True)
            team = raw_data["home_team"] if is_home else raw_data["away_team"]

            if inc_type == "goal":
                player = inc.get("player", "Unknown")
                assist = inc.get("assist", "")
                assist_str = f" (assist: {assist})" if assist else ""
                lines.append(f"{minute}' GOAL - {player} ({team}){assist_str}")

            elif inc_type == "yellowCard":
                player = inc.get("player", "Unknown")
                lines.append(f"{minute}' YELLOW CARD - {player} ({team})")

            elif inc_type == "redCard":
                player = inc.get("player", "Unknown")
                lines.append(f"{minute}' RED CARD - {player} ({team})")

            elif inc_type == "substitution":
                player_in = inc.get("player_in", "")
                player_out = inc.get("player_out", "")
                if player_in and player_out:
                    lines.append(
                        f"{minute}' SUB - {player_out} -> "
                        f"{player_in} ({team})"
                    )
        lines.append("")

    # Lineups
    lineups = raw_data.get("lineups", {})
    if lineups:
        home_lineup = lineups.get("home", {})
        away_lineup = lineups.get("away", {})

        if home_lineup and home_lineup.get("players"):
            lines.append(f"=== {raw_data['home_team'].upper()} LINEUP ===")
            if home_lineup.get("formation"):
                lines.append(f"Formation: {home_lineup['formation']}")
            starters = [p for p in home_lineup["players"] if p.get("starter", True)]
            for p in starters:
                lines.append(
                    f"  {p.get('number', '')} {p.get('name', 'Unknown')} "
                    f"({p.get('pos', '')})"
                )
            lines.append("")

        if away_lineup and away_lineup.get("players"):
            lines.append(f"=== {raw_data['away_team'].upper()} LINEUP ===")
            if away_lineup.get("formation"):
                lines.append(f"Formation: {away_lineup['formation']}")
            starters = [p for p in away_lineup["players"] if p.get("starter", True)]
            for p in starters:
                lines.append(
                    f"  {p.get('number', '')} {p.get('name', 'Unknown')} "
                    f"({p.get('pos', '')})"
                )
            lines.append("")

    return "\n".join(lines)


def soccer_fetch_node(state: SportsCastState) -> dict:
    """LangGraph node that fetches Soccer match data using BSD API."""

    match_id = state["match_id"]
    start_time = log_agent_start("SoccerFetchAgent")

    try:
        if not match_id or match_id == "latest":
            try:
                print("Fetching latest World Cup match...")
                raw_data = fetch_latest_match("world_cup")
                match_date = raw_data.get("date", "")
                if match_date and match_date < "2025-01-01":
                    raise ValueError(f"World Cup data is stale ({match_date}), falling back to Premier League")
            except Exception as e:
                print(f"World Cup not available ({e}), fetching Premier League...")
                raw_data = fetch_latest_match("premier_league")

        elif str(match_id).isdigit():
            raw_data = fetch_match_by_id(match_id)

        elif match_id.lower() in LEAGUE_IDS:
            raw_data = fetch_latest_match(match_id)

        else:
            raw_data = fetch_latest_match("premier_league")

        print(f"Fetched: {raw_data['home_team']} vs {raw_data['away_team']}")
        print(f"Score: {raw_data['home_score']} - {raw_data['away_score']}")
        print(f"Incidents: {len(raw_data.get('incidents', []))}")

        log_agent_complete("SoccerFetchAgent", start_time)
        return {
            "raw_match_data": raw_data,
            "match_id": raw_data["match_id"]
        }

    except Exception as e:
        log_error("SoccerFetchAgent", str(e))
        return {"error": f"Soccer data fetch failed: {str(e)}"}