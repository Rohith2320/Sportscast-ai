from data_sources.nba_recent_games import fetch_recent_games, format_game_card

print("Fetching recent NBA games automatically...")
print("=" * 60)

result = fetch_recent_games()

if result["message"]:
    print(f"\n{result['message']}")
else:
    if result["featured"]:
        print(f"\nFEATURED GAME (most recent, closest margin):")
        print("-" * 60)
        print(format_game_card(result["featured"]))
        print(f"Game ID: {result['featured']['game_id']}")

    if result["latest"]:
        print(f"\nLATEST GAMES ({len(result['latest'])} games):")
        print("-" * 60)
        for game in result["latest"]:
            print(format_game_card(game))

    if result["recent"]:
        print(f"\nRECENT GAMES ({len(result['recent'])} games):")
        print("-" * 60)
        for game in result["recent"]:
            print(format_game_card(game))

    print(f"\nTotal games found: {result['total']}")

from datetime import datetime
from data_sources.nba_recent_games import fetch_games_for_date

# Test with May 11 - we know Lakers vs Thunder happened
print("\nDirect date test - May 11, 2026:")
test_date = datetime(2026, 5, 11)
games = fetch_games_for_date(test_date)
if games:
    for game in games:
        print(format_game_card(game))
        print(f"Game ID: {game['game_id']}")
else:
    print("No games found")