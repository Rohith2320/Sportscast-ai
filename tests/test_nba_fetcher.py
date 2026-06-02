from data_sources.nba_fetcher import fetch_nba_match

match_id = "0022300456"

print("Testing NBA fetcher...")
data = fetch_nba_match(match_id)

if "player_stats" in data and "team_stats" in data:
    print("Success - got real NBA match data")
    
    # Show team scores
    teams = data["team_stats"]["data"]
    print(f"\n{teams[0][2]} {teams[0][23]} vs {teams[1][2]} {teams[1][23]}")
    
    # Show number of players
    players = data["player_stats"]["data"]
    print(f"Total players in data: {len(players)}")
else:
    print("Something went wrong")