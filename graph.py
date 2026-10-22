import os
from langgraph.graph import StateGraph, END
from utils.state import SportsCastState
from utils.cache import save_to_cache, load_from_cache

# ── LangSmith tracing — graceful no-op when LANGCHAIN_API_KEY is not set ──
try:
    from langsmith import traceable as _langsmith_traceable
    _LANGSMITH_ENABLED = bool(os.getenv("LANGCHAIN_API_KEY"))
except ImportError:
    _langsmith_traceable = None
    _LANGSMITH_ENABLED = False
from data_sources.nba_fetcher import nba_fetch_node
from data_sources.f1_fetcher import f1_fetch_node
from data_sources.soccer_fetcher import soccer_fetch_node
from data_sources.valorant_fetcher import valorant_fetch_node
from data_sources.mlb_fetcher import mlb_fetch_node
from agents.match_analysis_agent import match_analysis_node
from agents.player_analysis_agent import player_analysis_node
from agents.enrichment_agent import enrichment_node
from agents.narrative_agent import narrative_node


# ─────────────────────────────────────────────
# CONDITIONAL EDGES
# ─────────────────────────────────────────────

def route_to_fetch(state: SportsCastState) -> str:
    """Route to correct fetch node based on sport."""
    sport = state.get("sport", "nba").lower()
    routes = {
        "nba": "nba_fetch",
        "f1": "f1_fetch",
        "soccer": "soccer_fetch",
        "football": "soccer_fetch",
        "valorant": "valorant_fetch",
        "valo": "valorant_fetch",
        "mlb": "mlb_fetch",
        "baseball": "mlb_fetch",
    }
    return routes.get(sport, "nba_fetch")


def should_continue_after_fetch(state: SportsCastState) -> str:
    """After fetch — continue or end on error."""
    if state.get("error"):
        print(f"Pipeline stopping: {state['error']}")
        return "end"
    return "analyze"


def should_continue_after_analysis(state: SportsCastState) -> str:
    """After analysis — continue to narrative or end."""
    if state.get("error"):
        print(f"Pipeline stopping: {state['error']}")
        return "end"
    if not state.get("match_analysis"):
        print("Match analysis missing, skipping narrative")
        return "end"
    return "narrative"


# ─────────────────────────────────────────────
# ROUTER NODE
# ─────────────────────────────────────────────

def router_node(state: SportsCastState) -> dict:
    """
    Entry point node. Acts as routing hub.
    Conditional edge handles actual routing to sport-specific fetch node.
    """
    return {}


# ─────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────

def build_sportscast_graph() -> StateGraph:
    """
    Build the full multi-sport SportsCast AI pipeline.

    Graph structure:
    START
      ↓
    router
      ↓          ↓
    nba_fetch   f1_fetch   (more sports added here)
      ↓          ↓
    [match_analysis + player_analysis] (parallel)
      ↓
    enrichment
      ↓
    narrative
      ↓
    END
    """

    graph = StateGraph(SportsCastState)

    # Router entry point
    graph.add_node("router", router_node)

    # Sport-specific fetch nodes
    graph.add_node("nba_fetch", nba_fetch_node)
    graph.add_node("f1_fetch", f1_fetch_node)
    graph.add_node("soccer_fetch", soccer_fetch_node)
    graph.add_node("valorant_fetch", valorant_fetch_node)
    graph.add_node("mlb_fetch", mlb_fetch_node)

    # Shared analysis nodes
    graph.add_node("match_analysis", match_analysis_node)
    graph.add_node("player_analysis", player_analysis_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("narrative", narrative_node)

    # Entry point is router
    graph.set_entry_point("router")

    # Router branches to correct fetch node
    graph.add_conditional_edges(
        "router",
        route_to_fetch,
        {
            "nba_fetch": "nba_fetch",
            "f1_fetch": "f1_fetch",
            "soccer_fetch": "soccer_fetch",
            "valorant_fetch": "valorant_fetch",
            "mlb_fetch": "mlb_fetch",
        }
    )

    # After NBA fetch — parallel analysis
    graph.add_conditional_edges(
        "nba_fetch",
        should_continue_after_fetch,
        {
            "analyze": "match_analysis",
            "end": END
        }
    )
    graph.add_edge("nba_fetch", "player_analysis")

    # After F1 fetch — parallel analysis
    graph.add_conditional_edges(
        "f1_fetch",
        should_continue_after_fetch,
        {
            "analyze": "match_analysis",
            "end": END
        }
    )
    graph.add_edge("f1_fetch", "player_analysis")

    # After Soccer fetch — parallel analysis
    graph.add_conditional_edges(
        "soccer_fetch",
        should_continue_after_fetch,
        {
            "analyze": "match_analysis",
            "end": END
        }
    )
    graph.add_edge("soccer_fetch", "player_analysis")

    # After Valorant fetch — parallel analysis
    graph.add_conditional_edges(
        "valorant_fetch",
        should_continue_after_fetch,
        {
            "analyze": "match_analysis",
            "end": END
        }
    )

    graph.add_edge("valorant_fetch", "player_analysis")

    graph.add_conditional_edges(
        "mlb_fetch",
        should_continue_after_fetch,
        {"analyze": "match_analysis", "end": END}
    )
    graph.add_edge("mlb_fetch", "player_analysis")

    # Both analysis nodes feed into enrichment
    graph.add_edge("match_analysis", "enrichment")
    graph.add_edge("player_analysis", "enrichment")

    # Enrichment to narrative
    graph.add_conditional_edges(
        "enrichment",
        should_continue_after_analysis,
        {
            "narrative": "narrative",
            "end": END
        }
    )

    graph.add_edge("narrative", END)

    return graph.compile()


# Build once at module level
sportscast_pipeline = build_sportscast_graph()


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def _run_analysis_impl(
    sport: str,
    match_id: str,
    persona: str = "espn_formal",
    force_refresh: bool = False
) -> SportsCastState:
    """
    Run the full SportsCast analysis pipeline for any sport.

    Args:
        sport: "nba", "f1", "nfl", "soccer", "valorant"
        match_id: Match identifier, team name, or "latest"
        persona: Analysis persona
        force_refresh: Bypass cache

    Returns:
        Final state with complete analysis
    """

    # Check cache first
    if not force_refresh:
        cached = load_from_cache(match_id, sport)
        if cached:
            print(f"Loaded from cache: {sport} {match_id}")
            return cached

    print(f"\nStarting {sport.upper()} analysis pipeline...")
    print(f"Input: {match_id} | Persona: {persona}")
    print("-" * 40)

    # Validate inputs
    if not sport:
        return {"error": "Sport is required", "narrative": None}
    if not match_id:
        return {"error": "Match ID or team name is required", "narrative": None}

    initial_state = {
        "sport": sport,
        "match_id": match_id,
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

    result = sportscast_pipeline.invoke(
        initial_state,
        {"recursion_limit": 25}
    )

    # Cache successful results
    if not result.get("error") and result.get("narrative"):
        game_id = result.get("match_id", match_id)
        save_to_cache(game_id, sport, result)

    return result


# Apply LangSmith @traceable when API key is configured
if _LANGSMITH_ENABLED and _langsmith_traceable:
    run_analysis = _langsmith_traceable(
        name="SportsCast Analysis Pipeline",
        run_type="chain",
    )(_run_analysis_impl)
else:
    run_analysis = _run_analysis_impl


def run_nba_analysis(
    team_or_game_id: str,
    persona: str = "espn_formal",
    force_refresh: bool = False
) -> SportsCastState:
    """Backward compatible wrapper for NBA analysis."""
    return run_analysis("nba", team_or_game_id, persona, force_refresh)
