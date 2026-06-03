from data_sources.nba_fetcher import fetch_nba_match
from agents.match_analysis_agent import format_nba_data, analyze_match
from agents.player_analysis_agent import format_player_data, analyze_players

match_id = "0022300456"

print("Step 1: Fetching NBA data...")
raw_data = fetch_nba_match(match_id)
print("Done")

print("\nStep 2: Running match analysis...")
formatted_match = format_nba_data(raw_data)
match_analysis = analyze_match(formatted_match, "NBA")
print("Done")

print("\nStep 3: Running player analysis...")
formatted_players = format_player_data(raw_data)
player_analysis = analyze_players(formatted_players, match_analysis, "NBA")

print("\n=== PLAYER ANALYSIS ===")
print(player_analysis)