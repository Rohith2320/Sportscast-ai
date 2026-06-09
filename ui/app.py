import streamlit as st
import requests
import time

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="SportsCast AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&display=swap');

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display: none;}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main { background-color: #0A0A0A; }

.hero-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 72px;
    line-height: 1;
    color: #FFFFFF;
    letter-spacing: 2px;
    margin: 0;
    padding: 0;
}

.hero-subtitle {
    font-size: 16px;
    color: #888888;
    font-weight: 300;
    margin-top: 8px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.game-card {
    background: #111111;
    border: 1px solid #1E1E1E;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 12px;
}

.game-card-sport {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.game-card-title {
    font-size: 18px;
    font-weight: 600;
    color: #FFFFFF;
    margin-bottom: 4px;
}

.game-card-meta {
    font-size: 12px;
    color: #555;
    margin-top: 8px;
}

.narrative-container {
    background: #0F0F0F;
    border-left: 3px solid #E8FF00;
    padding: 32px;
    border-radius: 0 8px 8px 0;
    margin: 16px 0;
}

.narrative-text {
    font-size: 17px;
    line-height: 1.8;
    color: #DDDDDD;
    font-weight: 300;
}

.progress-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
    font-size: 14px;
    color: #888;
}

.progress-done { color: #E8FF00; }

.cost-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.cost-cached {
    background: #0A2A0A;
    color: #44FF44;
    border: 1px solid #1A4A1A;
}

.cost-fresh {
    background: #2A1A0A;
    color: #FFAA44;
    border: 1px solid #4A3A1A;
}

.chat-message-user {
    background: #1A1A2E;
    border-radius: 12px 12px 4px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 14px;
    color: #FFFFFF;
    text-align: right;
}

.chat-message-ai {
    background: #111111;
    border: 1px solid #1E1E1E;
    border-radius: 12px 12px 12px 4px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 14px;
    color: #DDDDDD;
    line-height: 1.6;
}

.intent-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    background: #1A1A1A;
    color: #555;
    margin-bottom: 6px;
}

.section-divider {
    border: none;
    border-top: 1px solid #1E1E1E;
    margin: 32px 0;
}
/* Fix button text contrast */
.stButton > button[kind="primary"] {
    color: #000000 !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

SPORTS = {
    "nba":      {"label": "NBA",      "icon": "🏀", "color": "#FF6B35", "desc": "Basketball"},
    "f1":       {"label": "F1",       "icon": "🏎️", "color": "#E8002D", "desc": "Formula 1"},
    "soccer":   {"label": "Soccer",   "icon": "⚽", "color": "#00D4AA", "desc": "Football"},
    "valorant": {"label": "Valorant", "icon": "🎮", "color": "#FF4655", "desc": "Esports"},
    "mlb":      {"label": "MLB",      "icon": "⚾", "color": "#1E90FF", "desc": "Baseball"},
}


def api_get(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        if r.status_code == 200:
            return r.json()
        return {}
    except Exception:
        return {}


def api_post(endpoint, data):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {}
    except Exception:
        return {}


def start_analysis(sport, match_id, persona, force_refresh):
    result = api_post("/analyze/", {
        "sport": sport,
        "match_id": match_id,
        "persona": persona,
        "force_refresh": force_refresh
    })
    return result.get("job_id", "")


def poll_job(job_id):
    return api_get(f"/analyze/{job_id}")


def get_cached_games(sport=None):
    endpoint = f"/games/?sport={sport}" if sport else "/games/"
    result = api_get(endpoint)
    return result.get("games", [])


def chat_with_game(sport, game_id, query, history):
    safe_id = game_id.replace("/", "_")
    return api_post("/chat/", {
        "sport": sport,
        "game_id": safe_id,
        "query": query,
        "chat_history": history
    })


if "selected_sport" not in st.session_state:
    st.session_state.selected_sport = "nba"
if "selected_game" not in st.session_state:
    st.session_state.selected_game = None
if "current_view" not in st.session_state:
    st.session_state.current_view = "home"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None


def render_sport_selector():
    sport = st.session_state.selected_sport
    cols = st.columns(len(SPORTS))
    for i, (key, config) in enumerate(SPORTS.items()):
        with cols[i]:
            is_active = key == sport
            label = config["icon"] + " " + config["label"]
            if st.button(
                label,
                key="sport_btn_" + key,
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.selected_sport = key
                st.session_state.current_view = "home"
                st.session_state.selected_game = None
                st.session_state.chat_history = []
                st.rerun()


def render_game_card(game, sport_config):
    game_id = game.get("game_id", "")
    match_id = game.get("match_id", game_id)
    cached_at = game.get("cached_at", "")[:10]
    color = sport_config["color"]
    icon = sport_config["icon"]
    label = sport_config["label"]
    # Make title more readable
    sport = game.get("sport", "")
    if sport == "nba":
        title = "Game " + match_id[-4:]
    elif sport == "f1":
        parts = match_id.replace("_", "/").split("/")
        title = "Round " + parts[-1] + " — " + parts[0] if len(parts) == 2 else match_id
    elif sport == "mlb":
        title = "Game " + match_id[-4:]
    else:
        title = match_id.replace("_", " ").upper()

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(
            '<div class="game-card">'
            '<div class="game-card-sport" style="color: ' + color + '">'
            + icon + " " + label +
            '</div>'
            '<div class="game-card-title">' + title + '</div>'
            '<div class="game-card-meta">Analyzed ' + cached_at +
            ' &nbsp;·&nbsp; <span style="color: #44FF44">● Cached</span></div>'
            '</div>',
            unsafe_allow_html=True
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("View →", key="view_" + game_id, use_container_width=True):
            st.session_state.selected_game = game
            st.session_state.current_view = "analysis"
            st.session_state.chat_history = []
            st.rerun()


def render_progress(progress, status):
    for msg in progress:
        st.markdown(
            '<div class="progress-item progress-done"><span>✓</span> ' + msg + '</div>',
            unsafe_allow_html=True
        )
    if status == "running":
        st.markdown(
            '<div class="progress-item"><span>⟳</span> Processing...</div>',
            unsafe_allow_html=True
        )


def render_narrative(result, cost):
    narrative = result.get("narrative", "")
    persona = result.get("persona", "espn_formal")

    if cost == 0:
        badge = '<span class="cost-badge cost-cached">⚡ Cached — $0.00</span>'
    else:
        badge = '<span class="cost-badge cost-fresh">Fresh — $' + f"{cost:.4f}" + '</span>'

    persona_label = "ESPN Formal" if persona == "espn_formal" else "Tactical Coach"

    st.markdown(
        '<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">'
        + badge +
        '<span style="font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 1px;">'
        "· " + persona_label +
        "</span></div>",
        unsafe_allow_html=True
    )

    lines = narrative.split("\n")
    clean_lines = []
    title = ""
    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:]
        elif line.startswith("## ") or line.startswith("### "):
            clean_lines.append("\n**" + line.lstrip("#").strip() + "**\n")
        else:
            clean_lines.append(line)

    if title:
        st.markdown("### " + title)

    paragraphs = "\n".join(clean_lines).split("\n\n")
    body = "<br><br>".join([p for p in paragraphs if p.strip()])

    st.markdown(
        '<div class="narrative-container"><div class="narrative-text">'
        + body +
        "</div></div>",
        unsafe_allow_html=True
    )


def render_chat(game):
    sport = game.get("sport", "")
    game_id = game.get("game_id", "")

    st.markdown("---")
    st.markdown("#### 💬 Ask the AI Analyst")

    suggestions = {
        "nba":      ["Why did they win?", "Who was the best player?", "What should they fix?"],
        "f1":       ["Why did the winner win?", "What was the key strategy?", "Who disappointed?"],
        "soccer":   ["Who scored and when?", "What was the turning point?", "Tactical breakdown?"],
        "valorant": ["Why did the winning team win?", "Who carried?", "Tournament impact?"],
        "mlb":      ["Who was the best pitcher?", "What decided the game?", "Hitting performance?"],
    }

    sugg = suggestions.get(sport, [])
    if sugg:
        cols = st.columns(len(sugg))
        for i, q in enumerate(sugg):
            with cols[i]:
                if st.button(q, key="sugg_" + str(i) + "_" + game_id, use_container_width=True):
                    st.session_state["chat_input_" + game_id] = q
                    st.rerun()

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                '<div class="chat-message-user">' + msg["content"] + "</div>",
                unsafe_allow_html=True
            )
        else:
            intent = msg.get("intent", "")
            st.markdown(
                '<div class="chat-message-ai">'
                '<div class="intent-badge">' + intent + "</div>"
                "<div>" + msg["content"] + "</div>"
                "</div>",
                unsafe_allow_html=True
            )


    col_input, col_btn = st.columns([5, 1])
    with col_input:
        query = st.text_input(
            "Ask anything about this game...",
            key="chat_query_" + game_id,
            placeholder="e.g. Why did they win? Who was the MVP?"
        )
    with col_btn:
        st.write("")
        send = st.button("Send →", key="chat_send_" + game_id, type="primary", use_container_width=True)

    # Use suggestion if set
    if st.session_state.get("chat_input_" + game_id):
        query = st.session_state["chat_input_" + game_id]
        st.session_state["chat_input_" + game_id] = ""

    if send:
        if query.strip():
            with st.spinner("Thinking..."):
                response = chat_with_game(
                    sport=sport,
                    game_id=game_id,
                    query=query,
                    history=[
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history
                    ]
                )
            if response.get("response"):
                st.session_state.chat_history.append({"role": "user", "content": query})
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response["response"],
                    "intent": response.get("intent", ""),
                })
                st.session_state["chat_input_" + game_id] = ""
                st.rerun()


def render_home():
    sport_key = st.session_state.selected_sport
    sport_config = SPORTS[sport_key]
    color = sport_config["color"]
    label = sport_config["label"]
    icon = sport_config["icon"]

    st.markdown(
        '<div style="padding: 32px 0 24px 0;">'
        '<div class="hero-title">SPORTSCAST <span style="color: ' + color + '">AI</span></div>'
        '<div class="hero-subtitle">Multi-Agent Sports Analysis · Powered by Claude & GPT-4o-mini</div>'
        "</div>",
        unsafe_allow_html=True
    )

    render_sport_selector()
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("#### " + icon + " Recent " + label + " Analyses")
        games = get_cached_games(sport_key)

        if not games:
            st.markdown(
                '<div style="color: #444; font-size: 14px; padding: 24px 0;">'
                "No analyses yet. Run your first analysis →"
                "</div>",
                unsafe_allow_html=True
            )
        else:
            for game in games[:5]:
                render_game_card(game, sport_config)

    with col2:
        st.markdown("#### ⚡ New Analysis")

        match_input = st.text_input(
            "Team, match ID, or 'latest'",
            value="latest",
            placeholder="Lakers / latest / 824916",
            key="match_input_" + sport_key
        )

        persona = st.selectbox(
            "Persona",
            options=["espn_formal", "tactical_coach"],
            format_func=lambda x: "ESPN Formal" if x == "espn_formal" else "Tactical Coach",
            key="persona_" + sport_key
        )

        force_refresh = st.checkbox(
            "Force fresh analysis (bypass cache)",
            key="force_" + sport_key
        )

        if st.button(
            "Analyze " + label + " →",
            key="analyze_" + sport_key,
            type="primary",
            use_container_width=True
        ):
            with st.spinner("Starting analysis..."):
                job_id = start_analysis(
                    sport=sport_key,
                    match_id=match_input,
                    persona=persona,
                    force_refresh=force_refresh
                )
            if job_id:
                st.session_state.job_id = job_id
                st.session_state.current_view = "loading"
                st.rerun()
            else:
                st.error("Could not connect to API. Make sure the server is running.")


def render_loading():
    job_id = st.session_state.job_id
    if not job_id:
        st.session_state.current_view = "home"
        st.rerun()
        return

    st.markdown(
        '<div style="padding: 32px 0 24px 0;">'
        '<div class="hero-title">ANALYZING...</div>'
        '<div class="hero-subtitle">Multi-agent pipeline running</div>'
        "</div>",
        unsafe_allow_html=True
    )

    if st.button("← Back", key="back_loading"):
        st.session_state.current_view = "home"
        st.session_state.job_id = None
        st.rerun()

    progress_container = st.empty()

    max_polls = 120
    for i in range(max_polls):
        job = poll_job(job_id)
        status = job.get("status", "unknown")
        progress = job.get("progress", [])

        with progress_container.container():
            render_progress(progress, status)

        if status == "complete":
            result = job.get("result", {})
            cost = job.get("cost", 0)
            game_data = {
                "game_id": result.get("match_id", ""),
                "match_id": result.get("match_id", ""),
                "sport": job.get("sport", ""),
                "cached_at": job.get("completed_at", "")[:10],
            }
            st.session_state.selected_game = {**game_data, "result": result, "cost": cost}
            st.session_state.analysis_result = result
            st.session_state.current_view = "analysis"
            st.rerun()
            return

        if status == "failed":
            error = job.get("error", "Unknown error")
            st.error("Analysis failed: " + error)
            if st.button("← Try Again"):
                st.session_state.current_view = "home"
                st.session_state.job_id = None
                st.rerun()
            return

        time.sleep(2)
        st.rerun()

    st.error("Analysis timed out. Please try again.")


def render_analysis():
    game = st.session_state.selected_game
    if not game:
        st.session_state.current_view = "home"
        st.rerun()
        return

    sport_key = game.get("sport", "nba")
    sport_config = SPORTS.get(sport_key, SPORTS["nba"])
    game_id = game.get("game_id", "")
    safe_game_id = game_id.replace("/", "_")
    cost = game.get("cost", 0)
    color = sport_config["color"]
    icon = sport_config["icon"]
    label = sport_config["label"]
    game_title = game_id.replace("_", " ").upper()

    result = game.get("result")
    if not result:
        safe_game_id = game_id.replace("/", "_")
        cached = api_get("/games/" + sport_key + "/" + safe_game_id)
        if cached:
            result = cached
            game["result"] = result

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(
            '<div style="padding: 24px 0 16px 0;">'
            '<div style="font-size: 11px; color: ' + color + '; letter-spacing: 3px; '
            'text-transform: uppercase; margin-bottom: 8px;">'
            + icon + " " + label + " Analysis"
            "</div>"
            '<div class="hero-title" style="font-size: 48px;">'
            + game_title +
            "</div></div>",
            unsafe_allow_html=True
        )
    with col2:
        st.write("")
        st.write("")
        st.write("")
        if st.button("← Back", key="back_analysis", use_container_width=True):
            st.session_state.current_view = "home"
            st.session_state.selected_game = None
            st.session_state.chat_history = []
            st.rerun()

        new_persona = st.selectbox(
            "Persona",
            options=["espn_formal", "tactical_coach"],
            format_func=lambda x: "ESPN Formal" if x == "espn_formal" else "Tactical Coach",
            key="analysis_persona"
        )

        if st.button("Regenerate →", key="regen", use_container_width=True):
            with st.spinner("Starting..."):
                job_id = start_analysis(
                    sport=sport_key,
                    match_id=game.get("match_id", "latest"),
                    persona=new_persona,
                    force_refresh=True
                )
            if job_id:
                st.session_state.job_id = job_id
                st.session_state.current_view = "loading"
                st.rerun()

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    if not result:
        st.error("Could not load analysis. Please go back and try again.")
        return

    tab1, tab2, tab3 = st.tabs(["📰 Narrative", "📊 Match Analysis", "👤 Player Analysis"])

    with tab1:
        render_narrative(result, cost)

    with tab2:
        match_analysis = result.get("match_analysis", "")
        if match_analysis:
            st.markdown(match_analysis)
        else:
            st.info("No match analysis available.")

    with tab3:
        player_analysis = result.get("player_analysis", "")
        if player_analysis:
            st.markdown(player_analysis)
        else:
            st.info("No player analysis available.")

    render_chat(game)


def main():
    view = st.session_state.current_view
    if view == "home":
        render_home()
    elif view == "loading":
        render_loading()
    elif view == "analysis":
        render_analysis()
    else:
        render_home()


if __name__ == "__main__":
    main()
