import json
import os
from datetime import datetime
from utils.logger import logger

CACHE_DIR = "cache"
CACHE_VERSION = "v1"


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def _cache_path(game_id: str, sport: str) -> str:
    """Build cache file path for a game."""
    safe_id = game_id.replace("/", "_")
    return os.path.join(CACHE_DIR, f"{sport}_{safe_id}.json")


def save_to_cache(game_id: str, sport: str, state: dict):
    """
    Save pipeline result to cache.

    Args:
        game_id: Unique game identifier
        sport: Sport name (nba, f1, nfl, etc.)
        state: Full pipeline state to cache
    """
    _ensure_cache_dir()

    cache_data = {
        "version": CACHE_VERSION,
        "game_id": game_id,
        "sport": sport,
        "cached_at": datetime.now().isoformat(),
        "state": {
            "sport": state.get("sport"),
            "match_id": state.get("match_id"),
            "match_analysis": state.get("match_analysis"),
            "player_analysis": state.get("player_analysis"),
            "narrative": state.get("narrative"),
            "persona": state.get("persona"),
            "raw_match_data": state.get("raw_match_data"),
        }
    }

    path = _cache_path(game_id, sport)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Cached analysis for {sport} game {game_id}")


def load_from_cache(
    game_id: str,
    sport: str,
    force_refresh: bool = False
) -> dict | None:
    """
    Load pipeline result from cache if available.

    Args:
        game_id: Unique game identifier
        sport: Sport name
        force_refresh: If True, ignore cache and return None

    Returns:
        Cached state dict if found and valid, None otherwise
    """
    if force_refresh:
        logger.info(f"Force refresh requested for {sport} game {game_id}")
        return None

    path = _cache_path(game_id, sport)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    # Check version - if prompts changed, invalidate
    if cache_data.get("version") != CACHE_VERSION:
        logger.info(
            f"Cache version mismatch for {game_id} "
            f"(cached: {cache_data.get('version')}, "
            f"current: {CACHE_VERSION}) - regenerating"
        )
        return None

    logger.info(
        f"Cache hit for {sport} game {game_id} "
        f"(cached at {cache_data['cached_at']})"
    )
    return cache_data["state"]


def cache_exists(game_id: str, sport: str) -> bool:
    """Check if a valid cache entry exists for a game."""
    path = _cache_path(game_id, sport)
    if not os.path.exists(path):
        return False

    with open(path, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    return cache_data.get("version") == CACHE_VERSION


def list_cached_games(sport: str = None) -> list[dict]:
    """
    List all cached games, optionally filtered by sport.
    Returns list sorted by most recently cached first.

    Args:
        sport: Optional sport filter

    Returns:
        List of cache metadata dicts
    """
    _ensure_cache_dir()

    cached = []

    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith(".json"):
            continue

        path = os.path.join(CACHE_DIR, filename)

        with open(path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        if sport and cache_data.get("sport") != sport:
            continue

        # Extract human-readable title from match analysis
        match_analysis = cache_data["state"].get("match_analysis", "") or ""
        title = ""
        for line in match_analysis.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        cached.append({
            "game_id": cache_data["game_id"],
            "sport": cache_data["sport"],
            "cached_at": cache_data["cached_at"],
            "match_id": cache_data["state"].get("match_id"),
            "has_narrative": bool(cache_data["state"].get("narrative")),
            "title": title,
        })

    cached.sort(key=lambda x: x["cached_at"], reverse=True)
    return cached


def invalidate_cache(game_id: str, sport: str):
    """Delete cached result for a specific game."""
    path = _cache_path(game_id, sport)

    if os.path.exists(path):
        os.remove(path)
        logger.info(f"Invalidated cache for {sport} game {game_id}")
    else:
        logger.info(f"No cache found for {sport} game {game_id}")