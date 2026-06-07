import requests

VLR_BASE = "https://vlr.orlandomm.net/api/v1"

print("Testing VLR Esports API...")
print("=" * 60)

# Test 1 - Recent results
print("\n1. Recent match results:")
r = requests.get(f"{VLR_BASE}/results", params={"page": 1}, timeout=15)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    results = data.get("data", [])
    print(f"Matches found: {len(results)}")
    if results:
        print("\nSample match:")
        import json
        print(json.dumps(results[0], indent=2))
else:
    print(f"Error: {r.text[:200]}")

# Test 2 - Upcoming matches
print("\n2. Upcoming matches:")
r = requests.get(f"{VLR_BASE}/matches", timeout=15)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    matches = data.get("data", [])
    print(f"Matches found: {len(matches)}")
    if matches:
        print("\nSample upcoming match:")
        print(json.dumps(matches[0], indent=2))
else:
    print(f"Error: {r.text[:200]}")

# Test 3 - Team details
print("\n3. Team details for FUT Esports (id: 1184):")
r = requests.get(f"{VLR_BASE}/teams/1184", timeout=15)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(json.dumps(data, indent=2)[:1000])
else:
    print(f"Error: {r.text[:200]}")

# Test 4 - Player details
print("\n4. All players:")
r = requests.get(f"{VLR_BASE}/players", params={"page": 1}, timeout=15)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    players = data.get("data", [])
    print(f"Players found: {len(players)}")
    if players:
        print(json.dumps(players[0], indent=2))
else:
    print(f"Error: {r.text[:200]}")

# Test 5 - Events
print("\n5. Current events:")
r = requests.get(f"{VLR_BASE}/events", params={"page": 1}, timeout=15)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    events = data.get("data", [])
    print(f"Events found: {len(events)}")
    if events:
        print(json.dumps(events[0], indent=2))
else:
    print(f"Error: {r.text[:200]}")