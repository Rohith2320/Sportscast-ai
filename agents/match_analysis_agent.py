import os
from anthropic import Anthropic
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.cost_tracker import track_cost
from utils.retry import with_retry
from dotenv import load_dotenv

load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def format_nba_data(raw_data: dict) -> str:
    """
    Format raw NBA data into clean readable text for the LLM.
    We only extract what matters for analysis.
    """

    team_stats = raw_data["team_stats"]
    player_stats = raw_data["player_stats"]

    headers_team = team_stats["headers"]
    headers_player = player_stats["headers"]

    # Helper to get value by header name
    def get_val(row, headers, key):
        return row[headers.index(key)]

    # Extract team summaries
    teams = team_stats["data"]
    team_summaries = []

    for team in teams:
        name = get_val(team, headers_team, "TEAM_NAME")
        pts = get_val(team, headers_team, "PTS")
        reb = get_val(team, headers_team, "REB")
        ast = get_val(team, headers_team, "AST")
        stl = get_val(team, headers_team, "STL")
        blk = get_val(team, headers_team, "BLK")
        tov = get_val(team, headers_team, "TO")
        fg_pct = get_val(team, headers_team, "FG_PCT")
        fg3_pct = get_val(team, headers_team, "FG3_PCT")

        team_summaries.append(
            f"{name}: {pts} PTS | {reb} REB | {ast} AST | "
            f"{stl} STL | {blk} BLK | {tov} TOV | "
            f"FG%: {fg_pct:.1%} | 3P%: {fg3_pct:.1%}"
        )

    # Extract top performers (players with minutes played)
    players = player_stats["data"]
    top_performers = []

    for player in players:
        mins = get_val(player, headers_player, "MIN")
        pts = get_val(player, headers_player, "PTS")

        # Skip DNP players
        if mins is None or pts is None:
            continue

        name = get_val(player, headers_player, "PLAYER_NAME")
        team = get_val(player, headers_player, "TEAM_ABBREVIATION")
        reb = get_val(player, headers_player, "REB")
        ast = get_val(player, headers_player, "AST")
        stl = get_val(player, headers_player, "STL")
        blk = get_val(player, headers_player, "BLK")
        plus_minus = get_val(player, headers_player, "PLUS_MINUS")

        top_performers.append(
            f"{name} ({team}): {pts} PTS | {reb} REB | "
            f"{ast} AST | {stl} STL | {blk} BLK | +/-: {plus_minus} "
            f"in {mins}"
        )

    # Build final formatted string
    formatted = "=== TEAM STATISTICS ===\n"
    formatted += "\n".join(team_summaries)
    formatted += "\n\n=== PLAYER STATISTICS ===\n"
    formatted += "\n".join(top_performers)

    return formatted

@with_retry(max_attempts=3, base_delay=1)
def analyze_match(formatted_data: str, sport: str = "NBA") -> str:
    """
    Use Claude Sonnet to analyze the match data.
    Returns structured analysis as a string.
    """

    prompt = f"""You are an expert {sport} analyst with deep knowledge of 
basketball tactics, player performance, and game flow. You have been 
provided with the complete box score data from a recent {sport} game.

Your job is to produce a thorough, insightful match analysis that goes 
beyond the numbers to tell the story of the game.

Here is the match data:

{formatted_data}

Produce a structured analysis with exactly these four sections:

1. GAME OVERVIEW
   Summarize the final result and the overall narrative of the game in 
   2-3 sentences. Which team controlled the game?

2. KEY TURNING POINTS
   Identify 2-3 specific moments or patterns in the data that decided 
   the outcome. Back every point with specific statistics.

3. TEAM PERFORMANCE
   Analyze both teams' performance across the key statistical categories.
   What did each team do well? Where did they struggle?

4. DECISIVE FACTORS
   What were the 2-3 most important factors that determined the winner?
   Be specific and analytical.

Write at the level of a professional sports journalist. Be specific, 
use the actual player names and statistics, and provide genuine insight 
rather than generic observations.

Writing style requirements:
- Use periods or commas instead of em dashes
- Never use these words: notably, crucially, underscore, delve, encapsulate, it is worth noting, it is important to note
- Vary sentence length. Mix short punchy sentences with longer analytical ones.
- Write like a human sports journalist, not an AI assistant
- Never start consecutive sentences with "The"
- Be direct. Say what happened. Do not announce that you are about to say it.
- Avoid overly long sentences with multiple clauses strung together

"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Track cost
    track_cost(
        model="claude-sonnet-4-6",
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens
    )

    return message.content[0].text


def match_analysis_node(state: SportsCastState) -> dict:
    if state.get("error"):
        return {}

    raw_data = state["raw_match_data"]
    sport = state.get("sport", "nba").lower()

    start_time = log_agent_start("MatchAnalysisAgent")

    try:
        print("Formatting match data...")

        # Route to correct formatter based on sport
        if sport == "f1":
            from data_sources.f1_fetcher import format_f1_data
            formatted_data = format_f1_data(raw_data)
        elif sport in ["soccer", "football"]:
            from data_sources.soccer_fetcher import format_soccer_data
            formatted_data = format_soccer_data(raw_data)
        elif sport == "valorant":
            from data_sources.valorant_fetcher import format_valorant_data
            formatted_data = format_valorant_data(raw_data)
        elif sport == "mlb":
            from data_sources.mlb_fetcher import format_mlb_data
            formatted_data = format_mlb_data(raw_data)
        else:
            formatted_data = format_nba_data(raw_data)

        print("Sending to Claude for analysis...")
        analysis = analyze_match(formatted_data, sport)

        log_agent_complete("MatchAnalysisAgent", start_time)
        return {"match_analysis": analysis}

    except Exception as e:
        log_error("MatchAnalysisAgent", str(e))
        return {"error": f"Match analysis failed: {str(e)}"}