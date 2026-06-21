import os
from anthropic import Anthropic
from utils.state import SportsCastState
from dotenv import load_dotenv
from utils.logger import log_agent_start, log_agent_complete, log_error
from utils.cost_tracker import track_cost
from utils.retry import with_retry

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

@with_retry(max_attempts=3, base_delay=1)
def analyze_players(
    formatted_players: str,
    match_analysis: str,
    sport: str = "NBA"
) -> str:
    """
    Use Claude Sonnet to analyze individual player performances.
    Prompt is sport-aware — each sport gets analysis matched to
    the data actually available.
    """

    match_context_section = f"""You have already produced the following match analysis:

=== MATCH CONTEXT ===
{match_analysis[:1000]}
====================

Use this context when analyzing individual performances.""" if match_analysis else ""

    sport_upper = sport.upper()

    # ── NBA — full structured breakdown, used by enrichment agent ──
    if sport_upper == "NBA":
        task = """For each player who played meaningful minutes (10+ minutes), produce
a structured breakdown in exactly this format:

PLAYER: [Full Name]
TEAM: [Team Name]
RATING: [Excellent / Good / Average / Poor]
STATS: [Key stats in one line]
INSIGHT: [2-3 sentences of genuine analytical insight using match context]
IMPROVEMENT: [One specific area to improve]
---

Focus on players who had the most impact, both positive and negative.
Skip players with fewer than 10 minutes unless they had exceptional impact."""

    # ── MLB — pitcher-first, uses real batting and pitching data ──
    elif sport_upper == "MLB":
        task = """Analyze the key performers in this game. Follow this structure:

First cover the starting pitchers for both teams:
- Name, innings pitched, strikeouts, earned runs, hits allowed
- Was this a quality start? How did they attack hitters?
- What does the linescore tell you about when they struggled or dominated?

Then cover the key offensive performers — only batters with hits, RBI, or home runs:
- Name, batting line (hits/at-bats), RBI, runs, home runs
- What did their contribution mean for the game outcome?

Finally identify the one player whose performance most decided the result.

Separate sections with ---
Do not invent statistics. Only reference numbers from the data provided."""

    # ── F1 — driver performance using race position and strategy data ──
    elif sport_upper == "F1":
        task = """Analyze driver performances across three categories:

WINNER ANALYSIS:
How did the winning driver win? Reference qualifying position vs finish position.
What strategic decisions were decisive? Back every claim with lap times or position data.

NOTABLE MOVERS:
Identify 2-3 drivers who gained or lost the most positions during the race.
What caused those position changes?

BIGGEST DISAPPOINTMENT:
Which driver underperformed relative to their starting position or team expectations?
Use qualifying vs race result as the benchmark.

Separate sections with ---
Only reference data from the race results and linescore provided."""

    # ── Soccer — incidents only, no invented individual stats ──
    elif sport_upper in ["SOCCER", "FOOTBALL"]:
        task = """Analyze only the players who appear in the match incidents data.

For each goal scorer: who scored, what minute, was it a decisive goal?
For each assist provider: how did they create the chance?
For each player who received a card: what impact did it have on the match?
For key substitutions: did the substitute change the game?

If a player is not mentioned in the incidents, do not analyze them.
Do not invent pass completion rates, shot accuracy, or any statistic
not explicitly present in the data above.

End with one paragraph identifying the single most impactful player
based only on what the incidents data shows."""

    # ── Valorant — roster context, uses Claude's knowledge of teams ──
    elif sport_upper == "VALORANT":
        task = """Analyze team and player performances using the match result
and your knowledge of these teams and players.

For the winning team:
- Which player was likely the primary carry based on their known role?
- What agent composition does this team typically run?
- How does their playstyle match up against the losing team?

For the losing team:
- Which player had the most pressure to perform?
- Where does their tactical system typically break down against this opponent?

Be specific about player IGNs. Reference known roles and tendencies.
Clearly frame insights as based on team knowledge, not match statistics."""

    # ── Default fallback ──
    else:
        task = """Analyze the key performers in this match.
For each significant player cover their contribution, impact on the result,
and one area for improvement. Separate sections with ---"""

    prompt = f"""You are an expert {sport} analyst specializing in
individual player evaluation and performance breakdown.

{match_context_section}

Here is the match data:

{formatted_players}

{task}

Writing style requirements:
- Use periods or commas instead of em dashes
- Never use: notably, crucially, underscore, delve, encapsulate, it is worth noting
- Vary sentence length
- Write like a human sports journalist, not an AI assistant
- Be direct. Say what happened without announcing you are about to say it."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
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


def player_analysis_node(state: SportsCastState) -> dict:
    """
    LangGraph node that analyzes individual player performances.
    Reads raw_match_data and match_analysis from state.
    Writes player_analysis to state.
    """

    if state.get("error"):
        return {}

    raw_data = state["raw_match_data"]
    match_analysis = state.get("match_analysis") or ""
    sport = state.get("sport", "nba").lower()

    start_time = log_agent_start("PlayerAnalysisAgent")

    try:
        print("Formatting player data...")

        # Route to correct formatter based on sport
        if sport == "f1":
            from data_sources.f1_fetcher import format_f1_data
            formatted_players = format_f1_data(raw_data)
        elif sport in ["soccer", "football"]:
            from data_sources.soccer_fetcher import format_soccer_data
            formatted_players = (
                format_soccer_data(raw_data) +
                "\n\n=== NOTE FOR ANALYSIS ===\n"
                "Individual player statistics are not available for this match "
                "on the free data tier. Base player analysis on the goal scorers, "
                "assist providers, cards, and substitutions from the incidents data above. "
                "For players not mentioned in incidents, note their presence in the lineup "
                "without inventing statistics."
            )
        elif sport == "valorant":
            from data_sources.valorant_fetcher import format_valorant_data
            formatted_players = format_valorant_data(raw_data)
        elif sport == "mlb":
            from data_sources.mlb_fetcher import format_mlb_data
            formatted_players = format_mlb_data(raw_data)
        else:
            formatted_players = format_player_data(raw_data)

        playoff_ctx = raw_data.get('playoff_context', {})
        if playoff_ctx.get('is_playoff'):
            playoff_header = (
                f"=== PLAYOFF CONTEXT ===\n"
                f"This is a {playoff_ctx.get('round', 'playoff')} game "
                f"(Game {playoff_ctx.get('game_in_series', '?')}).\n"
                f"=== END PLAYOFF CONTEXT ===\n\n"
            )
            formatted_players = playoff_header + formatted_players

        print("Sending to Claude for player analysis...")
        analysis = analyze_players(formatted_players, match_analysis, sport)

        log_agent_complete("PlayerAnalysisAgent", start_time)
        return {"player_analysis": analysis}

    except Exception as e:
        log_error("PlayerAnalysisAgent", str(e))
        return {"error": f"Player analysis failed: {str(e)}"}