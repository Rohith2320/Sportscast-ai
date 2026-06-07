import requests
import os
from dotenv import load_dotenv

load_dotenv()

BSD_KEY = os.getenv("BSD_API_KEY")
V2_BASE = "https://sports.bzzoiro.com/api/v2"
HEADERS = {"Authorization": f"Token {BSD_KEY}"}

print("Finding league IDs...")
print("=" * 60)

r = requests.get(
    f"{V2_BASE}/leagues/",
    headers=HEADERS,
    params={"limit": 100}
)

data = r.json()
leagues = data.get("results", [])

# Search for major leagues
keywords = [
    "premier", "england", "la liga", "spain", "bundesliga",
    "germany", "serie a", "italy", "world cup", "fifa",
    "champions", "ligue", "france"
]

print(f"Total leagues: {data.get('count', 0)}")
print("\nMajor leagues found:")

for league in leagues:
    name = league.get("name", "").lower()
    country = league.get("country", "").lower()

    if any(k in name or k in country for k in keywords):
        print(f"ID: {league['id']} | {league['name']} | {league.get('country', '')}")