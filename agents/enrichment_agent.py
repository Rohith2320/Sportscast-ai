import os
import re
from anthropic import Anthropic
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error
from utils.cost_tracker import track_cost
from utils.retry import with_retry
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_top_players(player_analysis: str, top_n: int = 3) -> list[dict]:
    """
    Parse structured player analysis to find top rated players.
    Uses pure Python - no LLM needed since output is already structured.

    Args:
        player_analysis: Structured player analysis text
        top_n: Number of top players to extract

    Returns:
        List of dicts with player name and their analysis section
    """

    # Split by the separator we defined in player analysis
    sections = player_analysis.split("---")

    rated_players = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract player name
        name_match = re.search(r"PLAYER:\s*(.+)", section)
        # Extract rating
        rating_match = re.search(r"RATING:\s*(.+)", section)

        if not name_match or not rating_match:
            continue

        name = name_match.group(1).strip()
        rating = rating_match.group(1).strip().lower()

        # Assign numeric score for sorting
        rating_score = {
            "excellent": 4,
            "good": 3,
            "average": 2,
            "poor": 1
        }.get(rating, 0)

        rated_players.append({
            "name": name,
            "rating": rating,
            "rating_score": rating_score,
            "section": section
        })

    # Sort by rating score descending, take top N
    rated_players.sort(key=lambda x: x["rating_score"], reverse=True)
    return rated_players[:top_n]


@with_retry(max_attempts=3, base_delay=1)
def enrich_player_sections(
    top_players: list[dict],
    match_analysis: str,
    sport: str = "NBA"
) -> str:
    """
    Enrich top player sections with match context.
    Returns updated player analysis with enriched top player sections.
    """

    if not top_players:
        return ""

    # Build enrichment prompt
    players_text = "\n\n---\n\n".join([p["section"] for p in top_players])
    player_names = ", ".join([p["name"] for p in top_players])

    prompt = f"""You are enriching existing player analysis for {sport} with 
additional match context.

Here is the match context:
=== MATCH CONTEXT ===
{match_analysis[:800]}
====================

Here are the top player sections that need enrichment:

{players_text}

For each player above, rewrite ONLY the INSIGHT field to weave in 
specific match context. Keep everything else exactly the same:
- PLAYER, TEAM, RATING, STATS, IMPROVEMENT stay identical
- Only INSIGHT gets updated with match context references

Return the enriched sections in the exact same format, separated by ---

Writing style:
- Use periods or commas instead of em dashes
- Be direct and specific
- Reference actual match events from the context
- Keep each INSIGHT to 2-3 sentences"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
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


def enrichment_node(state: SportsCastState) -> dict:
    """
    LangGraph node that enriches top player analyses with match context.
    Runs after both Match Analysis and Player Analysis complete.

    Reads: match_analysis, player_analysis from state
    Writes: player_analysis (enriched version) to state
    """

    if state.get("error"):
        return {}

    sport = state.get("sport", "nba").lower()
    match_analysis = state.get("match_analysis", "")
    player_analysis = state.get("player_analysis", "")

    # Sports without structured player analysis — skip enrichment
    non_enrichable = ["f1", "soccer", "football", "valorant", "mlb"]
    if sport in non_enrichable:
        start_time = log_agent_start("EnrichmentAgent")
        print(f"Skipping enrichment for {sport.upper()} — no structured player stats available")
        log_agent_complete("EnrichmentAgent", start_time)
        return {}

    # If either is missing, skip enrichment
    if not match_analysis or not player_analysis:
        return {}

    start_time = log_agent_start("EnrichmentAgent")

    try:
        # Find top 3 players using pure Python
        top_players = extract_top_players(player_analysis, top_n=3)

        if not top_players:
            print("No structured player sections found — skipping enrichment")
            log_agent_complete("EnrichmentAgent", start_time)
            return {}

        print(f"Enriching top {len(top_players)} players with match context...")
        player_names = [p["name"] for p in top_players]
        print(f"Players: {', '.join(player_names)}")

        # Enrich with LLM
        enriched_sections = enrich_player_sections(
            top_players,
            match_analysis,
            state.get("sport", "NBA").upper()
        )

        # Rebuild player analysis with enriched sections
        updated_analysis = player_analysis

        for i, player in enumerate(top_players):
            original_section = player["section"]
            enriched_parts = enriched_sections.split("---")
            if i < len(enriched_parts):
                enriched_section = enriched_parts[i].strip()
                if enriched_section:
                    updated_analysis = updated_analysis.replace(
                        original_section,
                        enriched_section
                    )

        log_agent_complete("EnrichmentAgent", start_time)
        return {"player_analysis": updated_analysis}

    except Exception as e:
        log_error("EnrichmentAgent", str(e))
        return {}