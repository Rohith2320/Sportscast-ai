from data_sources.soccer_fetcher import fetch_latest_match, format_soccer_data

print("Fetching latest Premier League match...")
print("=" * 50)

data = fetch_latest_match("premier_league")

print(f"Match: {data['home_team']} vs {data['away_team']}")
print(f"Score: {data['home_score']} - {data['away_score']}")
print(f"Winner: {data['winner']}")
print(f"Date: {data['date']}")
print(f"Goals: {len(data['goals'])}")

print("\nFormatted data:")
print("-" * 50)
formatted = format_soccer_data(data)
print(formatted)