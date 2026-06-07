from data_sources.mlb_fetcher import fetch_latest_game, format_mlb_data

print("Fetching latest MLB game...")
print("=" * 60)

data = fetch_latest_game()

print(f"Game: {data['away_team']} @ {data['home_team']}")
print(f"Score: {data['away_runs']} - {data['home_runs']}")
print(f"Winner: {data['winner']}")
print(f"Shutout: {data['is_shutout']}")

print("\nFormatted data:")
print("-" * 60)
print(format_mlb_data(data))