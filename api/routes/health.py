import time
import requests
import os
from fastapi import APIRouter
from api.models.schemas import HealthResponse, APIStatus, MetricsResponse
from api.services.job_manager import get_metrics
from utils.cache import list_cached_games

router = APIRouter()


def _check_api(name: str, url: str, timeout: int = 5) -> APIStatus:
    """Check if an external API is reachable."""
    start = time.time()
    try:
        response = requests.get(url, timeout=timeout)
        latency = round((time.time() - start) * 1000, 1)
        if response.status_code < 500:
            return APIStatus(name=name, status="ok", latency_ms=latency)
        return APIStatus(name=name, status="degraded", latency_ms=latency)
    except Exception as e:
        return APIStatus(name=name, status="unreachable", latency_ms=None)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Check system health — API connectivity and cache status.
    """
    from api.main import get_start_time
    uptime = round(time.time() - get_start_time(), 1)

    # Check all external APIs
    apis = [
        _check_api("NBA Stats API", "https://stats.nba.com", timeout=5),
        _check_api(
            "F1 Jolpica API",
            "https://api.jolpi.ca/ergast/f1/current/last/results.json",
            timeout=10
        ),
        _check_api(
            "BSD Soccer API",
            "https://sports.bzzoiro.com/api/v2/events/?limit=1",
            timeout=5
        ),
        _check_api(
            "VLR Esports API",
            "https://vlr.orlandomm.net/api/v1/results?page=1",
            timeout=5
        ),
        _check_api(
            "MLB Stats API",
            "https://statsapi.mlb.com/api/v1/sports",
            timeout=5
        ),
    ]

    # Count cached games
    try:
        cached = list_cached_games()
        cache_count = len(cached)
    except Exception:
        cache_count = 0

    # Overall status
    unreachable = [a for a in apis if a.status == "unreachable"]
    if len(unreachable) >= 3:
        status = "degraded"
    else:
        status = "ok"

    return HealthResponse(
        status=status,
        uptime_seconds=uptime,
        cache_count=cache_count,
        apis=apis,
    )


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics_endpoint():
    """
    Get aggregate metrics — total analyses, costs, cache stats.
    """
    metrics = get_metrics()
    return MetricsResponse(**metrics)