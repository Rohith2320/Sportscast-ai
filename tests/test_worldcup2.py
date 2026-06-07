from data_sources.soccer_fetcher import safe_fetch

# Check scheduled matches
data = safe_fetch(
    "https://api.football-data.org/v4/competitions/WC/matches",
    "WC/all_matches"
)

matches = data.get("matches", [])
print(f"Total World Cup matches scheduled: {len(matches)}")

if matches:
    # Show first few
    print("\nFirst 3 matches:")
    for m in matches[:3]:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        date = m["utcDate"][:10]
        status = m["status"]
        print(f"{date} | {home} vs {away} | {status}")

    print("\nNext upcoming match:")
    upcoming = [m for m in matches if m["status"] == "TIMED"]
    if upcoming:
        m = upcoming[0]
        print(f"{m['utcDate'][:10]} | {m['homeTeam']['name']} vs {m['awayTeam']['name']}")