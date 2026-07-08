<div align="center">

<img src="https://img.shields.io/badge/LIVE%20ON%20AWS-EC2-FF6B35?style=for-the-badge&logo=amazonaws&logoColor=white" alt="Live on AWS"/>

# SportsCast AI

**Five specialized AI agents that turn raw sports data into broadcast-quality analysis.**

*Not a data lookup tool. Not a chatbot wrapper. A multi-agent reasoning system.*

<br/>

[![Live Demo](https://img.shields.io/badge/%E2%9A%A1%20Live%20Demo-http%3A%2F%2F3.227.255.166-FF6B35?style=flat-square)](http://3.227.255.166)
[![GitHub](https://img.shields.io/badge/GitHub-Sportscast--ai-181717?style=flat-square&logo=github)](https://github.com/Rohith2320/Sportscast-ai)
[![Eval](https://img.shields.io/badge/Eval-9%2F9%20Passing-22C55E?style=flat-square)]()
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-7C3AED?style=flat-square)]()
[![AWS EC2](https://img.shields.io/badge/AWS-EC2%20%2B%20Docker-FF9900?style=flat-square&logo=amazonaws&logoColor=white)]()

<br/>

> Pick a sport. Click **Discover Latest**. In 90 seconds you get a full editorial narrative, player breakdowns, match analysis, and AI voice commentary. Powered by five agents running in parallel on a LangGraph pipeline.

</div>

---

## What Is This

SportsCast AI fetches live data from five sports (NBA, F1, EPL Soccer, Valorant, MLB), runs it through a LangGraph pipeline with five specialized Claude Opus 4 agents, and produces broadcast-quality sports narratives with voice commentary.

The system covers NBA Finals analysis, Formula 1 race breakdowns, Premier League match reports, Valorant Champions Tour coverage, and MLB game analysis using free live APIs with zero paywalls.

Try it: [http://3.227.255.166](http://3.227.255.166)

---

## Why I Built This

ESPN and StatMuse are data retrieval systems. You ask a question, they look up a stat. That is data retrieval, not analysis.

I wanted to build a system that actually *reasons* about sports. A system that could look at a box score and explain why a team won, what the turning point was, and which player made the decisive difference. Not because it was told the answer, but because five specialized agents worked through the data independently and synthesized an original conclusion.

The deeper goal was practical. I needed a portfolio project that demonstrated production AI engineering: not a Jupyter notebook, not a chatbot wrapper, but a real system with agents, orchestration, observability, cost management, streaming, and AWS deployment.

---

## How It Differs From Existing Products

| | ESPN / StatMuse | The Athletic | SportsCast AI |
|---|---|---|---|
| **Mechanism** | Data lookup | Human journalists | 5-agent AI pipeline |
| **Output** | Stats and scores | Editorial articles | AI-generated narratives |
| **Latency** | Instant (pre-written) | Hours (human written) | 90s fresh / 0s cached |
| **Voice commentary** | No | No | Yes (ElevenLabs) |
| **Agent-to-agent API** | No | No | Yes (FastMCP) |
| **Observability** | No | No | Yes (LangSmith per-agent traces) |
| **Cost per analysis** | N/A | N/A | ~$0.08 fresh / $0.00 cached |

---

## Pipeline Architecture

```
RAW SPORTS DATA
NBA Stats API · Jolpica F1 · BSD Soccer · VLR Esports · MLB Stats API
         |
         v
     ROUTER NODE  (pure Python, zero LLM cost)
         |
    _____|_____
   |           |
   v           v
MATCH       PLAYER           <- parallel execution
ANALYSIS    ANALYSIS
(Opus 4)    (Opus 4)
   |           |
   |___________|
         |
         v
    ENRICHMENT               <- NBA only (skip if no structured data)
    (Opus 4)
         |
         v
    NARRATIVE                <- broadcast-quality 400-600 word output
    (Opus 4)
         |
         v
    JSON CACHE               <- $0.00 on all repeat requests
         |
         v
  FASTAPI BACKEND
  POST /analyze  GET /stream (SSE)  POST /chat  GET /discover  POST /tts
         |
         v
   REACT FRONTEND
   Home · Loading (SSE progress) · Analysis (Narrative/Chat/Viz/Voice)
         |
         v
  AWS EC2 + DOCKER
  2 containers · Nginx · docker-compose

Observability: LangSmith (per-agent traces, latency, cost attribution)
Memory:        Mem0 (persistent chat context across sessions)
MCP Server:    FastMCP on port 8001 (AI-callable tool integration)
```

---

## The Five Agents

**Router Node** | Pure Python
Reads `state["sport"]` and routes to the correct fetcher. Zero LLM cost. This was the first design decision: knowing when NOT to use AI.

**Match Analysis Agent** | `claude-opus-4-8`
4-section structured analysis: game overview, key turning points, team performance, decisive factors. Runs in parallel with Player Analysis.

**Player Analysis Agent** | `claude-opus-4-8`
Sport-aware breakdowns. NBA uses structured PLAYER/RATING/STATS/INSIGHT format with 16 players per game. F1 analyzes driver strategy and race pace. MLB is pitcher-first. Each sport gets a different prompt because the relevant information is fundamentally different.

**Enrichment Agent** | `claude-opus-4-8` (NBA only)
Takes the top 3 performers from Player Analysis and enriches them with match-level context. Deliberately skipped for other sports. Only NBA has the structured per-player data to make enrichment meaningful. Knowing when to skip a pipeline stage matters as much as knowing when to run it.

**Narrative Agent** | `claude-opus-4-8`
The output layer. 400-600 words. Explicitly instructed to avoid AI writing patterns: no em dashes, no "notably" or "crucially," no consecutive sentences starting with "The." The output should read like a journalist wrote it.

**Chat Agent** | `gpt-4o-mini` + pure Python intent classifier
Not part of the main pipeline. Uses pattern-matching for intent classification (7 categories, zero LLM cost, microsecond latency), then GPT-4o-mini for response generation. GPT-4o-mini costs 20x less than Claude for grounded Q&A. Knowing which model fits which task is part of the engineering.

---

## Key Engineering Decisions

**Pure Python intent classifier, not an LLM**
The chat agent classifies questions using regex pattern matching. Zero LLM cost, microsecond latency, 100% accuracy on 20 test cases. A junior engineer reaches for GPT-4. An experienced one recognizes when pattern matching is sufficient.

**GPT-4o-mini for chat, Claude Opus for narrative**
Not every task needs the best model. Chat responses are grounded (the answer is in the provided context) and conversational. GPT-4o-mini handles this at $0.0003 per response. Narrative generation requires creative reasoning and journalist voice. That is where Opus earns its $0.012 per call.

**JSON file cache, not a database**
Flat JSON files on disk. Every completed analysis is stored and served instantly on repeat visits. Deliberately avoided Redis or PostgreSQL: a single t3.micro instance gains no UX benefit from a database at this scale. Choosing the simplest thing that works is engineering judgment, not laziness.

**Disk-persisted job manager**
Job state is written to disk after every status change. If the server crashes mid-analysis, the job is marked as failed on next startup rather than silently hanging. This is the kind of failure mode experienced engineers think about before it happens.

**SSE streaming, not polling**
The loading page uses a real `EventSource` connection to `GET /analyze/{job_id}/stream`. Earlier versions polled every 2 seconds. SSE is more efficient, lower latency, and demonstrates understanding of async streaming patterns.

---

## Problems Faced and How They Were Solved

**NBA Stats API blocks direct HTTP requests**
The health check was hitting `stats.nba.com` directly and getting blocked. The `nba_api` Python library handles auth headers and rate limiting automatically. Fixed by changing the health check to use `nba_api.stats.static.teams.get_teams()`. Lesson: understand the tool before assuming the endpoint is broken.

**F1 game IDs with slashes broke React Router**
F1 races are identified as `2026/6`. Putting this in a URL created `/analysis/f1/2026/6` which React Router parses as sport=`f1`, gameId=`2026`, with a dangling `/6` matching nothing. Fixed by encoding slashes as underscores in navigation and decoding them back before cache lookups. Lesson: URL-safe ID encoding is not optional.

**Cost tracking reporting Sonnet pricing for Opus calls**
The narrative agent was upgraded to `claude-opus-4-8` but the cost tracker still logged `claude-sonnet-4-6`, causing 15x cost underreporting. Found during a LangSmith trace audit. Lesson: observability tools catch bugs that unit tests miss.

**Soccer BSD API silently returning 2022 World Cup data**
The fetcher tried `league_id=27` (FIFA World Cup) which only has 2022 data. The system served Serbia vs Switzerland from December 2022 as if it were a recent match. Fixed by adding date validation: if match date is before 2025-01-01, reject and fall back to Premier League. Lesson: validate data currency, not just data presence.

**NBA playoff context missing from narratives**
Analyses of NBA Finals games never mentioned "NBA Finals" or which game number it was. The fetcher pulled box scores but not playoff series metadata. Fixed by parsing the game_id format: playoff IDs start with `004`, round number is at positions 4-5, game number is the last digit. Added `get_playoff_context()` and prepended a CRITICAL PLAYOFF CONTEXT header to all three agent prompts. Lesson: the data you need is often already available; you just have to know where to look.

**Docker cache folder permissions**
When Docker created the `cache/` directory, it was owned by root inside the container. Copying files in via `scp` failed with "Permission denied." Fixed with `chmod 777`. Lesson: container filesystem permissions behave differently from host permissions, especially with bind mounts.

---

## Evaluation Suite

Two-tier system, zero manual labeling:

```
TIER 1 (free, runs on every commit via GitHub Actions):
  Environment        6/6   API keys, imports, directory structure
  Cache System       7/7   Write, read, invalidate, speed, cost
  Intent Classifier  20/20 All 7 categories correct
  NBA Quality        8/8   Narrative length, statistics, player structure
  F1 Quality         7/7   Driver names, race terminology, championship context
  Soccer Quality     7/7   Goal events, team names, no hallucinated stats
  Valorant Quality   5/5   Agent names, round structure
  MLB Quality        9/9   Pitching/batting stats, linescore context
  Error Handling     4/4   Invalid teams, unsupported sports, empty inputs

TIER 2 (live pipeline, costs ~$0.42):
  End-to-end fresh runs for each sport

Result: 9/9 suites passing across 40 cached analyses
```

---

## What I Learned

**LangGraph changes how you think about agents.** Before this project, I thought of AI agents as LLM calls in a for loop. LangGraph forced me to think about agents as nodes in a state machine: what state flows between them, what conditions route between them, when they run in parallel, when they skip. That mental model is more powerful and more production-appropriate than anything I had built before.

**Model selection is a cost/quality tradeoff, not a "use the best one" decision.** Using Claude Opus for every agent would cost $0.40 per analysis and produce marginal improvement in chat quality. The right architecture uses Opus where quality is user-visible and cheaper models where the task is grounded. Understanding where each dollar of LLM spend goes is a production engineering skill.

**Observability is not optional.** Without LangSmith traces, I would never have caught the Opus/Sonnet cost tracking bug. The trace showed the model being called, the model being logged, and the discrepancy between them in 30 seconds. Adding observability from the start, not as an afterthought, is the right approach.

**The hardest problems are data problems, not AI problems.** Most bugs in this project were not about AI outputs being wrong. They were about data being stale, URLs being malformed, permissions being wrong, or API responses having unexpected structure. Clean data in, good analysis out.

**Knowing when NOT to use an LLM is as important as knowing when to.** The intent classifier is pure Python. The router is a dictionary lookup. The cost tracker is arithmetic. These could all be LLM calls. They would just be 1000x slower and cost money for no improvement.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph, LangChain |
| **LLM (pipeline)** | Claude Opus 4 (`claude-opus-4-8`) |
| **LLM (chat)** | GPT-4o-mini |
| **Observability** | LangSmith (per-agent traces, cost attribution) |
| **Memory** | Mem0 (persistent chat context) |
| **MCP** | FastMCP (AI-callable tool server) |
| **Backend** | FastAPI, Uvicorn, SSE streaming |
| **Frontend** | React 18, Vite, Framer Motion |
| **Voice** | ElevenLabs TTS (George voice) |
| **Deployment** | AWS EC2, Docker, Nginx, docker-compose |
| **CI** | GitHub Actions (eval suite + build on every push) |
| **Data** | NBA Stats API, Jolpica F1, BSD Soccer, VLR, MLB Stats |

---

## Running Locally

```bash
git clone https://github.com/Rohith2320/Sportscast-ai.git
cd Sportscast-ai

cp .env.example .env
# Fill in your API keys

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn api.main:app --reload --port 8000
```

```bash
# Frontend (separate terminal)
cd ui-react
npm install
npm run dev
# Open http://localhost:5173
```

```bash
# With Docker
docker compose up --build
# Open http://localhost
```

```bash
# Run evaluation suite
python -m tests.test_production_eval        # Tier 1 (free)
python -m tests.test_production_eval --live # Tier 2 (~$0.42)
```

```bash
# MCP Server (Claude Desktop / Claude Code integration)
python mcp_server.py   # port 8001
# Tools: analyze_sport, list_cached_analyses, chat_about_game, discover_latest_game
```

---

## Required API Keys

| Key | Source | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | Yes |
| `OPENAI_API_KEY` | platform.openai.com | Yes |
| `BSD_API_KEY` | betsapi.com | Yes (Soccer) |
| `RIOT_API_KEY` | developer.riotgames.com | Yes (Valorant) |
| `ELEVENLABS_API_KEY` | elevenlabs.io | Optional |
| `LANGCHAIN_API_KEY` | smith.langchain.com | Optional |

NBA, F1, and MLB use free APIs with no key required.

---

## Project Structure

```
sportscast-ai/
├── agents/                     5 LangGraph agent nodes
│   ├── match_analysis_agent.py
│   ├── player_analysis_agent.py
│   ├── enrichment_agent.py
│   ├── narrative_agent.py
│   └── chat_agent.py           GPT-4o-mini + Mem0 + intent classifier
├── api/                        FastAPI backend
│   ├── routes/                 analyze, chat, games, health, tts, discovery
│   └── services/job_manager.py disk-persisted job state
├── data_sources/               one fetcher per sport
├── utils/                      cache, cost tracker, logger, retry, state
├── ui-react/                   React 18 + Vite frontend
├── tests/test_production_eval.py two-tier eval suite
├── mcp_server.py               FastMCP server
├── graph.py                    LangGraph pipeline definition
├── Dockerfile                  backend container
├── docker-compose.yml          orchestration
└── .github/workflows/ci.yml   GitHub Actions CI
```

---

## Live Demo

**URL:** http://3.227.255.166

Best ways to experience the system:

1. Click **NBA** > **Discover Latest** > wait 90 seconds for a fresh Finals analysis
2. Click **F1** > open the Canadian GP > click **Voice Commentary** for ElevenLabs audio
3. Click **MLB** > open any game > ask the chat "who was the best pitcher and why?"
4. Click **LangSmith trace** button on any analysis page to see live agent execution data

---

<div align="center">

Built by **Rohith Reddy Kar**

MS Applied Information Technology (ML) · George Mason University · May 2026

F-1 OPT eligible · Targeting ML Engineer and AI Engineer roles

[![LinkedIn](https://img.shields.io/badge/LinkedIn-rohith--reddy--kar-0077B5?style=flat-square&logo=linkedin)](https://linkedin.com/in/rohith-reddy-kar-76536226a)
[![GitHub](https://img.shields.io/badge/GitHub-Rohith2320-181717?style=flat-square&logo=github)](https://github.com/Rohith2320)
[![Email](https://img.shields.io/badge/Email-rohithreddykar20%40gmail.com-EA4335?style=flat-square&logo=gmail)](mailto:rohithreddykar20@gmail.com)

</div>
