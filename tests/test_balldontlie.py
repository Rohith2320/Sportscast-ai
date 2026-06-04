import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BALLDONTLIE_API_KEY")

headers = {"Authorization": API_KEY}

# Get today's games
print("Testing BallDontLie API...")
response = requests.get(
    "https://api.balldontlie.io/v1/games",
    headers=headers,
    params={
        "dates[]": "2026-06-03",  # Yesterday - Knicks vs Spurs
        "per_page": 10
    }
)

print(f"Status: {response.status_code}")
data = response.json()

if "data" in data:
    games = data["data"]
    print(f"Found {len(games)} games:")
    for game in games:
        home = game["home_team"]
        away = game["visitor_team"]
        print(f"\n{away['full_name']} {game['visitor_team_score']} vs "
              f"{game['home_team_score']} {home['full_name']}")
        print(f"Status: {game['status']}")
        print(f"Game ID: {game['id']}")
else:
    print("Error:", data)