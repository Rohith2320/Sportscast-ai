from graph import run_nba_analysis

print("Running full NBA pipeline with team name search...")
print("=" * 50)

result = run_nba_analysis("Lakers", persona="espn_formal", force_refresh=True)
if result.get("error"):
    print(f"\nPipeline failed: {result['error']}")
else:
    print("\n=== PIPELINE COMPLETE ===")
    print(f"Match ID: {result['match_id']}")
    print(f"Sport: {result['sport']}")
    print(f"Persona: {result['persona']}")

    print("\n--- NARRATIVE OUTPUT ---")
    print(result["narrative"])

    print("\n--- COST SUMMARY ---")
    from utils.cost_tracker import get_session_cost
    print(f"Total pipeline cost: ${get_session_cost():.4f}")