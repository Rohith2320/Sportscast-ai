from langgraph.graph import StateGraph, END
from utils.state import SportsCastState
from utils.cache import save_to_cache, load_from_cache
from data_sources.nba_fetcher import nba_fetch_node
from agents.match_analysis_agent import match_analysis_node
from agents.player_analysis_agent import player_analysis_node
from agents.narrative_agent import narrative_node

def should_continue_after_fetch(state: SportsCastState) -> str:
    """
    Conditional edge after data fetch.
    If fetch failed, go to end. Otherwise continue to analysis.
    """
    if state.get("error"):
        print(f"Pipeline stopping due to error: {state['error']}")
        return "end"
    return "analyze"


def should_continue_after_analysis(state: SportsCastState) -> str:
    """
    Conditional edge after parallel analysis.
    If either analysis failed, go to end. Otherwise continue to narrative.
    """
    if state.get("error"):
        print(f"Pipeline stopping due to error: {state['error']}")
        return "end"
    if not state.get("match_analysis"):
        print("Match analysis missing, skipping narrative")
        return "end"
    return "narrative"


def build_nba_graph() -> StateGraph:
    """
    Build and return the NBA analysis LangGraph pipeline.

    Graph structure:
    fetch -> [match_analysis, player_analysis] (parallel) -> narrative -> END
    """

    # Initialize graph with our state schema
    graph = StateGraph(SportsCastState)

    # Add all nodes
    graph.add_node("fetch", nba_fetch_node)
    graph.add_node("match_analysis", match_analysis_node)
    graph.add_node("player_analysis", player_analysis_node)
    graph.add_node("narrative", narrative_node)

    # Set entry point
    graph.set_entry_point("fetch")

    # Conditional edge after fetch
    graph.add_conditional_edges(
        "fetch",
        should_continue_after_fetch,
        {
            "analyze": "match_analysis",
            "end": END
        }
    )

    # Parallel execution - both analysis nodes start after fetch
    # LangGraph handles parallel execution when multiple nodes
    # are connected from the same source
    graph.add_edge("fetch", "player_analysis")

    # Conditional edge after match analysis
    graph.add_conditional_edges(
        "match_analysis",
        should_continue_after_analysis,
        {
            "narrative": "narrative",
            "end": END
        }
    )

    # Player analysis also feeds into narrative
    graph.add_edge("player_analysis", "narrative")

    # Narrative goes to end
    graph.add_edge("narrative", END)

    return graph.compile()


# Build the graph once at module level
nba_pipeline = build_nba_graph()


def run_nba_analysis(
    team_or_game_id: str,
    persona: str = "espn_formal",
    force_refresh: bool = False
) -> SportsCastState:
    """
    Run the full NBA analysis pipeline with caching.

    Args:
        team_or_game_id: Team name or game ID
        persona: Analysis persona
        force_refresh: If True, bypass cache and re-analyze

    Returns:
        Final state containing all analysis results
    """

    print(f"\nStarting NBA analysis pipeline...")
    print(f"Input: {team_or_game_id}")
    print(f"Persona: {persona}")
    print("-" * 40)

    # Initial state
    initial_state = {
        "sport": "nba",
        "match_id": team_or_game_id,
        "raw_match_data": None,
        "match_analysis": None,
        "player_analysis": None,
        "narrative": None,
        "chat_history": [],
        "user_query": None,
        "chat_response": None,
        "persona": persona,
        "error": None,
    }

    # Run pipeline
    result = nba_pipeline.invoke(initial_state)

    # Save to cache if successful
    if not result.get("error") and result.get("narrative"):
        game_id = result.get("match_id")
        save_to_cache(game_id, "nba", result)

    return result