from fastapi import APIRouter, HTTPException
from api.models.schemas import ChatRequest, ChatResponse
from utils.cache import load_from_cache
from utils.cost_tracker import reset_session_cost, get_session_cost

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat with the analysis agent about a specific game.
    Requires a completed analysis in cache for the game_id.
    """

    # Load cached analysis
    cached = load_from_cache(request.game_id, request.sport.value)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for {request.sport.value} "
                f"game {request.game_id}. Run /analyze first."
            )
        )

    reset_session_cost()

    try:
        from agents.chat_agent import (
            classify_intent,
            build_smart_context,
            generate_chat_response,
            extract_players_from_analysis,
            find_player_in_query,
        )

        # Extract players from analysis
        players_in_game = extract_players_from_analysis(
            cached.get("player_analysis", "")
        )

        # Classify intent
        intent = classify_intent(request.query, request.chat_history)

        # Find player references
        player_in_query = len(
            find_player_in_query(request.query, players_in_game)
        ) > 0

        # Build context
        context = build_smart_context(
            query=request.query,
            state=cached,
            intent=intent,
            players_in_game=players_in_game,
        )

        # Generate response
        response = generate_chat_response(
            query=request.query,
            context=context,
            chat_history=request.chat_history,
            intent=intent,
            sport=request.sport.value.upper(),
            players_in_game=players_in_game,
            player_in_query=player_in_query,
        )

        cost = get_session_cost()

        return ChatResponse(
            response=response,
            intent=intent,
            cost=cost,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))