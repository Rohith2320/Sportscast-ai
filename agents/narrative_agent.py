import os
from anthropic import Anthropic
from utils.state import SportsCastState
from utils.personas import get_persona
from utils.logger import log_agent_start, log_agent_complete, log_error
from utils.cost_tracker import track_cost
from utils.retry import with_retry
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_key_storylines(
    match_analysis: str,
    player_analysis: str
) -> str:
    """
    Extract the most important elements from both analyses.
    We summarize to avoid sending too many tokens to the Narrative Agent.
    """

    # Take first 800 chars of match analysis - covers overview and key turning points
    match_summary = match_analysis[:800]

    # Take first 1000 chars of player analysis - covers top performers
    player_summary = player_analysis[:1000]

    return f"""=== MATCH CONTEXT ===
{match_summary}

=== TOP PERFORMER CONTEXT ===
{player_summary}"""


@with_retry(max_attempts=3, base_delay=1)
def generate_narrative(
    storylines: str,
    sport: str,
    persona_key: str
) -> str:
    """
    Use Claude Sonnet to generate broadcast-quality narrative commentary.

    Args:
        storylines: Extracted key storylines from match and player analysis
        sport: Sport name for terminology context
        persona_key: Which persona style to use

    Returns:
        Final narrative commentary as string
    """

    persona = get_persona(persona_key)

    prompt = f"""You are writing the final broadcast commentary for a {sport} game.

Your writing persona:
{persona["instructions"]}

Here is the analysis to base your commentary on:

{storylines}

Write a compelling {sport} game narrative of 3-4 paragraphs.

Requirements:
- Open with a strong hook that captures the essence of the game
- Weave match context and individual performances together naturally
- Build toward a conclusion that captures what this result means
- Use specific names and statistics to back every claim
- Make it feel like something worth reading, not a stat summary

Writing style requirements:
- Use periods or commas instead of em dashes
- Never use: notably, crucially, underscore, delve, encapsulate, it is worth noting
- Vary sentence length. Short punchy sentences alongside longer analytical ones.
- Write like a human journalist, not an AI assistant
- Be direct. Say what happened without announcing you are about to say it."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    track_cost(
        model="claude-sonnet-4-6",
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens
    )

    return message.content[0].text


def narrative_node(state: SportsCastState) -> dict:
    """
    LangGraph node that generates final narrative commentary.
    Reads match_analysis, player_analysis, persona from state.
    Writes narrative to state.
    """

    if state.get("error"):
        return {}

    match_analysis = state["match_analysis"]
    player_analysis = state["player_analysis"]
    sport = state.get("sport", "NBA").upper()
    persona_key = state.get("persona", "espn_formal")

    start_time = log_agent_start("NarrativeAgent")

    try:
        print(f"Generating narrative in '{persona_key}' style...")
        storylines = extract_key_storylines(match_analysis, player_analysis)
        narrative = generate_narrative(storylines, sport, persona_key)

        log_agent_complete("NarrativeAgent", start_time)
        return {"narrative": narrative}

    except Exception as e:
        log_error("NarrativeAgent", str(e))
        return {"error": f"Narrative generation failed: {str(e)}"}