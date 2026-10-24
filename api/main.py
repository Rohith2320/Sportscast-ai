import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.services.job_manager import load_all_jobs_from_disk
from api.routes import analysis, chat, games, health, discovery, tts, traces

load_dotenv()

# Server start time for uptime tracking
START_TIME = time.time()


# ─────────────────────────────────────────────
# LIFESPAN — startup and shutdown events
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: load jobs from disk, verify environment.
    Shutdown: clean up resources.
    """
    print("=" * 50)
    print("SportsCast AI — Starting up")
    print("=" * 50)

    # Verify required environment variables
    critical_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    optional_keys = ["BSD_API_KEY", "ELEVENLABS_API_KEY"]
    missing_critical = [k for k in critical_keys if not os.getenv(k)]
    missing_optional = [k for k in optional_keys if not os.getenv(k)]

    if missing_critical:
        print("!" * 50)
        print(f"CRITICAL: Missing required API keys: {missing_critical}")
        print("The analysis pipeline WILL FAIL without these keys.")
        print("Set them in your .env file or environment before starting.")
        print("!" * 50)
    else:
        print("Environment: All required API keys loaded (Anthropic + OpenAI)")

    if missing_optional:
        print(f"Note: Optional keys not set: {missing_optional}")

    # Load jobs from disk
    load_all_jobs_from_disk()

    # Ensure cache and jobs directories exist
    for directory in ["cache", "jobs"]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

    print("SportsCast AI — Ready")
    print("=" * 50)

    yield

    # Shutdown
    print("SportsCast AI — Shutting down")


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

app = FastAPI(
    title="SportsCast AI",
    description=(
        "Production multi-agent sports analysis system. "
        "Supports NBA, F1, Soccer, Valorant, and MLB. "
        "Powered by LangGraph, Claude, and GPT-4o-mini."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# CORS — allow the React UI to call the API
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

app.include_router(health.router, tags=["Health"])
app.include_router(games.router, prefix="/games", tags=["Games"])
app.include_router(analysis.router, prefix="/analyze", tags=["Analysis"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(discovery.router, prefix="/discover", tags=["Discovery"])
app.include_router(tts.router, prefix="/tts", tags=["TTS"])
app.include_router(traces.router, prefix="/traces", tags=["Traces"])


# ─────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "SportsCast AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "sports": ["nba", "f1", "soccer", "valorant", "mlb"],
    }


# Export start time for health endpoint
def get_start_time() -> float:
    return START_TIME