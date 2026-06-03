from data_sources.nba_fetcher import fetch_nba_match
from agents.match_analysis_agent import format_nba_data, analyze_match
from agents.player_analysis_agent import format_player_data, analyze_players
from agents.narrative_agent import extract_key_storylines, generate_narrative

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
print("Done")

print("\nStep 4: Generating narrative - ESPN Formal style...")
storylines = extract_key_storylines(match_analysis, player_analysis)
narrative_espn = generate_narrative(storylines, "NBA", "espn_formal")
print("\n=== ESPN FORMAL NARRATIVE ===")
print(narrative_espn)

print("\nStep 5: Generating narrative - Tactical Coach style...")
narrative_tactical = generate_narrative(storylines, "NBA", "tactical_coach")
print("\n=== TACTICAL COACH NARRATIVE ===")
print(narrative_tactical)