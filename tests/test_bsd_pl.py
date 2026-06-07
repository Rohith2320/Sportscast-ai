import requests
import os
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
V2_BASE = "https://sports.bzzoiro.com/api/v2"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

print("Finding recent Premier League match with rich data...")
print("=" * 60)

# Get recent PL matches
r = requests.get(
    f"{V2_BASE}/events/",
    headers=HEADERS,
    params={
        "status": "finished",
        "league_id": 1,
        "limit": 5
    }
)

data = r.json()
matches = data.get("results", [])
print(f"Recent PL matches: {len(matches)}")

for m in matches:
    print(f"\nID: {m['id']} | {m['home_team']} {m['home_score']} - {m['away_score']} {m['away_team']}")
    print(f"Date: {m.get('event_date', '')[:10]}")
    print(f"xG: {m.get('actual_home_xg')} - {m.get('actual_away_xg')}")

if matches:
    # Test incidents on the most recent match
    match_id = matches[0]["id"]
    print(f"\n\nTesting incidents for match {match_id}...")

    r = requests.get(
        f"{V2_BASE}/events/{match_id}/incidents/",
        headers=HEADERS
    )

    if r.status_code == 200:
        data = r.json()
        print(f"Response type: {type(data)}")
        print(f"Response preview: {str(data)[:500]}")
    else:
        print(f"Error: {r.text[:200]}")

    # Test player stats
    print(f"\nTesting player stats for match {match_id}...")
    r = requests.get(
        f"{V2_BASE}/events/{match_id}/player-stats/",
        headers=HEADERS
    )
    if r.status_code == 200:
        data = r.json()
        results = data.get("results", [])
        print(f"Player stats: {len(results)}")
        if results:
            print(f"Sample player: {results[0]}")
    else:
        print(f"Error: {r.text[:200]}")