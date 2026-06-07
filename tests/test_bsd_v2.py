import requests
import os
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
V2_BASE = "https://sports.bzzoiro.com/api/v2"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

MATCH_ID = 206686  # Paraguay vs Nicaragua

print(f"Testing BSD v2 API on match {MATCH_ID}...")
print("=" * 60)

# Test incidents (goals, cards, subs)
print("\n1. INCIDENTS (goals, cards, substitutions):")
r = requests.get(f"{V2_BASE}/events/{MATCH_ID}/incidents/", headers=HEADERS)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    incidents = data.get("results", data) if isinstance(data, dict) else data
    print(f"Incidents found: {len(incidents) if isinstance(incidents, list) else 'N/A'}")
    if isinstance(incidents, list) and incidents:
        print(f"First incident: {incidents[0]}")
else:
    print(f"Error: {r.text[:200]}")

# Test lineups
print("\n2. LINEUPS:")
r = requests.get(f"{V2_BASE}/events/{MATCH_ID}/lineups/", headers=HEADERS)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    if isinstance(data, dict):
        home = data.get("home", {})
        away = data.get("away", {})
        print(f"Home lineup players: {len(home.get('players', []))}")
        print(f"Away lineup players: {len(away.get('players', []))}")
        if home.get("players"):
            print(f"First home player: {home['players'][0]}")
else:
    print(f"Error: {r.text[:200]}")

# Test player stats
print("\n3. PLAYER STATS:")
r = requests.get(f"{V2_BASE}/events/{MATCH_ID}/player-stats/", headers=HEADERS)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    results = data.get("results", [])
    print(f"Player stats found: {len(results)}")
    if results:
        print(f"First player stat keys: {list(results[0].keys())}")
        print(f"First player: {results[0]}")
else:
    print(f"Error: {r.text[:200]}")

# Test recent Premier League match for richer data
print("\n4. RECENT PREMIER LEAGUE MATCHES:")
r = requests.get(
    f"{V2_BASE}/events/",
    headers=HEADERS,
    params={
        "status": "finished",
        "league_id": 2,  # Premier League
        "limit": 3
    }
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    results = data.get("results", [])
    print(f"Matches found: {len(results)}")
    for m in results[:3]:
        print(f"  {m.get('home_team')} {m.get('home_score')} - {m.get('away_score')} {m.get('away_team')} | {m.get('event_date', '')[:10]}")
else:
    print(f"Error: {r.text[:200]}")