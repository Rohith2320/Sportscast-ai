from data_sources.f1_fetcher import fetch_race_weekend, format_f1_data

print("Fetching complete F1 race weekend...")
print("=" * 60)

data = fetch_race_weekend("current", "last")

print(f"\nRace: {data['race_name']}")
print(f"Circuit: {data['circuit']}")
print(f"Date: {data['date']}")
print(f"\nData collected:")
print(f"  Practice 1: {len(data['practice_1'])} drivers")
print(f"  Practice 2: {len(data['practice_2'])} drivers")
print(f"  Practice 3: {len(data['practice_3'])} drivers")
print(f"  Qualifying: {len(data['qualifying'])} drivers")
print(f"  Race results: {len(data['results'])} drivers")
print(f"  Pit stops: {len(data['pit_stops'])} recorded")
print(f"  Driver standings: {len(data['driver_standings'])} drivers")
print(f"  Constructor standings: {len(data['constructor_standings'])} teams")

print("\nFormatted data preview:")
print("-" * 60)
formatted = format_f1_data(data)
print(formatted[:2000])