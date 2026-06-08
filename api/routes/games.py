from fastapi import APIRouter, HTTPException
from api.models.schemas import GamesResponse, CachedGame
from utils.cache import list_cached_games, load_from_cache, invalidate_cache

router = APIRouter()


@router.get("/", response_model=GamesResponse)
def list_games(sport: str = None):
    """
    List all cached game analyses.
    Optionally filter by sport.
    """
    try:
        games = list_cached_games(sport=sport)
        return GamesResponse(
            games=[CachedGame(**g) for g in games],
            total=len(games)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sport}/{game_id}")
def get_game(sport: str, game_id: str):
    """
    Get a specific cached game analysis.
    Returns full analysis including narrative, match analysis, player analysis.
    """
    cached = load_from_cache(game_id, sport)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No cached analysis found for {sport} game {game_id}"
        )

    return {
        "game_id": game_id,
        "sport": sport,
        "match_id": cached.get("match_id"),
        "narrative": cached.get("narrative"),
        "match_analysis": cached.get("match_analysis"),
        "player_analysis": cached.get("player_analysis"),
        "persona": cached.get("persona"),
    }


@router.delete("/{sport}/{game_id}")
def delete_game(sport: str, game_id: str):
    """
    Delete a cached game analysis.
    Forces fresh analysis on next request.
    """
    from utils.cache import cache_exists
    if not cache_exists(game_id, sport):
        raise HTTPException(
            status_code=404,
            detail=f"No cached analysis found for {sport} game {game_id}"
        )
    invalidate_cache(game_id, sport)
    return {"deleted": True, "game_id": game_id, "sport": sport}