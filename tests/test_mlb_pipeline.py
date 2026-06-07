from graph import run_analysis
from utils.cost_tracker import get_session_cost

print("Running MLB analysis pipeline...")
print("=" * 50)

result = run_analysis("mlb", "latest", persona="espn_formal")

if result.get("error"):
    print(f"Pipeline failed: {result['error']}")
else:
    print("\n=== MLB PIPELINE COMPLETE ===")
    print(f"Game ID: {result.get('match_id')}")
    print(f"\n--- NARRATIVE ---")
    print(result.get("narrative", "No narrative generated"))
    print(f"\nTotal cost: ${get_session_cost():.4f}")