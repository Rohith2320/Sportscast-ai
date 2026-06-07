from data_sources.soccer_fetcher import safe_fetch

data = safe_fetch(
    "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED",
    "WC/matches"
)

matches = data.get("matches", [])
print(f"World Cup matches found: {len(matches)}")

if matches:
    m = matches[-1]
    home = m["homeTeam"]["name"]
    away = m["awayTeam"]["name"]
    score = m["score"]["fullTime"]
    date = m["utcDate"][:10]
    print(f"Latest: {home} vs {away}")
    print(f"Score: {score}")
    print(f"Date: {date}")
else:
    print("No finished World Cup matches found")
    print("Response keys:", list(data.keys()))
    if "message" in data:
        print("Message:", data["message"])