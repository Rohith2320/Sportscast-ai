from utils.cache import load_from_cache
from agents.chat_agent import (
    classify_intent,
    extract_players_from_analysis,
    build_smart_context,
    generate_chat_response,
    find_player_in_query
)

print("Loading cached analysis...")
state = load_from_cache("0042500401", "nba")

if not state:
    print("No cache found - run test_pipeline.py first")
    exit()

print("Cache loaded\n")

players_in_game = extract_players_from_analysis(state.get("player_analysis", ""))
print(f"Players in game: {len(players_in_game)}")
print(f"Sample: {players_in_game[:5]}\n")
print("=" * 60)

# Test cases covering all 7 intent types
test_cases = [
    # Factual
    ("How many points did Josh Hart score?", []),
    # Analytical
    ("Why did the Knicks win this game?", []),
    # Comparative
    ("Compare Josh Hart and Victor Wembanyama", []),
    # Predictive
    ("What should the Spurs adjust for Game 2?", []),
    # Emotional
    ("That Josh Hart performance was absolutely insane", []),
    # Out of scope - player not in game
    ("How many points did LeBron James score?", []),
    # Out of scope - unrelated
    ("Who won the Super Bowl this year?", []),
]

chat_history = []

for question, _ in test_cases:
    print(f"\nQ: {question}")

    intent = classify_intent(question, chat_history)
    print(f"Intent: {intent}")

    matched = find_player_in_query(question, players_in_game)
    player_found = len(matched) > 0

    context = build_smart_context(
        query=question,
        state=state,
        intent=intent,
        players_in_game=players_in_game
    )

    response = generate_chat_response(
        query=question,
        context=context,
        chat_history=chat_history,
        intent=intent,
        sport="NBA",
        players_in_game=players_in_game,
        player_in_query=player_found
    )

    print(f"A: {response}")

    chat_history.append({"role": "user", "content": question})
    chat_history.append({"role": "assistant", "content": response})
    print("-" * 60)

# Test clarification follow-up
print("\nQ: Can you clarify what you meant about the turnovers?")
intent = classify_intent(
    "Can you clarify what you meant about the turnovers?",
    chat_history
)
print(f"Intent: {intent}")

context = build_smart_context(
    query="Can you clarify what you meant about the turnovers?",
    state=state,
    intent=intent,
    players_in_game=players_in_game
)

response = generate_chat_response(
    query="Can you clarify what you meant about the turnovers?",
    context=context,
    chat_history=chat_history,
    intent=intent,
    sport="NBA",
    players_in_game=players_in_game,
    player_in_query=False
)
print(f"A: {response}")

from utils.cost_tracker import get_session_cost
print(f"\nTotal cost: ${get_session_cost():.4f}")