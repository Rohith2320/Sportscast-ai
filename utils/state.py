from typing import TypedDict, Optional, List, Annotated
import operator


class SportsCastState(TypedDict):
    # Input fields
    sport: str
    match_id: str

    # Raw data from API
    raw_match_data: Optional[dict]

    # Agent outputs
    match_analysis: Optional[str]
    player_analysis: Optional[str]
    narrative: Optional[str]

    # Chat interface
    chat_history: List[dict]
    user_query: Optional[str]
    chat_response: Optional[str]

    # Persona selection
    persona: Optional[str]

    # Error handling - Annotated allows multiple parallel writes
    error: Annotated[Optional[str], operator.or_]