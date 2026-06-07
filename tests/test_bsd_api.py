import requests
import os
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
BSD_BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

print("Testing BSD API...")
print("=" * 50)

# Test 1 — Get recent events
print("\nTest 1: Recent matches...")
response = requests.get(
    f"{BSD_BASE_URL}/events/",
    headers=HEADERS,
    params={"status": "finished", "limit": 3}
)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    events = data.get("results", [])
    print(f"Matches found: {len(events)}")
    if events:
        e = events[0]
        print(f"Match: {e.get('home_team')} vs {e.get('away_team')}")
        print(f"Score: {e.get('home_score')} - {e.get('away_score')}")
        print(f"Date: {e.get('date', '')[:10]}")
        print(f"Keys available: {list(e.keys())}")
else:
    print(f"Error: {response.text[:200]}")