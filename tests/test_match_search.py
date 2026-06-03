from data_sources.nba_fetcher import find_team_id, find_recent_game_id

# Test team name lookup
print("Testing team name lookup...")
test_names = ["Lakers", "lakers", "LAL", "Los Angeles Lakers", "Suns", "PHX"]

for name in test_names:
    team_id = find_team_id(name)
    print(f"{name} -> Team ID: {team_id}")

# Test game finder
print("\nFinding most recent Lakers game...")
game_id, description = find_recent_game_id("Lakers")
print(f"Game ID: {game_id}")
print(f"Description: {description}")

print("\nFinding most recent Suns game...")
game_id, description = find_recent_game_id("Suns")
print(f"Game ID: {game_id}")
print(f"Description: {description}")

from data_sources.nba_fetcher import fetch_nba_match

# Test full fetch using team name search
print("\nFull fetch test - Lakers most recent game...")
data = fetch_nba_match(game_id)

if "player_stats" in data and "team_stats" in data:
    teams = data["team_stats"]["data"]
    headers = data["team_stats"]["headers"]
    pts_idx = headers.index("PTS")
    name_idx = headers.index("TEAM_NAME")
    print(f"{teams[0][name_idx]} vs {teams[1][name_idx]}")
    print(f"Score: {teams[0][pts_idx]} - {teams[1][pts_idx]}")
else:
    print("Something went wrong")