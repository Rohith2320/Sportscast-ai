from data_sources.nba_fetcher import fetch_nba_match
from agents.match_analysis_agent import format_nba_data, analyze_match

match_id = "0022300456"

print("Step 1: Fetching NBA data...")
raw_data = fetch_nba_match(match_id)
print("Data fetched successfully")

print("\nStep 2: Formatting data...")
formatted = format_nba_data(raw_data)
print("Formatted data preview:")
print(formatted[:500])

print("\nStep 3: Sending to Claude for analysis...")
analysis = analyze_match(formatted, "NBA")
print("\n=== MATCH ANALYSIS ===")
print(analysis)