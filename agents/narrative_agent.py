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
    player_analysis: str,
    sport: str = "nba"
) -> str:
    """
    Extract the most important elements from both analyses.
    Token limits are sport-aware — data-rich sports get more context.
    """

    # Sport-aware token limits
    # MLB and F1 have rich structured data that needs more context
    # NBA has dense player stats that benefit from longer player summary
    match_limits = {
        "mlb": 1500,
        "f1": 1500,
        "soccer": 1200,
        "nba": 800,
        "valorant": 800,
    }
    player_limits = {
        "mlb": 1200,
        "f1": 1200,
        "soccer": 800,
        "nba": 1000,
        "valorant": 800,
    }

    sport_lower = sport.lower()
    match_limit = match_limits.get(sport_lower, 800)
    player_limit = player_limits.get(sport_lower, 1000)

    match_summary = match_analysis[:match_limit]
    player_summary = player_analysis[:player_limit]

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

    # Sport-specific structure guidance
    if sport.upper() == "F1":
        structure_guide = """Write a compelling F1 race narrative of 4 paragraphs:

PARAGRAPH 1 - OPENING HOOK:
Start with the single most unexpected or memorable thing about this race.
Not the winner's name. The thing that made this race different from others.

PARAGRAPH 2 - THE RACE WINNER:
Dedicate this paragraph entirely to the winning driver.
How specifically did they win - strategy, pace, overtakes, or survival?
Reference qualifying position vs finish position. Back every claim with specifics.

PARAGRAPH 3 - THE KEY MOMENT:
The single strategic or on-track moment that decided the race.
Pit stop timing, safety car, overtake, retirement of a rival - be specific.
Also address the biggest loser - who had the most to lose and why.

PARAGRAPH 4 - CHAMPIONSHIP IMPLICATIONS:
What does this result mean for the championship standings?
Must reference specific points gaps from the data.
End with one sentence about what the next race needs to produce."""

    elif sport.upper() == "VALORANT":
        structure_guide = """Write a compelling Valorant esports match narrative of 4 paragraphs:

PARAGRAPH 1 - OPENING HOOK:
Start with the single most interesting thing about this match result.
Reference the tournament context and what this result means for both teams.

PARAGRAPH 2 - THE WINNING TEAM:
Analyze the winning team's performance using your knowledge of their
players, typical agent compositions, and strategic tendencies.
Reference specific players by IGN and their known roles/strengths.

PARAGRAPH 3 - THE TACTICAL STORY:
Based on your knowledge of both teams' playstyles, explain HOW this
result likely happened. Agent compositions, map preferences, economic
strategies. Be specific about known team tendencies.

PARAGRAPH 4 - TOURNAMENT IMPLICATIONS:
What does this result mean for Masters London 2026?
Reference the tournament format and standings implications.
End with what both teams need to do next."""

    elif sport.upper() == "MLB":
        structure_guide = """Write a compelling MLB game narrative of 4 paragraphs:

PARAGRAPH 1 - OPENING HOOK:
Start with the single most interesting thing about this game.
The comeback, the dominant pitching, the late-inning heroics.
Not just the final score.

PARAGRAPH 2 - THE STARTING PITCHER:
MLB narratives center on pitching. Dedicate this paragraph to
the most dominant pitcher in the game. Innings pitched, strikeouts,
hits allowed. How did he attack hitters? What did the linescore show?

PARAGRAPH 3 - THE TURNING POINT:
Identify the exact inning where the game turned.
Reference the linescore data directly. Who got the key hit?
What was the score before and after that inning?

PARAGRAPH 4 - WHAT THIS MEANS:
What does this result reveal about both teams?
Reference specific players and stats from THIS game.
End with one sentence a fan of the losing team would find painful but accurate."""

    else:
        structure_guide = f"""Write a compelling {sport} game narrative of 4 paragraphs:

PARAGRAPH 1 - OPENING HOOK:
Start with the single most interesting or unexpected thing about this game.
Not the final score. Not "Team A beat Team B." The thing that makes this game
memorable. One or two punchy sentences that make the reader want to continue.

PARAGRAPH 2 - THE STAR PLAYER:
Dedicate this paragraph entirely to the most impactful player on the winning team.
How specifically did they beat the opposing team? What did they do that the defense
had no answer for? Back every claim with specific statistics.

PARAGRAPH 3 - THE TURNING POINT:
Identify the single moment or sequence that decided this game. Be specific about
when it happened, who was involved, and what the score was at that moment.
Also address the losing team - which of their players gave them the best chance
to win, and why it wasn't enough.

PARAGRAPH 4 - WHAT THIS MEANS:
One paragraph about what this result reveals about both teams going forward.
Must reference something specific from THIS game - not generic team identity statements.
End with one sentence that a fan of the losing team would find painful but accurate."""

    prompt = f"""You are writing the final broadcast commentary for a {sport} race/game.

Your writing persona:
{persona["instructions"]}

Here is the analysis to base your commentary on:

{storylines}

{structure_guide}

Writing style requirements:
- Use periods or commas instead of em dashes
- Never use: notably, crucially, underscore, delve, encapsulate, it is worth noting
- Vary sentence length. Short punchy sentences alongside longer analytical ones.
- Write like a human journalist, not an AI assistant
- Be direct. Say what happened without announcing you are about to say it.
- Every paragraph must contain at least two specific statistics from the data."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
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
        storylines = extract_key_storylines(match_analysis, player_analysis, sport.lower())
        narrative = generate_narrative(storylines, sport, persona_key)

        log_agent_complete("NarrativeAgent", start_time)
        return {"narrative": narrative}

    except Exception as e:
        log_error("NarrativeAgent", str(e))
        return {"error": f"Narrative generation failed: {str(e)}"}