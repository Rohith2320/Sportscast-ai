from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class Sport(str, Enum):
    NBA = "nba"
    F1 = "f1"
    SOCCER = "soccer"
    VALORANT = "valorant"
    MLB = "mlb"


class Persona(str, Enum):
    ESPN_FORMAL = "espn_formal"
    TACTICAL_COACH = "tactical_coach"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# ─────────────────────────────────────────────
# REQUESTS
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    sport: Sport
    match_id: str = Field(
        default="latest",
        description="Match ID, team name, or 'latest'"
    )
    persona: Persona = Field(
        default=Persona.ESPN_FORMAL,
        description="Analysis persona"
    )
    force_refresh: bool = Field(
        default=False,
        description="Bypass cache and regenerate analysis"
    )


class ChatRequest(BaseModel):
    sport: Sport
    game_id: str = Field(
        description="Game ID from a completed analysis"
    )
    query: str = Field(
        description="User question about the game"
    )
    chat_history: List[dict] = Field(
        default=[],
        description="Previous messages in the conversation"
    )


# ─────────────────────────────────────────────
# RESPONSES
# ─────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    sport: Optional[str] = None
    match_id: Optional[str] = None
    progress: List[str] = []
    result: Optional[dict] = None
    error: Optional[str] = None
    cost: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    cost: float


class CachedGame(BaseModel):
    game_id: str
    sport: str
    match_id: Optional[str] = None
    cached_at: str
    has_narrative: bool
    title: Optional[str] = None
    match_date: Optional[str] = None
    narrative_excerpt: Optional[str] = None


class GamesResponse(BaseModel):
    games: List[CachedGame]
    total: int


class APIStatus(BaseModel):
    name: str
    status: str
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    cache_count: int
    apis: List[APIStatus]


class MetricsResponse(BaseModel):
    total_analyses: int
    total_cost: float
    cache_hits: int
    cache_misses: int
    by_sport: dict
    average_cost_per_analysis: float