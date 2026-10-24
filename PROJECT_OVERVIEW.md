# SportsCast AI — Architecture Overview

This document describes the system as it exists in the code today. Where the code was ambiguous or I could not verify a claim by reading it directly, I say so rather than guessing. File:line references point at the specific implementation.

**One-paragraph summary**: a FastAPI backend (`api/`) accepts an analysis request, hands it to a background thread running a 5-node LangGraph pipeline (`graph.py` + `agents/`), which fetches raw stats from one of 5 sport-specific external APIs (`data_sources/`), runs them through 4 sequential/parallel Claude calls to produce team analysis, player analysis, and a final broadcast narrative, and caches the result as a JSON file on disk. A React frontend (`ui-react/`) polls that job via Server-Sent Events, then renders the cached result and lets the user ask follow-up questions through a separate chat endpoint that does its own, simpler GPT-4o-mini-based intent classification. A standalone MCP server also exists alongside this and partially duplicates it.

---

## 1. File Structure

Excludes `node_modules/`, `__pycache__/`, `.git/`, `venv/`, build output, and the two runtime data directories `cache/` and `jobs/` (each holds dozens of generated JSON files — see Section 6 for what's in them instead of listing every file).

```
sportscast-ai/
├── graph.py                        LangGraph pipeline definition + run_analysis() entry point
├── mcp_server.py                   Standalone FastMCP server (port 8001), partially independent of the FastAPI app
├── requirements.txt                17 unpinned top-level deps (langgraph, fastapi, anthropic, openai, nba-api, etc.)
├── Dockerfile                      Backend image: python:3.11-slim, installs requirements, runs uvicorn with 2 workers
├── docker-compose.yml              Defines `api` + `frontend` services
├── nginx.conf.example              Documentation-only Nginx config for a bare-metal/VM deploy (not used by Docker build)
├── .dockerignore / .gitignore      Exclude venv, node_modules, caches, runtime data (cache/, jobs/), logs, local scratch scripts
├── .env / .env.example             Local secrets / documented template of required and optional env vars
├── README.md                       Project pitch, live demo link, architecture and model breakdown
│
├── .github/workflows/
│   └── ci.yml                      GitHub Actions: runs Tier-1 eval suite + builds the frontend (no deploy step)
├── .claude/settings.local.json     Claude Code local tool-permission settings (not part of the app)
│
├── agents/                         Each agent builds its API client lazily via get_client(), so importing
│   │                               an agent never requires an API key (only calling the model does)
│   ├── __init__.py                 Empty
│   ├── match_analysis_agent.py     Team/game-level analysis agent (Claude Sonnet 4.6)
│   ├── player_analysis_agent.py    Per-player breakdown agent (Claude Sonnet 4.6)
│   ├── enrichment_agent.py         Rewrites top-3 NBA players' INSIGHT field (Claude Sonnet 4.6, NBA-only)
│   ├── narrative_agent.py          Final broadcast narrative, persona-driven (Claude Opus 4.8)
│   └── chat_agent.py               Intent classification + grounded Q&A (GPT-4o-mini) — not a graph node; POST /chat calls its functions directly
│
├── data_sources/
│   ├── __init__.py                 Empty
│   ├── nba_fetcher.py              nba_api wrapper: team lookup, recent game finder, box score
│   ├── nba_recent_games.py         League-wide recent-games scan (separate from nba_fetcher's single-team lookup)
│   ├── f1_fetcher.py               Jolpica (Ergast-compatible) F1 API client + hardcoded 2026 round lookup table
│   ├── mlb_fetcher.py               Official MLB Stats API client
│   ├── soccer_fetcher.py           BSD soccer API client (requires BSD_API_KEY) — EPL only, rejects non-EPL teams explicitly
│   └── valorant_fetcher.py         VLR.gg community API client
│
├── api/
│   ├── __init__.py                 Empty
│   ├── main.py                     FastAPI app: CORS, lifespan startup/shutdown, router mounting, `/` and health wiring
│   ├── models/
│   │   ├── __init__.py             Empty
│   │   └── schemas.py              All Pydantic request/response models and the Sport/Persona/JobStatus enums
│   ├── routes/
│   │   ├── __init__.py             Empty
│   │   ├── analysis.py             POST /analyze, GET /analyze/{id}, GET /analyze/{id}/stream (SSE)
│   │   ├── chat.py                 POST /chat — calls chat_agent's classify_intent / build_smart_context / generate_chat_response directly
│   │   ├── discovery.py            GET /discover/{sport} — finds the latest match ID per sport, no pipeline run
│   │   ├── games.py                GET/DELETE cached games
│   │   ├── health.py               GET /health, GET /metrics
│   │   ├── traces.py               GET /traces/latest — LangSmith trace lookup
│   │   └── tts.py                  POST /tts — ElevenLabs voice synthesis with browser-speech fallback
│   └── services/
│       ├── __init__.py             Empty
│       └── job_manager.py          In-memory + disk-backed job store (Section 6)
│
├── utils/
│   ├── __init__.py                 Empty
│   ├── state.py                    SportsCastState TypedDict (Section 2)
│   ├── cache.py                    Disk-based JSON cache for completed analyses (Section 6)
│   ├── cost_tracker.py             Per-model $ cost table + a single global running total (Section 8, Section 11)
│   ├── retry.py                    `with_retry` decorator: 3 attempts, exponential backoff, catches bare Exception
│   ├── personas.py                 Two narrative personas: espn_formal, tactical_coach
│   └── logger.py                   stdout logging helpers (agent start/stop timing, API call logging, errors)
│
├── scripts/                        Manual dev utilities, run from the repo root as `python -m scripts.<name>`
│   ├── run_quality_audit.py        Scans all locally cached narratives for banned words/em-dashes/length
│   └── run_simulation.py           Hits a running API end-to-end and prints a human-readable report
│
├── ui-react/                        Production frontend (React + Vite)
│   ├── Dockerfile                  Multi-stage: node:20-slim build → nginx:alpine serve
│   ├── nginx.conf                  Static-file-only Nginx config baked into the Docker image (no API proxy)
│   ├── vite.config.js              Vite + React + Tailwind plugins, no dev-server proxy
│   ├── eslint.config.js            Standard ESLint flat config (not run in CI)
│   ├── index.html                  Vite HTML entry point
│   ├── package.json / package-lock.json   The project's only npm manifest (React 19, react-router-dom, framer-motion, axios, tailwind)
│   ├── public/favicon.svg, icons.svg        Static assets
│   └── src/
│       ├── main.jsx                 Entry point: BrowserRouter + HelmetProvider
│       ├── App.jsx                  Route table: / , /loading/:jobId , /analysis/:sport/:gameId
│       ├── api.js                   Axios client wrapping every backend endpoint except the SSE stream
│       ├── config.js                Static per-sport UI config (labels, colors, chat suggestions)
│       ├── index.css                Tailwind entry stylesheet
│       ├── hooks/useWindowSize.js   Responsive-layout hook
│       ├── assets/hero.png, react.svg, vite.svg   Static assets
│       └── pages/
│           ├── Home.jsx             Sport picker, cached-game list, "Discover Latest" / manual analyze
│           ├── Loading.jsx          Consumes the SSE stream directly via native EventSource (Section 10)
│           └── Analysis.jsx         Tabbed result view: narrative, match/player analysis, viz, chat, TTS
│
└── tests/
    ├── __init__.py                 Empty
    ├── test_production_eval.py     The real automated suite — 9 Tier-1 test groups + optional Tier-2 live tests (Section 7)
    ├── fixtures/                   5 committed pipeline outputs (one per sport) the Tier-1 quality suites assert against
    │                               (nba_0042500401, f1_2026_5, soccer_374, valorant_754737, mlb_824916)
    ├── test_chat_agent.py          Manual print-and-eyeball script exercising chat_agent against cached NBA + F1 games
    └── test_*.py (27 more files)   Ad-hoc exploratory/debug scripts for individual APIs and pipelines — no assertions, print-only (Section 7)
```

---

## 2. The LangGraph Pipeline

### State schema — `utils/state.py` (26 lines)

`SportsCastState` is a `TypedDict`:

| Field | Type | Populated by |
|---|---|---|
| `sport` | `str` | Caller (`run_analysis`) |
| `match_id` | `str` | Caller |
| `raw_match_data` | `Optional[dict]` | The sport-specific `*_fetch_node` |
| `match_analysis` | `Optional[str]` | `match_analysis_node` |
| `player_analysis` | `Optional[str]` | `player_analysis_node`, then overwritten by `enrichment_node` |
| `narrative` | `Optional[str]` | `narrative_node` |
| `chat_history` | `List[dict]` | Starts `[]`; no graph node writes it (chat runs outside the graph via `POST /chat`) |
| `user_query` | `Optional[str]` | Not written by any graph node; legacy field from when chat was a node |
| `chat_response` | `Optional[str]` | Not written by any graph node; legacy field from when chat was a node |
| `persona` | `Optional[str]` | Caller, default `"espn_formal"` |
| `error` | `Optional[str]` | Any node. Uses a custom reducer: `lambda x, y: y if y is not None else x` — needed because `match_analysis` and `player_analysis` write to state concurrently and LangGraph must know how to merge two simultaneous writes to the same key. |

### Shape of the graph

```
                              ┌─────────┐
                              │ router  │  (validates sport; unsupported → sets error)
                              └────┬────┘
            route_to_fetch() picks one of 5 fetch nodes by state["sport"],
            or END if router set an error (no fetch or LLM call runs)
                              ┌────┴─────────────────────────┐
                 ┌────────┬───┴────┬─────────┬───────────┐   │
             nba_fetch  f1_fetch soccer_fetch valorant_fetch mlb_fetch
                 │          │        │            │           │
                 └──────────┴────────┴────────────┴───────────┘
                     (should_continue_after_fetch: error? → END)
                              │ (unconditional)         │ (conditional, on success)
                              ▼                         ▼
                     player_analysis            match_analysis
                              │                         │
                              └────────────┬────────────┘
                                   (fan-in: both required)
                                           ▼
                                      enrichment
                                  (NBA only; others no-op)
                      (should_continue_after_analysis: error or
                       missing match_analysis? → END)
                                           ▼
                                       narrative
                                           ▼
                                          END
```

Chat is not part of the graph. It used to be registered as a `chat` node with no edges (dead code); that node was removed, and `POST /chat` calls `chat_agent`'s functions directly against a cached analysis.

### Nodes (`graph.py`, 309 lines)

- **`router_node`** (`graph.py:71-89`) — the graph's entry point. Validates `state["sport"]` against `SPORT_FETCH_ROUTES`; for an unsupported sport it returns `{"error": "Unsupported sport: '<x>'. Supported sports: ..."}` so the pipeline ends before any fetch or LLM call. Otherwise returns `{}`.
- **`route_to_fetch`** (`graph.py:40-45`) — not a node, the conditional-edge function. Returns `"end"` if the router set an error; otherwise maps `state["sport"]` → one of `nba_fetch, f1_fetch, soccer_fetch, valorant_fetch, mlb_fetch` (aliases: `football`→soccer, `valo`→valorant, `baseball`→mlb). There is no fallback to NBA: an unknown sport routes to `END`.
- **5 sport-specific fetch nodes** (imported from `data_sources/`) — each calls its external API, writes `raw_match_data` or `{"error": "..."}`.
- **`match_analysis_node`** (`agents/match_analysis_agent.py`) — reads `raw_match_data`, calls Claude Sonnet 4.6, writes `match_analysis`.
- **`player_analysis_node`** (`agents/player_analysis_agent.py`) — reads `raw_match_data` + `match_analysis`, calls Claude Sonnet 4.6, writes `player_analysis`.
- **`enrichment_node`** (`agents/enrichment_agent.py`) — reads `match_analysis` + `player_analysis`, calls Claude Sonnet 4.6 (NBA only), rewrites `player_analysis`.
- **`narrative_node`** (`agents/narrative_agent.py`) — reads `match_analysis` + `player_analysis` + `persona`, calls Claude Opus 4.8, writes `narrative`.

All four LLM agents (and `chat_agent`) create their Anthropic/OpenAI client lazily through a module-level `get_client()` that builds and caches it on first call. Importing `graph.py` therefore needs no API keys; a missing key only surfaces when a model is actually called.

### Routing and parallel execution

Each of the 5 fetch nodes gets **two** outgoing edges:
1. A conditional edge via `should_continue_after_fetch` (`graph.py:48-53`) → `match_analysis` if no error, else `END`.
2. An **unconditional** edge straight to `player_analysis`.

Because `add_edge` is unconditional regardless of the conditional branch's outcome, both `match_analysis` and `player_analysis` end up scheduled in the same LangGraph superstep after a successful fetch — this is the pipeline's fan-out, achieved just by having two edges into the same step rather than any explicit parallel API (no `Send`, no thread pool config in `graph.py` itself). LangGraph's Pregel-style executor runs same-superstep nodes concurrently.

One caveat: if the fetch fails, the conditional edge sends the error to `END`, but the unconditional edge to `player_analysis` *still fires* — `player_analysis_node` only avoids doing real work because of its own internal guard (`if state.get("error"): return {}`), not because the graph topology prevented it from running.

Fan-in: both `match_analysis` and `player_analysis` have an edge to `enrichment` (`graph.py:204-205`), so `enrichment` waits for both to complete before running.

`enrichment` → conditional edge via `should_continue_after_analysis` (`graph.py:56-64`) → `narrative` or `END` (ends if there's an error, or if `match_analysis` is missing). `narrative` → `END` unconditionally.

### Error handling and entry point

No graph-level retry policy is configured on any node. The only graph-level safety net is a hard `recursion_limit: 25` passed to `.invoke()` (`graph.py:282`). Retries exist only inside individual agent functions (`@with_retry`, see Section 3). `run_analysis(sport, match_id, persona, force_refresh)` (`_run_analysis_impl`, `graph.py:230-290`) is the public entry point: checks cache first, validates inputs, builds `initial_state`, invokes the compiled graph, and saves to cache on success. It's wrapped in a LangSmith `@traceable` decorator if `LANGCHAIN_API_KEY` is set, otherwise called raw. `run_nba_analysis(...)` is a thin backward-compatible wrapper around `run_analysis("nba", ...)`.

---

## 3. The 5 Agents

| Agent | Node | Model | Max tokens | Retry |
|---|---|---|---|---|
| `match_analysis_agent.py` | `match_analysis` | `claude-sonnet-4-6` | 2000 | 3 attempts, 1s base delay |
| `player_analysis_agent.py` | `player_analysis` | `claude-sonnet-4-6` | 3000 | 3 attempts, 1s base delay |
| `enrichment_agent.py` | `enrichment` | `claude-sonnet-4-6` | 800 | 3 attempts, 1s base delay |
| `narrative_agent.py` | `narrative` | `claude-opus-4-8` | 1200 | 3 attempts, 1s base delay |
| `chat_agent.py` | — (outside the graph; called by `POST /chat`) | `gpt-4o-mini` | 600 | 3 attempts, 1s base delay |

**match_analysis_agent.py** — single-shot, user-only prompt (no system message) instructing Claude to act as "an expert {sport} analyst" and produce exactly 4 fixed sections: GAME OVERVIEW, KEY TURNING POINTS, TEAM PERFORMANCE, DECISIVE FACTORS. Plain-text output, no JSON mode. Style rules ban em-dashes and a list of words ("notably," "crucially," "delve," etc.). Reads `raw_match_data` + `sport`, writes `{"match_analysis": ...}`.

**player_analysis_agent.py** — also single-shot user-only, but the task instructions branch by sport: NBA gets a strict `PLAYER:/TEAM:/RATING:/STATS:/INSIGHT:/IMPROVEMENT:` field format separated by `---`; MLB/F1/Soccer/Valorant each get bespoke instructions (soccer explicitly says "do not invent statistics" since it has no individual stats; Valorant explicitly tells the model to draw on its own training knowledge of teams/players since the fetched data is sparse). Reads `raw_match_data` + first 1000 chars of `match_analysis`, writes `{"player_analysis": ...}`.

**enrichment_agent.py** — two stages: (1) pure-Python regex extraction of the top 3 rated players from `player_analysis` (no LLM call), (2) one LLM call that rewrites only their `INSIGHT` field using match context, then splices the result back into the original text via string replace. Explicitly skipped for `f1, soccer, football, valorant, mlb` — it only ever runs for NBA. On any failure it returns `{}` and does **not** set `state["error"]` — enrichment failures are silent; the pipeline just proceeds with the un-enriched player analysis.

**narrative_agent.py** — the only Opus call, and the last step before `END`. Prompt assembles: persona instructions from `utils/personas.py`, a storylines block (sport-aware truncation of match/player analysis — MLB/F1 get 1500 chars, NBA/Valorant get 800), and a sport-specific 4-paragraph structure template (separate hardcoded templates for F1, Valorant, MLB, and a generic one for the rest). Requires "at least two specific statistics" per paragraph. Reads `match_analysis`/`player_analysis` without `.get()` defaults (would `KeyError` if missing, caught by the outer `try/except`), plus `persona` and playoff context if present.

**chat_agent.py** — the most complex file (475 lines), and the only one not using Claude. It exposes plain functions rather than a graph node; `POST /chat` and `mcp_server.py` call them directly. Intent classification is pure Python keyword matching over 7 categories (`classify_intent`, `chat_agent.py:52-127`), not an LLM call. Player/entity matching is regex + substring. Context retrieval varies by intent (factual pulls a specific player section; predictive pulls the full match analysis plus 2500 chars of player analysis; etc.). History beyond 8 turns gets summarized into a synthetic exchange. The file still defines a Mem0 long-term-memory helper (`_get_memory()`, gated on `MEM0_ENABLED=true`), but nothing calls it: its only caller was the deleted `chat_node()`, and `POST /chat` never used Mem0, so setting `MEM0_ENABLED` currently has no effect. The final generation call uses a system+user split (system prompt carries grounding rules and per-intent format instructions), `temperature=0.7`.

**Runtime per agent**: no benchmark data exists anywhere in the repo. `utils/logger.py`'s `log_agent_start`/`log_agent_complete` print per-agent wall-clock duration to stdout at runtime, but nothing persists or aggregates those numbers — I could not find logged timing data, a benchmarks file, or CI timing output to cite. The only thing I can say with confidence from the code: `narrative` is the last node in the dependency chain (after both `match_analysis` and `player_analysis` complete) and uses the larger/slower Opus model, so it is very likely the single biggest latency contributor, but I cannot give you a number.

---

## 4. Data Sources

| Fetcher | External API | Auth | Rate limiting | On failure |
|---|---|---|---|---|
| `nba_fetcher.py` | `nba_api` package → stats.nba.com (unauthenticated public endpoints) | None | `time.sleep(1)` before each call, no documented RPS limit | Raises `ValueError` for not-found cases; top-level node catches everything and returns `{"error": ...}` |
| `nba_recent_games.py` | Same `nba_api` package, `LeagueGameFinder` | None | `time.sleep(1)` | Returns empty-result dict (not an exception) when no games found |
| `f1_fetcher.py` | Jolpica F1 API (`http://api.jolpi.ca/ergast/f1`, note: plain HTTP) | None | `time.sleep(0.5)`, commented "Respectful rate limiting" | Each sub-fetch soft-fails to `{}` via `safe_fetch`; the whole function raises only if the primary results fetch is empty |
| `mlb_fetcher.py` | Official MLB Stats API (`statsapi.mlb.com/api/v1`) | None | `time.sleep(0.3)` | Same soft-fail-to-`{}` pattern; raises `ValueError` if box score + linescore both empty |
| `soccer_fetcher.py` | BSD soccer API at `sports.bzzoiro.com/api/v2` (README and code agree on this host) | **Required for soccer** — `Authorization: Token <BSD_API_KEY>` header (the app itself starts without it) | `time.sleep(0.3)` | Soft-fail to `{}`; explicitly rejects ~25 known non-EPL team/country names up front with a clear "only EPL teams supported" error instead of silently fetching wrong data; has a live-data fallback (World Cup → Premier League if World Cup data is stale, cutoff hardcoded at `< "2025-01-01"`) |
| `valorant_fetcher.py` | VLR.gg community API mirror (`vlr.orlandomm.net/api/v1`) | None (confirmed in `.env.example`'s own comment — `RIOT_API_KEY` is test-only, unused in production fetches) | `time.sleep(0.3)` | Soft-fail to `{}`; falls back to "most recent match" if a tournament-specific lookup fails before finally raising |

Shared infrastructure: every fetcher's top-level function is wrapped in `@with_retry(max_attempts=3, base_delay=2)` from `utils/retry.py` — exponential backoff (2s, then 4s) catching any bare `Exception`. There is **no shared HTTP client, session, or default timeout** — each file implements its own near-identical `safe_fetch()` helper independently, with inconsistent timeouts (NBA via `nba_api`: 60s; F1/MLB/Soccer: 30s; Valorant: 15s). `f1_fetcher.py` additionally bakes in a hardcoded `F1_2026_ROUND_LOOKUP` table (~50 entries) snapshotted from the API on 2026-06-10 rather than resolving round numbers live — it will need manual updates for future seasons.

---

## 5. API Surface

All routers mount in `api/main.py:101-107`. Base path shown includes the router's prefix.

| Method | Path | File | Sync/Async | Notes |
|---|---|---|---|---|
| GET | `/` | `api/main.py:114` | sync | Static metadata dict |
| GET | `/health` | `health.py:38` | sync | Checks NBA/F1/MLB/Soccer/VLR APIs + cache count; `degraded` if ≥3 of 5 external checks fail |
| GET | `/metrics` | `health.py:93` | sync | Aggregates over the in-memory job store only |
| GET | `/games/` | `games.py:8` | sync | Optional `?sport=` query param |
| GET | `/games/{sport}/{game_id}` | `games.py:24` | sync | 404 if not cached |
| DELETE | `/games/{sport}/{game_id}` | `games.py:50` | sync | Deletes the cache file |
| POST | `/analyze/` | `analysis.py:69` | async | Body: `AnalyzeRequest {sport, match_id="latest", persona="espn_formal", force_refresh=False}`. Returns `job_id` immediately; actual pipeline runs on a `ThreadPoolExecutor(max_workers=4)` |
| GET | `/analyze/{job_id}` | `analysis.py:101` | sync | Returns job status; if complete, reloads the full result from cache |
| GET | `/analyze/{job_id}/stream` | `analysis.py:148` | async | **The only streaming endpoint.** SSE via `StreamingResponse`; see Section 6 and 11 for how it actually works and its fragility |
| POST | `/chat/` | `chat.py:9` | sync | Body: `ChatRequest {sport, game_id, query, chat_history=[]}`. Requires cached analysis; 404 if missing |
| GET | `/discover/{sport}` | `discovery.py:139` | sync | Finds the latest match ID for a sport without running the pipeline; 400 on unknown sport, 503 if the discoverer call fails |
| POST | `/tts/` | `tts.py:39` | async (but does blocking `requests.post` inside) | Body: local `TTSRequest {text, voice_id}`. Falls back to `{"fallback": True}` if `ELEVENLABS_API_KEY` unset; buffers and base64-encodes the audio rather than streaming it |
| GET | `/traces/latest` | `traces.py:14` | async (blocking LangSmith SDK call inside) | Returns `None` trace URL gracefully if `LANGCHAIN_API_KEY` unset or on any error |

Response models live in `api/models/schemas.py` (`Sport`, `Persona`, `JobStatus` enums; `AnalyzeRequest/Response`, `ChatRequest/Response`, `JobStatusResponse`, `CachedGame`, `GamesResponse`, `APIStatus`, `HealthResponse`, `MetricsResponse`). CORS is wide open: `allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]` (`api/main.py:88-94`) — no auth of any kind on any route.

---

## 6. State and Storage

Everything is **disk-based JSON**, not Redis, not a database.

**Cache (`utils/cache.py`)** — one file per game at `cache/{sport}_{game_id}.json` (slashes in the ID replaced with underscores). `save_to_cache` persists only 7 fields of state (`sport, match_id, match_analysis, player_analysis, narrative, persona, raw_match_data`) plus a `cached_at` timestamp and a `version: "v1"` tag. The *only* invalidation logic is the version tag — there is no TTL, no age check. A cache entry from a year ago with a matching version is returned as a hit. Deletion is manual, via `DELETE /games/{sport}/{game_id}` → `os.remove()`.

**Jobs (`api/services/job_manager.py`)** — a dual store: a module-level in-memory dict `_jobs = {}` as the primary read path, with every create/update also synchronously written to `jobs/{job_id}.json`. On FastAPI startup, `load_all_jobs_from_disk()` rehydrates `_jobs` from disk and marks any job that was `RUNNING`/`QUEUED` at shutdown as `FAILED` ("Server restarted during analysis"). `get_job()` checks memory first, only falling back to disk on a cold miss.

**This breaks with more than one worker process or replica, and it is already running that way in production.** `Dockerfile:19` starts `uvicorn --workers 2`. Each worker is a separate OS process with its own independent copy of `_jobs` — there is no shared memory, IPC, or lock between them. A `POST /analyze/` handled by worker A creates the job and runs it on worker A's local `ThreadPoolExecutor`. If a later `GET /analyze/{job_id}` or the SSE stream request is routed to worker B, worker B's in-memory `_jobs` won't have it — it falls back to reading `jobs/{job_id}.json` from disk, which only works because both workers currently share the same container's local filesystem. If this were ever split across multiple containers/replicas without a shared volume, that fallback would also fail and clients would get `404 Job not found` nondeterministically depending on load-balancer routing. Even within the same container, concurrent `_save_job()` writes from different threads are not file-locked.

**Cache has the same shared-filesystem dependency** — it would work fine across the 2 uvicorn workers in the current single-container setup (same local disk), but would silently degrade to per-replica cache misses (and redundant, costly pipeline re-runs) if ever deployed across multiple containers without a shared volume.

---

## 7. The Evaluation Suite

The "9/9 passing" number referenced in the README and run in CI refers specifically to the 9 Tier-1 groups inside **`tests/test_production_eval.py`** (run via `python -m tests.test_production_eval`). Tier 1 makes no LLM calls and needs no API keys, so it costs $0.00 and runs in CI with no secrets configured:

1. **Environment** — checks `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `BSD_API_KEY` are present and plausible length; `RIOT_API_KEY` optional; cache dir exists; all core modules import cleanly. When `CI=true` (set by GitHub Actions), missing keys are reported as **skipped** rather than failed, since the fixture-based suites don't need them; run locally, a missing key is still a failure.
2. **Cache System** — write/read round-trip, read speed (10 reads < 1s), `force_refresh` bypasses cache, missing key returns `None`, cache reads cost `$0.00`, invalidation removes the file.
3. **Intent Classifier** — the 20 hand-written (text, expected-label) cases covering all 7 intent types, asserting `classify_intent()` returns the expected label (pure Python, no model call).
4. **NBA Quality** — against the committed fixture `tests/fixtures/nba_0042500401.json`: required fields present, narrative ≥300 words, no em-dashes, no banned words, player analysis has the `PLAYER:/RATING:/STATS:/INSIGHT:` structure, narrative contains ≥10 numbers, both team names mentioned, enrichment produced ≥3 player sections.
5. **F1 Quality** — against `f1_2026_5.json`: required fields, length, no em-dashes, F1 terminology present, ≥3 named drivers, championship-context keywords, player analysis has driver-relevant content.
6. **Soccer Quality** — against `soccer_374.json` (Brighton vs Manchester United): required fields, length ≥200 words, team names present, soccer terminology, incident players referenced, and explicitly asserts the narrative does **not** hallucinate individual stats soccer data doesn't have (checks for fabricated "% pass" / "xG of" phrasing).
7. **Valorant Quality** — against `valorant_754737.json` (LOUD vs Team Vitality): terminology, player IGNs present, tournament context, player analysis has team content.
8. **MLB Quality** — against `mlb_824916.json` (Pittsburgh vs Atlanta): pitcher names, inning references, MLB terminology, pitching+batting content in player analysis, named top performers.
9. **Error Handling** — invalid NBA team name, unsupported sport (asserts an error is returned rather than a silent fallback to NBA), empty match_id, and that a failed analysis is not written to cache. None of these reach an external API: the invalid team is rejected by `nba_api`'s bundled static team list before any stats.nba.com call, and the unsupported sport is rejected by `router_node`. The two invalid-team cases do spend ~6s each in `with_retry` backoff (see Section 11).

**Fixtures.** Each quality suite loads its game from `tests/fixtures/` via `load_fixture()`, not from the gitignored `cache/` directory. A missing fixture is a hard **FAIL** ("Missing fixture: tests/fixtures/<name>"), not a skip. Previously these suites read from `cache/`, which CI never populated, so 5 of the 9 suites hit a "cache not found → return True" early exit and reported PASS with zero assertions run.

**Runner behavior.** The main runner wraps each suite call, so an exception raised outside an individual test (e.g. a failing import at the top of a suite) marks *that suite* FAIL with the error text (`FAIL (crashed: <Type>: <msg>)` in the final summary) while the remaining suites still run and the summary still prints. The process exits with code **1 if any suite failed, 0 otherwise**. Before this change the runner never called `sys.exit`, so it exited 0 even with failing suites — CI only ever went red on an uncaught crash.

An optional **Tier 2** (`--live` flag, not run in CI) actually calls live APIs and the live pipeline for all 5 sports plus an API-connectivity check and a total-cost budget assertion (expects total session cost under $0.60 for ~5 live analyses).

**What this suite does not cover at all:** the FastAPI layer (no test imports or calls any `api/` module — no test ever hits `/analyze`, `/chat`, `/health`, `/games`, or the SSE stream endpoint), the job manager (`api/services/job_manager.py` has zero tests), the multi-worker/disk-persistence behavior described in Section 6, the frontend (no JS test files exist anywhere under `ui-react/`), `mcp_server.py`, TTS, LangSmith tracing, and Mem0 integration. Chat correctness (beyond intent classification) also has no automated assertions — `tests/test_chat_agent.py` runs real queries against a cached game and prints the model's answers for a human to read, with no pass/fail check.

The other 27 `test_*.py` files in `tests/` (e.g. `test_balldontlie.py`, `test_bsd_*.py`, `test_vlr_api.py`, `test_worldcup*.py`, `test_mlb_api.py`, per-sport `test_*_fetcher.py`/`test_*_pipeline.py`) are exploratory scratch scripts: they call a function or hit an API and `print()` the result for a human to eyeball. None of them use `assert`, pytest fixtures, or any pass/fail mechanism — they do not run in CI and provide no regression protection. If one of these scripts still "works," it's only because nobody has run it recently to notice otherwise.

---

## 8. Models, Cost, Latency

| Model | Used by | Price (per 1K tokens, from `utils/cost_tracker.py:2-6`) |
|---|---|---|
| `claude-sonnet-4-6` | match_analysis, player_analysis, enrichment | $0.003 in / $0.015 out |
| `claude-opus-4-8` | narrative | $0.015 in / $0.075 out |
| `gpt-4o-mini` | chat | $0.00015 in / $0.0006 out |

Using each agent's `max_tokens` ceiling as an upper bound (actual output is usually shorter, since the model stops at a natural completion point, not at the ceiling):

- match_analysis: 2000 out tokens → ≤$0.03 output cost alone
- player_analysis: 3000 out tokens → ≤$0.045
- enrichment (NBA only): 800 out tokens → ≤$0.012
- narrative: 1200 out tokens → ≤$0.09 (Opus output is 5x the per-token price of Sonnet output)

Summing these ceilings (plus input tokens, which I can't bound precisely without knowing real prompt lengths) puts a full NBA analysis's theoretical worst case somewhere around $0.20–$0.25. The README claims an actual observed cost of **~$0.08 per fresh analysis**, which is consistent with real completions landing well under their `max_tokens` ceilings — I can't verify that $0.08 figure independently since no real token-usage logs are persisted anywhere in the repo; it's the project's own documented number, not something I derived from code. Each chat turn (GPT-4o-mini, 600 max output tokens) costs a small fraction of a cent regardless.

**Important caveat on cost tracking itself:** `utils/cost_tracker.py` holds `_session_cost` as a single module-level global, reset and read around each job in `api/routes/analysis.py:25,61` and `api/routes/chat.py:27,70`. See Section 11 — this is not safe for concurrent requests.

**Latency**: no timing data is persisted anywhere (see Section 3). The pipeline's critical path is fetch → (match_analysis ∥ player_analysis) → enrichment (NBA only) → narrative, i.e. 3-4 sequential LLM calls minimum, each subject to up to 3 retry attempts with up to 3s of sleep between them on failure. `nginx.conf.example`'s own comment (lines 1-10) states the pipeline takes "60-90s per analysis" in practice and sets `proxy_read_timeout 120s` accordingly — that's the one concrete latency figure anywhere in the repo, and it comes from a config comment, not a benchmark.

---

## 9. Deployment

**Backend `Dockerfile`**: `python:3.11-slim`, installs `build-essential`/`curl`, `pip install -r requirements.txt`, copies the repo, creates `cache/` and `jobs/` dirs, exposes 8000, runs `uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2`. `requirements.txt` no longer includes `streamlit`: the legacy Streamlit UI (`ui/`, `.streamlit/`) was deleted, so the only frontend is `ui-react/`.

**Frontend `ui-react/Dockerfile`**: multi-stage — `node:20-slim` builds the Vite app with build-arg `VITE_API_URL` (default `http://localhost:8000`) baked in at build time, then an `nginx:alpine` stage serves the static `dist/` output with `ui-react/nginx.conf` (SPA fallback + gzip only, no backend proxy).

**`docker-compose.yml`**: two services, `api` (port 8000:8000, `.env` file mount, volumes `./cache` and `./jobs` mounted into the container, healthcheck via `curl /health` every 30s) and `frontend` (port 80:80, depends on `api`'s healthcheck passing, `VITE_API_URL` build arg). There is **no internal Docker network wiring between the two** — the frontend container doesn't reverse-proxy to `api`; the browser calls the backend directly at whatever host/port `VITE_API_URL` resolves to. `nginx.conf.example` documents a different, more complete topology (path-based `/api/` proxying with explicit SSE-safe settings — `proxy_buffering off`, 120s timeouts) intended for a single-domain bare-metal/VM deploy, but that file is not wired into the Docker build at all.

**GitHub Actions (`.github/workflows/ci.yml`)**: triggers on push/PR to `master`/`main`. Two jobs: `backend` (checkout, Python 3.11, `pip install -r requirements.txt`, run `python -m tests.test_production_eval`) and `frontend` (checkout, Node 20, `npm ci && npm run build` inside `ui-react/`). The workflow references 4 API key secrets, but **the repo has no Actions secrets configured**, so they arrive as empty strings. That's by design now: Tier 1 needs no keys (lazy agent clients mean imports don't require them, and the Environment suite skips key checks under `CI=true`). The job's pass/fail is driven by the runner's exit code, which is non-zero if any suite fails (Section 7). The backend job takes about a minute, ~45s of which is `pip install`. **There is no deploy step** — no Docker build/push, no artifact upload, nothing that touches the EC2 instance mentioned in the README. Whatever is running at the README's live demo IP was deployed manually, not by this pipeline.

**Environment variables** (from `.env.example`):

| Var | Required? | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes, to run analyses (not needed for Tier-1 tests) | match/player/enrichment/narrative agents |
| `OPENAI_API_KEY` | Yes, to run chat (not needed for Tier-1 tests) | chat agent |
| `BSD_API_KEY` | Optional — the app starts without it (`.env.example` and `api/main.py` agree), but every soccer request fails until it's set | soccer fetcher |
| `ELEVENLABS_API_KEY` | Optional | TTS, falls back to browser speech synthesis if unset |
| `RIOT_API_KEY` | Optional, tests only | not read anywhere in `api/` or `data_sources/` |
| `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` | Optional | LangSmith tracing |
| `MEM0_ENABLED` | Optional | currently no effect — `chat_agent._get_memory()` reads it, but nothing calls that helper |
| `RAPIDAPI_KEY`, `BALLDONTLIE_API_KEY` | Optional, tests only | not read in app code |
| `VITE_API_URL` | Optional | frontend build arg, defaults to `http://localhost:8000` |

---

## 10. Frontend

React + Vite, 3 routes defined in `ui-react/src/App.jsx:14-16`:

- **`/` → `Home.jsx`** — sport picker, lists cached games per sport (fetched in parallel for all 5 sports), a "Discover Latest" action or manual match-ID entry, a health-check poll every 15s that shows an "API down" banner after 2 consecutive failures.
- **`/loading/:jobId` → `Loading.jsx`** — a 5-step animated progress display driven by the SSE stream, navigates to `/analysis/...` on completion.
- **`/analysis/:sport/:gameId` → `Analysis.jsx`** (1539 lines, by far the largest frontend file) — tabbed view (Narrative / Match Analysis / Player Analysis / Visualization / Chat), TTS playback with browser-speech fallback, chat Q&A, copy/share/print, and per-sport SVG visualizations.

**`ui-react/src/api.js`** wraps every backend endpoint except the SSE stream in an `axios` instance (`baseURL` from `VITE_API_URL`, 15s timeout).

**SSE consumption** happens directly inside `Loading.jsx` (`ui-react/src/pages/Loading.jsx:99-137`) via the browser's native `EventSource`, not through `api.js` and not polling — the code comment there literally says "SSE connection — replaces polling":

```js
const sse = new EventSource(`${API_BASE_URL}/analyze/${jobId}/stream`)
sse.onmessage = (e) => {
  try {
    const data = JSON.parse(e.data)
    if (data.type === 'progress') { /* append to progress list */ }
    else if (data.type === 'complete') { sse.close(); /* fetch full job, navigate */ }
    else if (data.type === 'failed') { sse.close(); /* show error */ }
  } catch {}
}
```

Note the bare `catch {}` — if the backend ever sends a malformed JSON frame (see Section 11's note on unescaped SSE strings), this silently drops the event instead of surfacing an error to the user.

---

## 11. Known Issues and Rough Edges

Being direct, as asked:

1. **Job store breaks under the exact deployment config shipped in this repo.** `Dockerfile:19` runs `uvicorn --workers 2`, but `api/services/job_manager.py`'s `_jobs` dict is a plain in-process global with no shared memory, IPC, or lock across workers. A job created by worker A may 404 on `GET /analyze/{id}` or the SSE stream if the request lands on worker B, with disk (`jobs/*.json`) as the only fallback — one that only happens to work right now because both workers share the same container's local disk. This is a live, exploitable-by-normal-use bug, not a hypothetical one.

2. **Cost tracking has a concurrency race.** `utils/cost_tracker.py`'s `_session_cost` is a single global, and both `_run_pipeline` (`api/routes/analysis.py:25,61`) and `chat()` (`api/routes/chat.py:27,70`) call `reset_session_cost()` at the start and `get_session_cost()` at the end to compute "this request's cost." The analysis route explicitly runs pipeline jobs concurrently on a 4-worker thread pool. Two analyses (or an analysis and a chat call) running at the same time in the same process will stomp on each other's counter — one job's `reset_session_cost()` can zero out another in-flight job's accumulating total, and the reported `cost` field for either job becomes meaningless. This isn't a theoretical edge case; it's the designed concurrency model (`max_workers=4`) combined with a non-isolated global.

3. **The SSE endpoint builds JSON by hand-interpolating strings, unescaped.** `api/routes/analysis.py:175,180,185` does things like `f"data: {{\"type\": \"progress\", \"message\": \"{message}\"}}\n\n"`. If a progress message or error string ever contains a `"` or a newline, the frame is invalid JSON on the wire. The frontend's `JSON.parse` call is wrapped in a bare `try {} catch {}` (`Loading.jsx:~120`), so this doesn't crash anything — it just silently drops the update, which is arguably worse, since the failure is invisible.

4. **Enrichment fails silently.** `enrichment_agent.py` never sets `state["error"]` on failure — any exception just returns `{}` and the pipeline proceeds with un-enriched player analysis. That might be an intentional "nice-to-have, not critical" design choice, but there's no log line distinguishing "enrichment skipped because non-NBA sport" from "enrichment attempted and silently failed," which makes it hard to debug from the outside.

5. **`with_retry` catches `Exception` broadly, including non-retryable errors like `ValueError`.** A bad API key, a malformed request, a 4xx from an external API, or a deterministic "not found" all get the same 3-attempts-with-backoff treatment as a transient network blip. Concrete case: `nba_fetcher.find_team_id()` raises `ValueError("Team '...' not found")` for an unknown team, and because it's called inside `@with_retry(max_attempts=3, base_delay=2)`-wrapped `find_recent_game_id`, the user waits 2s + 4s = **6s** before getting an error that was certain on the first attempt (agents use `base_delay=1`, so 1s + 2s there). This also costs ~12s per CI run across the two invalid-team Error Handling tests. Fix: re-raise `ValueError` (or a dedicated non-retryable exception type) immediately.

6. **Cache has no expiry.** `utils/cache.py`'s only invalidation check is a hardcoded `version` string. A cached narrative from a year ago, if the schema version hasn't changed, is served as a cache hit with no age check at all. Fine for a portfolio demo with static past games; would be a real bug for a live/in-progress game use case.

7. **No authentication anywhere.** Every API route is open, CORS is `allow_origins=["*"]` with credentials allowed. Reasonable for a portfolio demo behind a single known IP; worth being explicit that this is not production-access-controlled if it's ever pointed at by anything real.

8. **Hardcoded, time-bound data.** `f1_fetcher.py`'s `F1_2026_ROUND_LOOKUP` table and `soccer_fetcher.py`'s World-Cup-staleness cutoff (`< "2025-01-01"`) are both snapshots that will need manual code changes as time moves forward — they're not self-updating.

### Resolved since this document was first written

- **Dead `chat` graph node** — removed from `graph.py`, and the orphaned `chat_node()` function deleted from `chat_agent.py`. Chat runs only through `POST /chat`, which calls `chat_agent`'s functions directly.
- **README model claims** — corrected: only `narrative_agent` uses Opus 4.8; match/player/enrichment use Sonnet 4.6; chat uses GPT-4o-mini.
- **Soccer vendor name** — the README now names `sports.bzzoiro.com`, matching the code.
- **`BSD_API_KEY` required-vs-optional contradiction** — `.env.example` now lists it as optional, matching `api/main.py`'s startup check.
- **Eval suite silently passing** — 5 of 9 suites were reporting PASS with zero assertions because they read from the gitignored `cache/`. They now load committed fixtures from `tests/fixtures/` and fail hard if one is missing. Related CI fixes: unsupported sports are rejected at the router (no silent NBA fallback), agent clients are lazy so Tier 1 runs without keys, a crashing suite no longer aborts the run, and the runner's exit code now reflects failures (Section 7).
- **Repo hygiene** — removed the empty `app.py`, the stray root `package.json`/`package-lock.json` and tracked root `node_modules/`, the legacy Streamlit UI (`ui/`, `.streamlit/`), scratch scripts, and leftover logs; moved the two useful scripts to `scripts/`; rewrote `.gitignore` in UTF-8 (a UTF-16 block fused onto `jobs/` had been silently disabling several rules).

---

## 12. Things I Could Not Determine

- **Actual end-to-end or per-agent latency.** No benchmark file, timing log, or persisted metric exists in the repo. `utils/logger.py` prints per-agent duration to stdout at runtime, but nothing captures or aggregates it. The only concrete number anywhere is `nginx.conf.example`'s comment claiming "60-90s per analysis," and I can't verify that against real measurements from the code alone.
- **Real per-run token counts, and therefore the real $ cost of a typical analysis.** I computed a theoretical ceiling from each agent's `max_tokens` and the price table in `utils/cost_tracker.py`, but actual output length depends on what the model produces at runtime, which isn't logged anywhere I could find.
- **Whether the README's live demo at the stated EC2 IP reflects the current state of this repo**, or an older deployed version — there's no deploy step in CI, so whatever is running there was pushed manually, and I have no way to confirm from the code when or what was last deployed.
