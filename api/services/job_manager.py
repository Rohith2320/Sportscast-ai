import uuid
import json
import os
import asyncio
from datetime import datetime
from typing import Optional
from api.models.schemas import JobStatus

JOBS_DIR = "jobs"


def _ensure_jobs_dir():
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)


def _job_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def _save_job(job: dict):
    _ensure_jobs_dir()
    with open(_job_path(job["job_id"]), "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)


def _load_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# IN-MEMORY INDEX (fast lookups)
# ─────────────────────────────────────────────

_jobs: dict[str, dict] = {}


def create_job(sport: str, match_id: str, persona: str) -> str:
    """
    Create a new analysis job.
    Returns job_id.
    """
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "sport": sport,
        "match_id": match_id,
        "persona": persona,
        "status": JobStatus.QUEUED,
        "progress": [],
        "result_cache_key": None,
        "cost": 0.0,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    _jobs[job_id] = job
    _save_job(job)
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """Get job by ID. Checks memory first, then disk."""
    if job_id in _jobs:
        return _jobs[job_id]
    job = _load_job(job_id)
    if job:
        _jobs[job_id] = job
    return job


def update_job_progress(job_id: str, message: str):
    """Add a progress message to a running job."""
    job = get_job(job_id)
    if not job:
        return
    job["progress"].append(f"{datetime.now().strftime('%H:%M:%S')} — {message}")
    job["status"] = JobStatus.RUNNING
    _jobs[job_id] = job
    _save_job(job)


def complete_job(job_id: str, cache_key: str, cost: float):
    """Mark a job as complete with its cache key and cost."""
    job = get_job(job_id)
    if not job:
        return
    job["status"] = JobStatus.COMPLETE
    job["result_cache_key"] = cache_key
    job["cost"] = cost
    job["completed_at"] = datetime.now().isoformat()
    _jobs[job_id] = job
    _save_job(job)


def fail_job(job_id: str, error: str):
    """Mark a job as failed with error message."""
    job = get_job(job_id)
    if not job:
        return
    job["status"] = JobStatus.FAILED
    job["error"] = error
    job["completed_at"] = datetime.now().isoformat()
    _jobs[job_id] = job
    _save_job(job)


def list_jobs(limit: int = 20) -> list:
    """List most recent jobs from memory."""
    jobs = list(_jobs.values())
    jobs.sort(key=lambda x: x["created_at"], reverse=True)
    return jobs[:limit]


def load_all_jobs_from_disk():
    """
    Called on server startup.
    Loads all jobs from disk into memory.
    Marks any 'running' jobs as failed since server restarted.
    """
    _ensure_jobs_dir()
    recovered = 0
    failed = 0

    for filename in os.listdir(JOBS_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(JOBS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                job = json.load(f)

            # Mark running jobs as failed — server restarted mid-analysis
            if job.get("status") in [JobStatus.RUNNING, JobStatus.QUEUED]:
                job["status"] = JobStatus.FAILED
                job["error"] = "Server restarted during analysis — please retry"
                job["completed_at"] = datetime.now().isoformat()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(job, f, indent=2)
                failed += 1
            else:
                recovered += 1

            _jobs[job["job_id"]] = job

        except Exception as e:
            print(f"Warning: Could not load job {filename}: {e}")

    print(f"Job manager: loaded {recovered} completed jobs, marked {failed} as failed")


def get_metrics() -> dict:
    """
    Aggregate metrics across all jobs.
    """
    all_jobs = list(_jobs.values())
    completed = [j for j in all_jobs if j["status"] == JobStatus.COMPLETE]
    failed = [j for j in all_jobs if j["status"] == JobStatus.FAILED]

    total_cost = sum(j.get("cost", 0.0) for j in completed)

    by_sport = {}
    for job in completed:
        sport = job.get("sport", "unknown")
        if sport not in by_sport:
            by_sport[sport] = {"count": 0, "total_cost": 0.0}
        by_sport[sport]["count"] += 1
        by_sport[sport]["total_cost"] += job.get("cost", 0.0)

    # Cache stats from cache directory
    cache_hits = sum(
        1 for j in all_jobs
        if j.get("result_cache_key") and
        j["status"] == JobStatus.COMPLETE
    )

    return {
        "total_analyses": len(completed),
        "total_cost": round(total_cost, 4),
        "cache_hits": cache_hits,
        "cache_misses": len(completed) - cache_hits,
        "by_sport": by_sport,
        "average_cost_per_analysis": round(
            total_cost / len(completed), 4
        ) if completed else 0.0,
        "total_failed": len(failed),
    }