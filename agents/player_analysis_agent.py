import os
from anthropic import Anthropic
from utils.state import SportsCastState
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def format_player_data(raw_data: dict) -> str:
    """
    Format raw player stats into clean readable text.
    Filters out DNP players.
    """

    player_stats = raw_data["player_stats"]
    headers = player_stats["headers"]

    def get_val(row, key):
        return row[headers.index(key)]

    players = player_stats["data"]
    formatted_players = []

    for player in players:
        mins = get_val(player, "MIN")
        pts = get_val(player, "PTS")

        # Skip DNP players
        if mins is None or pts is None:
            continue

        name = get_val(player, "PLAYER_NAME")
        team = get_val(player, "TEAM_ABBREVIATION")
        reb = get_val(player, "REB")
        ast = get_val(player, "AST")
        stl = get_val(player, "STL")
        blk = get_val(player, "BLK")
        tov = get_val(player, "TO")
        fgm = get_val(player, "FGM")
        fga = get_val(player, "FGA")
        fg_pct = get_val(player, "FG_PCT")
        fg3m = get_val(player, "FG3M")
        fg3a = get_val(player, "FG3A")
        ftm = get_val(player, "FTM")
        fta = get_val(player, "FTA")
        plus_minus = get_val(player, "PLUS_MINUS")
        position = get_val(player, "START_POSITION")

        pos_label = f"Starter ({position})" if position else "Bench"

        formatted_players.append(
            f"Player: {name} | Team: {team} | {pos_label}\n"
            f"Stats: {pts} PTS | {reb} REB | {ast} AST | "
            f"{stl} STL | {blk} BLK | {tov} TOV\n"
            f"Shooting: {fgm}/{fga} FG ({fg_pct:.1%}) | "
            f"{fg3m}/{fg3a} 3PT | {ftm}/{fta} FT\n"
            f"Plus/Minus: {plus_minus} | Minutes: {mins}"
        )

    return "\n\n".join(formatted_players)


def analyze_players(
    formatted_players: str,
    match_analysis: str,
    sport: str = "NBA"
) -> str:
    """
    Use Claude Sonnet to analyze individual player performances.
    Returns structured breakdown for each player.
    """

    prompt = f"""You are an expert {sport} analyst specializing in 
individual player evaluation and performance breakdown.

You have already produced the following match analysis:

=== MATCH CONTEXT ===
{match_analysis[:1000]}
====================

Now analyze each individual player's performance using both their 
statistics and the match context above.

Here are the player statistics:

{formatted_players}

For each player who played meaningful minutes (10+ minutes), produce 
a structured breakdown in exactly this format:

PLAYER: [Full Name]
TEAM: [Team Name]
RATING: [Excellent / Good / Average / Poor]
STATS: [Key stats in one line]
INSIGHT: [2-3 sentences of genuine analytical insight using match context]
IMPROVEMENT: [One specific area to improve]
---

Focus on players who had the most impact — both positive and negative.
Skip players with fewer than 10 minutes unless they had exceptional impact.
Be specific, analytical, and back every claim with statistics."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


def player_analysis_node(state: SportsCastState) -> dict:
    """
    LangGraph node that analyzes individual player performances.
    Reads raw_match_data and match_analysis from state.
    Writes player_analysis to state.
    """

    if state.get("error"):
        return {}

    raw_data = state["raw_match_data"]
    match_analysis = state["match_analysis"]
    sport = state.get("sport", "NBA").upper()

    try:
        print("Formatting player data...")
        formatted_players = format_player_data(raw_data)

        print("Sending to Claude for player analysis...")
        analysis = analyze_players(formatted_players, match_analysis, sport)

        print("Player analysis complete")
        return {"player_analysis": analysis}

    except Exception as e:
        print(f"Error in player analysis: {e}")
        return {"error": f"Player analysis failed: {str(e)}"}