import os
import re
from openai import OpenAI
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error
from utils.cost_tracker import track_cost
from utils.retry import with_retry
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> OpenAI:
    # Built on first use so importing this module doesn't require OPENAI_API_KEY
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


_mem0_client = None


def _get_memory():
    global _mem0_client
    if _mem0_client is None and os.getenv('MEM0_ENABLED', 'false').lower() == 'true':
        try:
            from mem0 import Memory
            _mem0_client = Memory()
        except Exception:
            pass
    return _mem0_client


# ─────────────────────────────────────────────
# INTENT CLASSIFICATION
# ─────────────────────────────────────────────

INTENT_TYPES = {
    "factual": "User wants a specific stat or fact from the game",
    "analytical": "User wants insight or explanation about what happened",
    "comparative": "User wants to compare two players or teams",
    "predictive": "User wants predictions or recommendations for future games",
    "emotional": "User is expressing a feeling or reaction about the game",
    "clarification": "User is asking for clarification on a previous answer",
    "out_of_scope": "User is asking about something unrelated to this game"
}


def classify_intent(query: str, chat_history: list[dict]) -> str:
    """
    Classify the intent of a user query.
    Uses pure Python pattern matching — no LLM needed.

    Returns intent type string.
    """
    query_lower = query.lower().strip()

    # Clarification — references previous conversation
    clarification_patterns = [
        "what do you mean", "can you explain", "tell me more",
        "elaborate", "what does that mean", "clarify",
        "that last", "previous answer", "you said", "you mentioned"
    ]
    if any(p in query_lower for p in clarification_patterns):
        return "clarification"

    # Emotional responses
    emotional_patterns = [
        "amazing", "incredible", "unbelievable", "wow", "insane",
        "great game", "terrible", "disappointing", "exciting",
        "love", "hate", "feel", "think about", "opinion"
    ]
    if any(p in query_lower for p in emotional_patterns):
        return "emotional"

    # Predictive queries
    predictive_patterns = [
        "next game", "game 2", "game 3", "game 4", "game 5",
        "predict", "what will", "what should", "going forward",
        "rest of series", "series", "championship", "finals",
        "recommend", "suggestion", "advice", "adjust", "change"
    ]
    if any(p in query_lower for p in predictive_patterns):
        return "predictive"

    # Comparative queries
    comparative_patterns = [
        "compare", " vs ", "versus", "better than", "worse than",
        "difference between", "who had more", "who had less",
        "who was better", "who was worse", "both players",
        "both teams", "head to head"
    ]
    if any(p in query_lower for p in comparative_patterns):
        return "comparative"
    
    # Why questions are always analytical - check before factual
    if query_lower.startswith("why") or " why " in query_lower:
        return "analytical"

    # Factual queries
    factual_patterns = [
        "how many", "how much", "what was", "what were",
        "score", "points", "rebounds", "assists", "steals",
        "blocks", "turnovers", "minutes", "percentage",
        "stats", "statistics", "did", "final score"
    ]
    if any(p in query_lower for p in factual_patterns):
        return "factual"

    # Out of scope detection
    out_of_scope_patterns = [
    "super bowl", "world series", "stanley cup",
    "career average", "all time", "last season",
    "trade", "contract", "salary", "draft",
    "other game", "another game", "different game",
    "weather", "temperature", "forecast",      # add these
    "stock", "crypto", "bitcoin",               # add these
    "news", "politics", "movie", "music"        # add these
    ]   
    if any(p in query_lower for p in out_of_scope_patterns):
        return "out_of_scope"

    # Default to analytical
    return "analytical"


# ─────────────────────────────────────────────
# PLAYER DETECTION
# ─────────────────────────────────────────────

def extract_players_from_analysis(player_analysis: str) -> list[str]:
    """
    Extract all player names from structured player analysis.
    Returns list of player names in this game.
    """
    if not player_analysis:
        return []

    names = re.findall(r"PLAYER:\s*(.+)", player_analysis)
    return [name.strip() for name in names]


def find_player_in_query(
    query: str,
    players_in_game: list[str]
) -> list[str]:
    """
    Find which players from this game are mentioned in the query.
    Returns list of matching player names.
    """
    query_lower = query.lower()
    matches = []

    for player in players_in_game:
        # Check full name and last name
        parts = player.split()
        if player.lower() in query_lower:
            matches.append(player)
        elif len(parts) >= 2 and parts[-1].lower() in query_lower:
            matches.append(player)

    return matches


def is_player_in_game(
    query: str,
    players_in_game: list[str]
) -> tuple[bool, list[str]]:
    """
    Check if query mentions a player and whether they played in this game.

    Returns:
        (player_found_in_game, matched_players)
    """
    matches = find_player_in_query(query, players_in_game)
    return len(matches) > 0, matches


# ─────────────────────────────────────────────
# SMART CONTEXT RETRIEVAL
# ─────────────────────────────────────────────

def extract_player_section(
    player_name: str,
    player_analysis: str
) -> str:
    """
    Extract the full analysis section for a specific player.
    Returns complete section without truncation.
    """
    if not player_analysis:
        return ""

    sections = player_analysis.split("---")

    for section in sections:
        if player_name.lower() in section.lower():
            # Also check last name
            last_name = player_name.split()[-1].lower()
            if last_name in section.lower():
                return section.strip()

    return ""


def build_smart_context(
    query: str,
    state: dict,
    intent: str,
    players_in_game: list[str]
) -> str:
    """
    Build query-aware context by pulling relevant sections.
    No fixed truncation — pulls exactly what the query needs.

    Args:
        query: User query
        state: Full pipeline state
        intent: Detected intent type
        players_in_game: List of players in this game

    Returns:
        Targeted context string
    """

    context_parts = []
    match_analysis = state.get("match_analysis", "")
    player_analysis = state.get("player_analysis", "")
    narrative = state.get("narrative", "")

    # Always include a brief game summary
    if narrative:
        context_parts.append(
            f"=== GAME SUMMARY ===\n{narrative[:300]}"
        )

    if intent == "factual":
        # For factual queries, check if asking about a specific player
        matched_players = find_player_in_query(query, players_in_game)

        if matched_players:
            # Pull full sections for mentioned players
            for player in matched_players:
                section = extract_player_section(player, player_analysis)
                if section:
                    context_parts.append(
                        f"=== {player.upper()} STATS ===\n{section}"
                    )
        else:
            # Team-level factual question
            if match_analysis:
                context_parts.append(
                    f"=== MATCH ANALYSIS ===\n{match_analysis[:1000]}"
                )

    elif intent == "analytical":
        # Full match analysis for analytical questions
        if match_analysis:
            context_parts.append(
                f"=== MATCH ANALYSIS ===\n{match_analysis}"
            )

        # Check if asking about specific player
        matched_players = find_player_in_query(query, players_in_game)
        for player in matched_players:
            section = extract_player_section(player, player_analysis)
            if section:
                context_parts.append(
                    f"=== {player.upper()} ANALYSIS ===\n{section}"
                )

    elif intent == "comparative":
        # Pull full sections for both players being compared
        matched_players = find_player_in_query(query, players_in_game)

        if matched_players:
            for player in matched_players:
                section = extract_player_section(player, player_analysis)
                if section:
                    context_parts.append(
                        f"=== {player.upper()} ===\n{section}"
                    )
        else:
            # Team comparison
            if match_analysis:
                context_parts.append(
                    f"=== MATCH ANALYSIS ===\n{match_analysis}"
                )

    elif intent == "predictive":
        # Full match analysis + all player analysis for predictions
        if match_analysis:
            context_parts.append(
                f"=== MATCH ANALYSIS ===\n{match_analysis}"
            )
        if player_analysis:
            context_parts.append(
                f"=== PLAYER ANALYSIS ===\n{player_analysis[:2500]}"
            )

    elif intent in ["emotional", "clarification"]:
        # For emotional/clarification, include narrative and recent analysis
        if match_analysis:
            context_parts.append(
                f"=== MATCH ANALYSIS ===\n{match_analysis[:800]}"
            )

    return "\n\n".join(context_parts)


# ─────────────────────────────────────────────
# CONVERSATION HISTORY MANAGEMENT
# ─────────────────────────────────────────────

def manage_history(chat_history: list[dict]) -> list[dict]:
    """
    Smart history management.
    After 8 turns, summarize older turns to preserve context
    without blowing the token budget.

    Returns managed history ready for LLM.
    """
    if len(chat_history) <= 8:
        return chat_history

    # Keep last 6 turns verbatim for immediate context
    recent = chat_history[-6:]

    # Summarize older turns into a single context message
    older = chat_history[:-6]
    summary_parts = []

    for turn in older:
        role = "User" if turn["role"] == "user" else "Assistant"
        # Truncate each turn to key content
        content = turn["content"][:150]
        summary_parts.append(f"{role}: {content}")

    summary = "Earlier in this conversation:\n" + "\n".join(summary_parts)

    # Prepend summary as a system-style context message
    managed = [{"role": "user", "content": summary},
               {"role": "assistant",
                "content": "Understood, I have that context."}]
    managed.extend(recent)

    return managed


# ─────────────────────────────────────────────
# RESPONSE FORMAT TEMPLATES
# ─────────────────────────────────────────────

FORMAT_INSTRUCTIONS = {
    "factual": """Answer in 1-2 sentences maximum.
Lead with the specific fact or number.
If the stat is not in the provided data, say exactly:
'That specific stat isn't in my data for this game.'
Never estimate or infer numbers.""",

    "analytical": """Answer in 2-3 focused paragraphs.
Start with your main claim, then support it with specific statistics.
End with one sentence of broader context or implication.
Never use bullet points for analytical responses.""",

    "comparative": """Structure your response as a clear comparison.
Cover the same categories for each player or team.
End with a one-sentence verdict on who was more impactful and why.
Use a parallel structure so the comparison is easy to follow.""",

    "predictive": """Give 3-4 specific, actionable recommendations.
Each recommendation must reference a pattern from this game.
Be analytical, not generic. 'Improve ball security' is generic.
'Reduce turnovers from De'Aaron Fox — his 4 giveaways directly
led to Knicks transition points' is specific.""",

    "emotional": """Match the user's energy briefly.
Acknowledge their reaction in one sentence.
Then pivot to one specific stat or moment that justifies the reaction.
Keep it conversational and brief.""",

    "clarification": """Directly address what needs clarification.
Reference the specific part of your previous answer.
Be more precise this time — add a stat or example that was missing.""",

    "out_of_scope": """Briefly acknowledge what they asked about.
If the query mentions a player NOT in this game, say so clearly.
Then redirect with: 'In this game, I can help with [relevant topic].'
Offer one specific thing they could ask about instead."""
}


# ─────────────────────────────────────────────
# GROUNDED RESPONSE GENERATOR
# ─────────────────────────────────────────────

@with_retry(max_attempts=3, base_delay=1)
def generate_chat_response(
    query: str,
    context: str,
    chat_history: list[dict],
    intent: str,
    sport: str,
    players_in_game: list[str],
    player_in_query: bool
) -> str:
    """
    Generate a grounded, formatted chat response using GPT-4o-mini.
    """

    format_instruction = FORMAT_INSTRUCTIONS.get(
        intent,
        FORMAT_INSTRUCTIONS["analytical"]
    )

    # Build player context note
    player_note = ""
    if not player_in_query and any(
        name_hint in query.lower()
        for name_hint in ["lebron", "curry", "durant", "james", "kobe"]
    ):
        player_note = """NOTE: The player mentioned is NOT in this game.
Acknowledge this briefly, then redirect to relevant players
who ARE in this game."""

    system_prompt = f"""You are a production-grade {sport} analyst assistant 
for a specific game. You have access to complete match data below.

CRITICAL GROUNDING RULES — never violate these:
1. Only use statistics explicitly present in the provided context
2. Never estimate, infer, or approximate any number
3. If a stat is missing, say: "That specific stat isn't in my data"
4. Never say "approximately", "around", "roughly" for statistics
5. Always cite which player or which team the stat belongs to
6. Players NOT listed in the context did NOT play in this game

{player_note}

RESPONSE FORMAT for this query type ({intent}):
{format_instruction}

WRITING STYLE:
- Conversational but authoritative
- Use player names, not pronouns alone
- Periods and commas only, never em dashes
- Never say "based on the analysis" or "according to the data"
- Just answer as an expert would

GAME CONTEXT:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add managed history
    managed_history = manage_history(chat_history)
    messages.extend(managed_history)

    # Add current query
    messages.append({"role": "user", "content": query})

    response = get_client().chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=600,
        messages=messages,
        temperature=0.7
    )

    track_cost(
        model="gpt-4o-mini",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens
    )

    return response.choices[0].message.content


# ─────────────────────────────────────────────
# MAIN CHAT NODE
# ─────────────────────────────────────────────

def chat_node(state: SportsCastState) -> dict:
    """
    Production-grade LangGraph chat node.

    Features:
    - 7-type intent classification
    - Smart query-aware context retrieval
    - Strict grounding with no hallucination
    - Consistent format per query type
    - Conversation history summarization
    - Player in/out of game detection
    """

    if state.get("error"):
        return {}

    user_query = state.get("user_query")
    if not user_query:
        return {}

    start_time = log_agent_start("ChatAgent")

    try:
        chat_history = state.get("chat_history", [])
        sport = state.get("sport", "NBA").upper()
        player_analysis = state.get("player_analysis", "")

        # Extract players in this game
        players_in_game = extract_players_from_analysis(player_analysis)

        # Classify intent
        intent = classify_intent(user_query, chat_history)
        print(f"Intent: {intent} | Players in game: {len(players_in_game)}")

        # Check if query mentions a player in this game
        player_found, matched_players = is_player_in_game(
            user_query,
            players_in_game
        )

        if matched_players:
            print(f"Players matched in query: {', '.join(matched_players)}")

        # Build smart context
        context = build_smart_context(
            query=user_query,
            state=dict(state),
            intent=intent,
            players_in_game=players_in_game
        )

        # Retrieve persistent memories if Mem0 is enabled
        memory = _get_memory()
        if memory:
            try:
                results = memory.search(user_query, user_id="sportscast_user")
                if results:
                    mem_lines = [r.get('memory', '') for r in results if r.get('memory')]
                    if mem_lines:
                        context = f"User preferences and history: {' | '.join(mem_lines)}\n\n" + context
            except Exception:
                pass

        # Generate grounded response
        response = generate_chat_response(
            query=user_query,
            context=context,
            chat_history=chat_history,
            intent=intent,
            sport=sport,
            players_in_game=players_in_game,
            player_in_query=player_found
        )

        # Update history
        updated_history = chat_history + [
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": response}
        ]

        # Store exchange in Mem0 if enabled
        if memory:
            try:
                memory.add(
                    f"User asked: {user_query}. About: {sport} game.",
                    user_id="sportscast_user"
                )
            except Exception:
                pass

        log_agent_complete("ChatAgent", start_time)

        return {
            "chat_response": response,
            "chat_history": updated_history
        }

    except Exception as e:
        log_error("ChatAgent", str(e))
        return {
            "chat_response": "I couldn't process that question. Please try again.",
            "chat_history": state.get("chat_history", [])
        }