from graph import run_nba_analysis
from utils.cache import cache_exists, list_cached_games, load_from_cache
import time

print("=" * 50)
print("TEST 1: First run - should hit pipeline")
print("=" * 50)

start = time.time()
result = run_nba_analysis("Knicks", persona="espn_formal")
first_run_time = round(time.time() - start, 2)

if result.get("error"):
    print(f"Pipeline failed: {result['error']}")
else:
    game_id = result["match_id"]
    print(f"\nGame ID: {game_id}")
    print(f"Time taken: {first_run_time}s")
    print(f"Cache exists now: {cache_exists(game_id, 'nba')}")

    print("\n" + "=" * 50)
    print("TEST 2: Load from cache - should be instant")
    print("=" * 50)

    start = time.time()
    cached = load_from_cache(game_id, "nba")
    cache_load_time = round(time.time() - start, 4)

    if cached:
        print(f"Cache loaded successfully")
        print(f"Time taken: {cache_load_time}s")
        print(f"Has narrative: {bool(cached.get('narrative'))}")
        print(f"Has match analysis: {bool(cached.get('match_analysis'))}")
        print(f"Has player analysis: {bool(cached.get('player_analysis'))}")
    else:
        print("Cache load failed")

    print("\n" + "=" * 50)
    print("TEST 3: List all cached games")
    print("=" * 50)

    all_cached = list_cached_games()
    print(f"Total cached games: {len(all_cached)}")
    for game in all_cached:
        print(f"  {game['sport'].upper()} | {game['game_id']} | "
              f"Cached at: {game['cached_at'][:19]}")