import requests
import time
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry

VLR_BASE = "https://vlr.orlandomm.net/api/v1"


def safe_fetch(url: str, label: str, params: dict = None) -> dict:
    """Safely fetch URL. Returns empty dict on failure."""
    try:
        log_api_call("VLR API", label)
        time.sleep(0.3)
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: Could not fetch {label}: {e}")
        return {}


@with_retry(max_attempts=3, base_delay=2)
def fetch_latest_match() -> dict:
    """
    Fetch the most recent completed VCT match.
    Returns the most recent result from VLR.
    """
    data = safe_fetch(
        f"{VLR_BASE}/results",
        "results/page1",
        params={"page": 1}
    )

    results = data.get("data", [])
    if not results:
        raise ValueError("No recent Valorant matches found")

    # Get most recent completed match
    match = results[0]
    return _build_match(match)


@with_retry(max_attempts=3, base_delay=2)
def fetch_match_by_id(match_id: str) -> dict:
    """Fetch a specific match by VLR match ID."""
    # Search through recent results for this ID
    data = safe_fetch(
        f"{VLR_BASE}/results",
        f"results/search/{match_id}",
        params={"page": 1}
    )

    results = data.get("data", [])
    for match in results:
        if match.get("id") == match_id:
            return _build_match(match)

    raise ValueError(f"Match {match_id} not found in recent results")


@with_retry(max_attempts=3, base_delay=2)
def fetch_team_roster(team_id: str, team_name: str) -> list[dict]:
    """
    Fetch roster for a team by ID.
    Returns list of player dicts.
    """
    data = safe_fetch(
        f"{VLR_BASE}/teams/{team_id}",
        f"teams/{team_id}"
    )

    team_data = data.get("data", {})
    players = team_data.get("players", [])

    return [
        {
            "name": p.get("name", ""),
            "ign": p.get("user", ""),
            "country": p.get("country", ""),
        }
        for p in players[:5]  # Starting 5 only
    ]


@with_retry(max_attempts=3, base_delay=2)
def fetch_latest_by_tournament(tournament: str = "masters") -> dict:
    """
    Fetch latest match from a specific tournament.

    Args:
        tournament: Partial tournament name to search for
    """
    data = safe_fetch(
        f"{VLR_BASE}/results",
        "results/page1",
        params={"page": 1}
    )

    results = data.get("data", [])
    tournament_lower = tournament.lower()

    for match in results:
        match_tournament = match.get("tournament", "").lower()
        if tournament_lower in match_tournament:
            return _build_match(match)

    # Fall back to most recent
    if results:
        return _build_match(results[0])

    raise ValueError(f"No matches found for tournament: {tournament}")


def _build_match(match: dict) -> dict:
    """
    Build complete match dict.
    Fetches team rosters for both teams.
    """
    teams = match.get("teams", [])
    if len(teams) < 2:
        raise ValueError("Match has fewer than 2 teams")

    team1 = teams[0]
    team2 = teams[1]

    # Fetch rosters for both teams
    team1_roster = []
    team2_roster = []

    if team1.get("id"):
        team1_roster = fetch_team_roster(team1["id"], team1["name"])
        time.sleep(0.3)

    if team2.get("id"):
        team2_roster = fetch_team_roster(team2["id"], team2["name"])

    winner = team1["name"] if team1.get("won") else team2["name"]
    winner_score = team1["score"] if team1.get("won") else team2["score"]
    loser_score = team2["score"] if team1.get("won") else team1["score"]

    return {
        "match_id": match.get("id", ""),
        "tournament": match.get("tournament", ""),
        "event": match.get("event", ""),
        "status": match.get("status", ""),
        "ago": match.get("ago", ""),
        "team1_name": team1["name"],
        "team1_score": team1["score"],
        "team1_country": team1.get("country", ""),
        "team1_won": team1.get("won", False),
        "team1_roster": team1_roster,
        "team2_name": team2["name"],
        "team2_score": team2["score"],
        "team2_country": team2.get("country", ""),
        "team2_won": team2.get("won", False),
        "team2_roster": team2_roster,
        "winner": winner,
        "winner_score": winner_score,
        "loser_score": loser_score,
    }


def format_valorant_data(raw_data: dict) -> str:
    """
    Format Valorant match data for the LLM.
    Combines match result with roster context.
    The LLM will enrich this with its training knowledge
    of teams, agents, and strategies.
    """

    lines = []

    # Header
    lines.append(
        f"=== {raw_data['team1_name'].upper()} vs "
        f"{raw_data['team2_name'].upper()} ==="
    )
    lines.append(f"Tournament: {raw_data['tournament']}")
    lines.append(f"Stage: {raw_data['event']}")
    lines.append(f"Status: {raw_data['status']}")
    lines.append("")

    # Result
    lines.append("=== MATCH RESULT ===")
    lines.append(
        f"Final Score: {raw_data['team1_name']} {raw_data['team1_score']} - "
        f"{raw_data['team2_score']} {raw_data['team2_name']}"
    )
    lines.append(f"Winner: {raw_data['winner']} "
                 f"({raw_data['winner_score']}-{raw_data['loser_score']})")
    lines.append("")

    # Team 1 roster
    if raw_data.get("team1_roster"):
        lines.append(f"=== {raw_data['team1_name'].upper()} ROSTER ===")
        for p in raw_data["team1_roster"]:
            lines.append(f"  {p['ign']} ({p['name']}) [{p['country'].upper()}]")
        lines.append("")

    # Team 2 roster
    if raw_data.get("team2_roster"):
        lines.append(f"=== {raw_data['team2_name'].upper()} ROSTER ===")
        for p in raw_data["team2_roster"]:
            lines.append(f"  {p['ign']} ({p['name']}) [{p['country'].upper()}]")
        lines.append("")

    # Context note for LLM
    lines.append("=== ANALYSIS CONTEXT ===")
    lines.append(
        f"This is a professional Valorant match from {raw_data['tournament']}. "
        f"Use your knowledge of these teams, their players, typical agent "
        f"compositions, strategic tendencies, and recent form to provide "
        f"deep tactical analysis. The match result is confirmed: "
        f"{raw_data['winner']} won {raw_data['winner_score']}-"
        f"{raw_data['loser_score']}."
    )

    return "\n".join(lines)


def valorant_fetch_node(state: SportsCastState) -> dict:
    """
    LangGraph node that fetches Valorant esports match data.

    Accepts match_id as:
    - "latest" — fetches most recent VCT match
    - "masters" or tournament name — fetches latest from that tournament
    - numeric VLR match ID — fetches specific match
    """

    match_id = state["match_id"]
    start_time = log_agent_start("ValorantFetchAgent")

    try:
        if not match_id or match_id == "latest":
            print("Fetching latest VCT match...")
            raw_data = fetch_latest_match()

        elif match_id.isdigit():
            print(f"Fetching Valorant match ID: {match_id}")
            raw_data = fetch_match_by_id(match_id)

        else:
            print(f"Fetching latest match from: {match_id}")
            raw_data = fetch_latest_by_tournament(match_id)

        print(f"Fetched: {raw_data['team1_name']} vs {raw_data['team2_name']}")
        print(f"Score: {raw_data['team1_score']} - {raw_data['team2_score']}")
        print(f"Tournament: {raw_data['tournament']}")
        print(f"Rosters: {len(raw_data['team1_roster'])} + "
              f"{len(raw_data['team2_roster'])} players")

        log_agent_complete("ValorantFetchAgent", start_time)
        return {
            "raw_match_data": raw_data,
            "match_id": raw_data["match_id"]
        }

    except Exception as e:
        log_error("ValorantFetchAgent", str(e))
        return {"error": f"Valorant data fetch failed: {str(e)}"}