import requests

MLB_BASE = "https://statsapi.mlb.com/api/v1"

print("Exploring MLB Stats API...")
print("=" * 60)

# Test 1 - Today's games
print("\n1. Today's schedule:")
r = requests.get(
    f"{MLB_BASE}/schedule",
    params={
        "sportId": 1,
        "date": "2026-06-07",
        "hydrate": "team,linescore,decisions"
    },
    timeout=15
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    dates = data.get("dates", [])
    if dates:
        games = dates[0].get("games", [])
        print(f"Games today: {len(games)}")
        if games:
            import json
            print("\nSample game:")
            g = games[0]
            print(f"  {g['teams']['away']['team']['name']} @ {g['teams']['home']['team']['name']}")
            print(f"  Status: {g['status']['detailedState']}")
            print(f"  Game ID: {g['gamePk']}")
    else:
        print("No games today")

# Test 2 - Recent completed games
print("\n2. Recent completed games:")
r = requests.get(
    f"{MLB_BASE}/schedule",
    params={
        "sportId": 1,
        "date": "2026-06-06",
        "hydrate": "team,linescore,decisions"
    },
    timeout=15
)
if r.status_code == 200:
    data = r.json()
    dates = data.get("dates", [])
    if dates:
        games = dates[0].get("games", [])
        print(f"Games yesterday: {len(games)}")
        for g in games[:3]:
            away = g['teams']['away']
            home = g['teams']['home']
            status = g['status']['detailedState']
            away_score = away.get('score', 'N/A')
            home_score = home.get('score', 'N/A')
            print(f"  {away['team']['name']} {away_score} @ {home['team']['name']} {home_score} | {status}")
            print(f"  Game ID: {g['gamePk']}")

# Test 3 - Box score for a specific game
print("\n3. Box score for game 824269 (Mariners vs Tigers):")
r = requests.get(
    f"{MLB_BASE}/game/824269/boxscore",
    timeout=15
)
if r.status_code == 200:
    data = r.json()
    print(f"Keys: {list(data.keys())}")

    teams = data.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    print(f"\nAway team: {away.get('team', {}).get('name')}")
    print(f"Home team: {home.get('team', {}).get('name')}")

    # Team stats
    away_stats = away.get("teamStats", {}).get("batting", {})
    home_stats = home.get("teamStats", {}).get("batting", {})
    print(f"\nAway batting: runs={away_stats.get('runs')}, hits={away_stats.get('hits')}, strikeOuts={away_stats.get('strikeOuts')}")
    print(f"Home batting: runs={home_stats.get('runs')}, hits={home_stats.get('hits')}, strikeOuts={home_stats.get('strikeOuts')}")

    # Sample players
    away_batters = away.get("batters", [])
    away_players = away.get("players", {})
    print(f"\nAway batters count: {len(away_batters)}")
    if away_batters:
        sample_id = f"ID{away_batters[0]}"
        sample = away_players.get(sample_id, {})
        print(f"Sample player: {sample.get('person', {}).get('fullName')}")
        print(f"Sample stats: {sample.get('stats', {}).get('batting', {})}")

# Test 4 - Linescore
print("\n4. Linescore for game 824269:")
r = requests.get(
    f"{MLB_BASE}/game/824269/linescore",
    timeout=15
)
if r.status_code == 200:
    data = r.json()
    print(f"Keys: {list(data.keys())}")
    innings = data.get("innings", [])
    print(f"Innings: {len(innings)}")
    if innings:
        print(f"Sample inning: {innings[0]}")
    teams = data.get("teams", {})
    print(f"Final: Away {teams.get('away', {}).get('runs')} - Home {teams.get('home', {}).get('runs')}")

# Test 5 - Pitching stats
print("\n5. Pitching stats for game 824269:")
teams = data.get("teams", {}) if "teams" not in dir() else {}
r = requests.get(f"{MLB_BASE}/game/824269/boxscore", timeout=15)
if r.status_code == 200:
    data = r.json()
    away = data["teams"]["away"]
    home = data["teams"]["home"]

    away_pitchers = away.get("pitchers", [])
    away_players = away.get("players", {})
    print(f"Away pitchers: {len(away_pitchers)}")

    for pid in away_pitchers[:3]:
        player = away_players.get(f"ID{pid}", {})
        name = player.get("person", {}).get("fullName", "Unknown")
        stats = player.get("stats", {}).get("pitching", {})
        ip = stats.get("inningsPitched", "0")
        so = stats.get("strikeOuts", 0)
        er = stats.get("earnedRuns", 0)
        hits = stats.get("hits", 0)
        print(f"  {name}: {ip} IP, {so} K, {er} ER, {hits} H")

    home_pitchers = home.get("pitchers", [])
    home_players = home.get("players", {})
    print(f"\nHome pitchers: {len(home_pitchers)}")
    for pid in home_pitchers[:3]:
        player = home_players.get(f"ID{pid}", {})
        name = player.get("person", {}).get("fullName", "Unknown")
        stats = player.get("stats", {}).get("pitching", {})
        ip = stats.get("inningsPitched", "0")
        so = stats.get("strikeOuts", 0)
        er = stats.get("earnedRuns", 0)
        hits = stats.get("hits", 0)
        print(f"  {name}: {ip} IP, {so} K, {er} ER, {hits} H")

# Test 6 - Top performers
print("\n6. Top performers:")
r = requests.get(f"{MLB_BASE}/game/824269/boxscore", timeout=15)
if r.status_code == 200:
    data = r.json()
    top = data.get("topPerformers", [])
    print(f"Top performers: {len(top)}")
    for p in top:
        player = p.get("player", {})
        name = player.get("person", {}).get("fullName", "Unknown")
        ptype = p.get("type", "")
        team = player.get("parentTeam", {}).get("name", "")
        print(f"  {name} ({team}) - {ptype}")