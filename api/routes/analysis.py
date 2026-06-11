import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from api.models.schemas import AnalyzeRequest, AnalyzeResponse, JobStatusResponse, JobStatus
from api.services.job_manager import (
    create_job, get_job, update_job_progress,
    complete_job, fail_job
)
from utils.cache import load_from_cache
from utils.cost_tracker import reset_session_cost, get_session_cost

router = APIRouter()

# Thread pool for running synchronous pipeline in async context
_executor = ThreadPoolExecutor(max_workers=4)


def _run_pipeline(job_id: str, sport: str, match_id: str, persona: str, force_refresh: bool):
    """
    Run the full analysis pipeline in a thread.
    Updates job progress as each agent completes.
    This runs in a thread pool so it doesn't block the event loop.
    """
    reset_session_cost()

    try:
        update_job_progress(job_id, f"Starting {sport.upper()} analysis...")

        # Check cache first unless force refresh
        if not force_refresh:
            cached = load_from_cache(match_id, sport)
            if cached:
                update_job_progress(job_id, "Loaded from cache instantly")
                game_id = cached.get("match_id", match_id)
                cache_key = f"{sport}_{game_id}"
                complete_job(job_id, cache_key, 0.0)
                return

        # Monkey-patch progress updates into the pipeline
        # We intercept the logger to capture agent start/complete events
        update_job_progress(job_id, f"Fetching {sport.upper()} data...")

        from graph import run_analysis
        result = run_analysis(
            sport=sport,
            match_id=match_id,
            persona=persona,
            force_refresh=force_refresh,
        )

        if result.get("error"):
            fail_job(job_id, result["error"])
            return

        update_job_progress(job_id, "Analysis complete")

        game_id = result.get("match_id", match_id)
        safe_id = game_id.replace("/", "_")
        cache_key = f"{sport}_{safe_id}"
        cost = get_session_cost()

        complete_job(job_id, cache_key, cost)

    except Exception as e:
        fail_job(job_id, str(e))


@router.post("/", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest):
    """
    Start a new analysis job.
    Returns job_id immediately — pipeline runs in background.
    Poll GET /analyze/{job_id} for status and results.
    """
    job_id = create_job(
        sport=request.sport.value,
        match_id=request.match_id,
        persona=request.persona.value,
    )

    # Run pipeline in thread pool — non-blocking
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_pipeline,
        job_id,
        request.sport.value,
        request.match_id,
        request.persona.value,
        request.force_refresh,
    )

    return AnalyzeResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"Analysis started for {request.sport.value} — {request.match_id}",
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_analysis_status(job_id: str):
    """
    Get the status and result of an analysis job.
    Poll this endpoint until status is 'complete' or 'failed'.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    result = None

    # If complete, load the full result from cache
    if job["status"] == JobStatus.COMPLETE and job.get("result_cache_key"):
        cache_key = job["result_cache_key"]
        parts = cache_key.split("_", 1)
        if len(parts) == 2:
            sport, game_id = parts[0], parts[1]
            cached = load_from_cache(game_id, sport)
            if cached:
                result = {
                    "match_id": cached.get("match_id"),
                    "narrative": cached.get("narrative"),
                    "match_analysis": cached.get("match_analysis"),
                    "player_analysis": cached.get("player_analysis"),
                    "persona": cached.get("persona"),
                    "raw_match_data": cached.get("raw_match_data"),
                    "match_date": cached.get("match_date"),
                }

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        sport=job.get("sport"),
        match_id=job.get("match_id"),
        progress=job.get("progress", []),
        result=result,
        error=job.get("error"),
        cost=job.get("cost"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@router.get("/{job_id}/stream")
async def stream_progress(job_id: str):
    """
    Stream real-time progress updates for a job using Server-Sent Events.
    Connect to this endpoint immediately after POST /analyze.
    Events arrive as each agent completes.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    async def event_generator():
        last_progress_count = 0

        while True:
            job = get_job(job_id)
            if not job:
                yield "data: {\"type\": \"error\", \"message\": \"Job not found\"}\n\n"
                break

            # Send any new progress messages
            progress = job.get("progress", [])
            while last_progress_count < len(progress):
                message = progress[last_progress_count]
                yield f"data: {{\"type\": \"progress\", \"message\": \"{message}\"}}\n\n"
                last_progress_count += 1

            # Check if done
            if job["status"] == JobStatus.COMPLETE:
                yield f"data: {{\"type\": \"complete\", \"job_id\": \"{job_id}\", \"cost\": {job.get('cost', 0)}}}\n\n"
                break

            if job["status"] == JobStatus.FAILED:
                error = job.get("error", "Unknown error")
                yield f"data: {{\"type\": \"failed\", \"error\": \"{error}\"}}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )