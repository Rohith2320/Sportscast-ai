import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
BSD_BASE_URL = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

print("Exploring BSD match data structure...")
print("=" * 60)

# Get a finished match
response = requests.get(
    f"{BSD_BASE_URL}/events/",
    headers=HEADERS,
    params={"status": "finished", "limit": 1}
)

data = response.json()
events = data.get("results", [])

if not events:
    print("No finished matches found")
    exit()

e = events[0]

print(f"Match: {e['home_team']} vs {e['away_team']}")
print(f"Score: {e['home_score']} - {e['away_score']}")
print(f"Date: {e.get('event_date', '')[:10]}")
print(f"League: {e.get('league', '')}")
print(f"xG: {e.get('actual_home_xg')} - {e.get('actual_away_xg')}")
print(f"Attendance: {e.get('attendance')}")
print(f"Referee: {e.get('referee')}")
print(f"Weather: {e.get('temperature_c')}C, Wind: {e.get('wind_speed')}")

# Coach info
home_coach = e.get("home_coach") or {}
away_coach = e.get("away_coach") or {}
print(f"\nHome Coach: {home_coach.get('name', 'N/A')}")
print(f"Away Coach: {away_coach.get('name', 'N/A')}")

# Unavailable players
unavailable = e.get("unavailable_players") or {}
home_out = unavailable.get("home", [])
away_out = unavailable.get("away", [])
print(f"\nUnavailable - Home: {len(home_out)} | Away: {len(away_out)}")
if home_out:
    print(f"Home out: {[p.get('name') for p in home_out[:3]]}")

# Live stats
live_stats = e.get("live_stats") or {}
print(f"\nLive stats keys: {list(live_stats.keys()) if live_stats else 'None'}")

# SR stats
sr_stats = e.get("sr_stats") or {}
print(f"SR stats keys: {list(sr_stats.keys()) if sr_stats else 'None'}")

# Get match detail by ID
match_id = e["id"]
print(f"\nFetching detailed match: {match_id}")
detail_response = requests.get(
    f"{BSD_BASE_URL}/events/{match_id}/",
    headers=HEADERS
)

if detail_response.status_code == 200:
    detail = detail_response.json()
    print(f"Detail keys: {list(detail.keys())}")

    # Check for lineups
    lineups = detail.get("lineups") or {}
    print(f"Lineups available: {bool(lineups)}")
    if lineups:
        print(f"Lineup keys: {list(lineups.keys())}")

    # Check for player stats
    player_stats = detail.get("player_stats") or {}
    print(f"Player stats available: {bool(player_stats)}")
    if player_stats:
        print(f"Player stats keys: {list(player_stats.keys())}")