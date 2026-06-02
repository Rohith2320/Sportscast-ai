from typing import TypedDict, Optional, List

class SportsCastState(TypedDict):
    # Input fields
    sport: str
    match_id: str

    # RAW data from API
    raw_match_data: Optional[dict]

    # Agent outputs
    match_analysis: Optional[str]
    player_analysis: Optional[str]
    narrative: Optional[str]

    # Chat interface
    chat_history: List[dict]
    user_query: Optional[str]
    chat_response: Optional[str]

    # Error handling
    error: Optional[str]



