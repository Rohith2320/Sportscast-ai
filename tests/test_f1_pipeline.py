from graph import run_analysis
from utils.cost_tracker import get_session_cost

print("Running F1 analysis pipeline...")
print("=" * 50)

result = run_analysis("f1", "latest", persona="espn_formal", force_refresh=True)

if result.get("error"):
    print(f"Pipeline failed: {result['error']}")
else:
    print("\n=== F1 PIPELINE COMPLETE ===")
    print(f"Race: {result.get('match_id')}")
    print(f"\n--- NARRATIVE ---")
    print(result.get("narrative", "No narrative generated"))
    print(f"\nTotal cost: ${get_session_cost():.4f}")