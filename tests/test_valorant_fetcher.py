from data_sources.valorant_fetcher import fetch_latest_match, format_valorant_data

print("Fetching latest VCT match...")
print("=" * 60)

data = fetch_latest_match()

print(f"Match: {data['team1_name']} vs {data['team2_name']}")
print(f"Score: {data['team1_score']} - {data['team2_score']}")
print(f"Winner: {data['winner']}")
print(f"Tournament: {data['tournament']}")
print(f"Stage: {data['event']}")

print(f"\n{data['team1_name']} roster: "
      f"{[p['ign'] for p in data['team1_roster']]}")
print(f"{data['team2_name']} roster: "
      f"{[p['ign'] for p in data['team2_roster']]}")

print("\nFormatted data:")
print("-" * 60)
formatted = format_valorant_data(data)
print(formatted)