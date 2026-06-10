"""
LangSmith traces endpoint.
GET /traces/latest — returns the URL of the most recent pipeline trace.
Gracefully returns null when LANGCHAIN_API_KEY is not configured.
"""
import os
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()


@router.get("/latest")
async def get_latest_trace():
    """
    Return the URL of the most recent LangSmith trace for this project.
    Used by the Analysis page to surface a 'View Pipeline Trace' link.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    project = os.getenv("LANGCHAIN_PROJECT", "sportscast-ai")

    if not api_key:
        return {
            "trace_url": None,
            "configured": False,
            "message": "Add LANGCHAIN_API_KEY to .env and LANGCHAIN_TRACING_V2=true to enable tracing",
        }

    try:
        from langsmith import Client
        client = Client(api_key=api_key)
        runs = list(client.list_runs(
            project_name=project,
            limit=1,
            is_root=True,
        ))
        if not runs:
            return {
                "trace_url": None,
                "configured": True,
                "message": "No traces found yet — run an analysis first",
            }
        run = runs[0]
        trace_url = f"https://smith.langchain.com/runs/{run.id}"
        return {
            "trace_url": trace_url,
            "configured": True,
            "run_id": str(run.id),
            "project": project,
        }
    except Exception as e:
        return {
            "trace_url": None,
            "configured": True,
            "message": f"LangSmith error: {str(e)}",
        }
