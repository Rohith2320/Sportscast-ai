"""
Game Discovery endpoint.
Returns the latest available game ID + display name for a sport.
Lightweight — does NOT run the full analysis pipeline.
"""
import requests
import time
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _discover_nba() -> dict:
    from data_sources.nba_recent_games import fetch_recent_games
    result = fetch_recent_games(max_days_back=7)
    featured = result.get("featured")
    if not featured:
        latest = result.get("latest", [])
        if not latest:
            raise ValueError("No recent NBA games found")
        featured = latest[0]
    return {
        "match_id": featured["game_id"],
        "display_name": f"{featured['team1_name']} vs {featured['team2_name']}",
        "date": featured.get("date", ""),
    }


def _discover_f1() -> dict:
    url = "http://api.jolpi.ca/ergast/f1/current/last/results.json"
    try:
        time.sleep(0.3)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            raise ValueError("No F1 race data found")
        race = races[0]
        season = race["season"]
        round_num = race["round"]
        race_name = race.get("raceName", f"Round {round_num}")
        race_date = race.get("date", "")
        return {
            "match_id": f"{season}/{round_num}",
            "display_name": race_name,
            "date": race_date,
        }
    except Exception as e:
        raise ValueError(f"F1 discovery failed: {e}")


def _discover_mlb() -> dict:
    from data_sources.mlb_fetcher import get_recent_games
    games = get_recent_games(days_back=3)
    if not games:
        raise ValueError("No recent MLB games found")
    g = games[0]
    away = g.get("teams", {}).get("away", {}).get("team", {}).get("name", "Away")
    home = g.get("teams", {}).get("home", {}).get("team", {}).get("name", "Home")
    game_id = str(g.get("gamePk", ""))
    game_date = g.get("gameDate", "")[:10]
    return {
        "match_id": game_id,
        "display_name": f"{away} @ {home}",
        "date": game_date,
    }


def _discover_soccer() -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    bsd_key = os.getenv("BSD_API_KEY", "")
    headers = {"Authorization": f"Token {bsd_key}"}
    try:
        time.sleep(0.3)
        r = requests.get(
            "https://sports.bzzoiro.com/api/v2/events/",
            headers=headers,
            params={"status": "finished", "league_id": 1, "limit": 1},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        matches = data.get("results", [])
        if not matches:
            raise ValueError("No finished soccer matches found")
        m = matches[0]
        match_id = str(m.get("id", ""))
        home = m.get("home_team", "Home")
        away = m.get("away_team", "Away")
        date = m.get("date", "")
        return {
            "match_id": match_id,
            "display_name": f"{home} vs {away}",
            "date": date,
        }
    except Exception as e:
        raise ValueError(f"Soccer discovery failed: {e}")


def _discover_valorant() -> dict:
    try:
        time.sleep(0.3)
        r = requests.get(
            "https://vlr.orlandomm.net/api/v1/results",
            params={"page": 1},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("data", [])
        if not results:
            raise ValueError("No Valorant results found")
        m = results[0]
        match_id = str(m.get("id", "latest"))
        teams = m.get("teams", [])
        t1 = teams[0]["name"] if len(teams) > 0 else "Team1"
        t2 = teams[1]["name"] if len(teams) > 1 else "Team2"
        return {
            "match_id": match_id,
            "display_name": f"{t1} vs {t2}",
            "date": m.get("ago", ""),
        }
    except Exception as e:
        raise ValueError(f"Valorant discovery failed: {e}")


_DISCOVERERS = {
    "nba": _discover_nba,
    "f1": _discover_f1,
    "mlb": _discover_mlb,
    "soccer": _discover_soccer,
    "valorant": _discover_valorant,
}


@router.get("/{sport}")
def discover_latest(sport: str):
    """
    Find the latest available game for a sport.
    Returns match_id and display_name — does NOT run analysis.
    """
    sport = sport.lower()
    if sport not in _DISCOVERERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sport '{sport}'. Valid: {list(_DISCOVERERS.keys())}",
        )
    try:
        result = _DISCOVERERS[sport]()
        return {
            "sport": sport,
            "match_id": result["match_id"],
            "display_name": result["display_name"],
            "date": result.get("date", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
