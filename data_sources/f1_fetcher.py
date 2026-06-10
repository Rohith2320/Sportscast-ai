import requests
import time
from utils.state import SportsCastState
from utils.logger import log_agent_start, log_agent_complete, log_error, log_api_call
from utils.retry import with_retry

BASE_URL = "http://api.jolpi.ca/ergast/f1"

# ── 2026 F1 Calendar — friendly name → "season/round" ──────────────────────
# Covers country names, city names, GP names, and common abbreviations.
# Fetched from api.jolpi.ca/ergast/f1/2026.json on 2026-06-10.
F1_2026_ROUND_LOOKUP: dict[str, str] = {
    # Round 1: Australian Grand Prix — Melbourne
    "australia": "2026/1", "australian": "2026/1", "melbourne": "2026/1",
    "australian gp": "2026/1", "australian grand prix": "2026/1",

    # Round 2: Chinese Grand Prix — Shanghai
    "china": "2026/2", "chinese": "2026/2", "shanghai": "2026/2",
    "chinese gp": "2026/2", "chinese grand prix": "2026/2",

    # Round 3: Japanese Grand Prix — Suzuka
    "japan": "2026/3", "japanese": "2026/3", "suzuka": "2026/3",
    "japanese gp": "2026/3", "japanese grand prix": "2026/3",

    # Round 4: Miami Grand Prix
    "miami": "2026/4", "miami gp": "2026/4", "miami grand prix": "2026/4",

    # Round 5: Canadian Grand Prix — Montreal
    "canada": "2026/5", "canadian": "2026/5", "montreal": "2026/5",
    "canadian gp": "2026/5", "canadian grand prix": "2026/5",

    # Round 6: Monaco Grand Prix — Monte Carlo
    "monaco": "2026/6", "monte carlo": "2026/6",
    "monaco gp": "2026/6", "monaco grand prix": "2026/6",

    # Round 7: Barcelona Grand Prix — Barcelona, Spain
    "barcelona": "2026/7", "barcelona gp": "2026/7", "barcelona grand prix": "2026/7",

    # Round 8: Austrian Grand Prix — Spielberg (Red Bull Ring)
    "austria": "2026/8", "austrian": "2026/8", "spielberg": "2026/8",
    "red bull ring": "2026/8",
    "austrian gp": "2026/8", "austrian grand prix": "2026/8",

    # Round 9: British Grand Prix — Silverstone
    "britain": "2026/9", "british": "2026/9", "silverstone": "2026/9", "uk": "2026/9",
    "british gp": "2026/9", "british grand prix": "2026/9",

    # Round 10: Belgian Grand Prix — Spa
    "belgium": "2026/10", "belgian": "2026/10", "spa": "2026/10",
    "belgian gp": "2026/10", "belgian grand prix": "2026/10",

    # Round 11: Hungarian Grand Prix — Budapest
    "hungary": "2026/11", "hungarian": "2026/11", "budapest": "2026/11",
    "hungarian gp": "2026/11", "hungarian grand prix": "2026/11",

    # Round 12: Dutch Grand Prix — Zandvoort
    "netherlands": "2026/12", "dutch": "2026/12", "zandvoort": "2026/12",
    "holland": "2026/12",
    "dutch gp": "2026/12", "dutch grand prix": "2026/12",

    # Round 13: Italian Grand Prix — Monza
    "italy": "2026/13", "italian": "2026/13", "monza": "2026/13",
    "italian gp": "2026/13", "italian grand prix": "2026/13",

    # Round 14: Spanish Grand Prix — Madrid (NOT Barcelona)
    "spain": "2026/14", "spanish": "2026/14", "madrid": "2026/14",
    "spanish gp": "2026/14", "spanish grand prix": "2026/14",

    # Round 15: Azerbaijan Grand Prix — Baku
    "azerbaijan": "2026/15", "baku": "2026/15",
    "azerbaijan gp": "2026/15", "azerbaijan grand prix": "2026/15",

    # Round 16: Singapore Grand Prix — Marina Bay
    "singapore": "2026/16", "marina bay": "2026/16",
    "singapore gp": "2026/16", "singapore grand prix": "2026/16",

    # Round 17: United States Grand Prix — Austin / COTA
    "united states": "2026/17", "usa": "2026/17", "austin": "2026/17", "cota": "2026/17",
    "us gp": "2026/17", "united states gp": "2026/17", "united states grand prix": "2026/17",

    # Round 18: Mexico City Grand Prix
    "mexico": "2026/18", "mexico city": "2026/18",
    "mexico gp": "2026/18", "mexico grand prix": "2026/18",

    # Round 19: Brazilian Grand Prix — Sao Paulo / Interlagos
    "brazil": "2026/19", "brazilian": "2026/19", "sao paulo": "2026/19",
    "interlagos": "2026/19",
    "brazilian gp": "2026/19", "brazilian grand prix": "2026/19",

    # Round 20: Las Vegas Grand Prix
    "las vegas": "2026/20", "vegas": "2026/20",
    "las vegas gp": "2026/20", "las vegas grand prix": "2026/20",

    # Round 21: Qatar Grand Prix — Lusail
    "qatar": "2026/21", "lusail": "2026/21",
    "qatar gp": "2026/21", "qatar grand prix": "2026/21",

    # Round 22: Abu Dhabi Grand Prix — Yas Marina
    "abu dhabi": "2026/22", "yas marina": "2026/22",
    "abu dhabi gp": "2026/22", "abu dhabi grand prix": "2026/22",
}


def safe_fetch(url: str, label: str) -> dict:
    """
    Safely fetch a URL and return parsed JSON.
    Returns empty dict on failure instead of crashing.
    """
    try:
        log_api_call("Jolpica F1 API", label)
        time.sleep(0.5)  # Respectful rate limiting
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: Could not fetch {label}: {e}")
        return {}


@with_retry(max_attempts=3, base_delay=2)
def fetch_race_weekend(
    season: str = "current",
    round_number: str = "last"
) -> dict:
    """
    Fetch complete F1 race weekend data including practice,
    qualifying, race results, pit stops and championship standings.

    Args:
        season: Season year e.g. "2026" or "current"
        round_number: Round number e.g. "8" or "last"

    Returns:
        Complete race weekend dictionary
    """

    base = f"{BASE_URL}/{season}/{round_number}"

    # ── Race Results ──
    race_data = safe_fetch(f"{base}/results.json", f"{season}/{round_number}/results")
    races = race_data.get("MRData", {}).get("RaceTable", {}).get("Races", [])

    if not races:
        raise ValueError(f"No race found for {season} round {round_number}")

    race = races[0]
    race_name = race["raceName"]
    circuit = race["Circuit"]["circuitName"]
    location = f"{race['Circuit']['Location']['locality']}, {race['Circuit']['Location']['country']}"
    date = race["date"]
    actual_season = race["season"]
    actual_round = race["round"]

    print(f"Fetching full weekend data for: {race_name}")

    # ── Qualifying ──
    qual_data = safe_fetch(f"{base}/qualifying.json", f"{season}/{round_number}/qualifying")
    qualifying = []
    if qual_data.get("MRData", {}).get("RaceTable", {}).get("Races"):
        qualifying = qual_data["MRData"]["RaceTable"]["Races"][0].get(
            "QualifyingResults", []
        )

    # ── Practice 1 ──
    fp1_data = safe_fetch(f"{base}/practice/1.json", f"{season}/{round_number}/practice/1")
    practice_1 = []
    if fp1_data.get("MRData", {}).get("RaceTable", {}).get("Races"):
        practice_1 = fp1_data["MRData"]["RaceTable"]["Races"][0].get(
            "PracticeResults", []
        )

    # ── Practice 2 ──
    fp2_data = safe_fetch(f"{base}/practice/2.json", f"{season}/{round_number}/practice/2")
    practice_2 = []
    if fp2_data.get("MRData", {}).get("RaceTable", {}).get("Races"):
        practice_2 = fp2_data["MRData"]["RaceTable"]["Races"][0].get(
            "PracticeResults", []
        )

    # ── Practice 3 ──
    fp3_data = safe_fetch(f"{base}/practice/3.json", f"{season}/{round_number}/practice/3")
    practice_3 = []
    if fp3_data.get("MRData", {}).get("RaceTable", {}).get("Races"):
        practice_3 = fp3_data["MRData"]["RaceTable"]["Races"][0].get(
            "PracticeResults", []
        )

    # ── Pit Stops ──
    pit_data = safe_fetch(f"{base}/pitstops.json", f"{season}/{round_number}/pitstops")
    pit_stops = []
    if pit_data.get("MRData", {}).get("RaceTable", {}).get("Races"):
        pit_stops = pit_data["MRData"]["RaceTable"]["Races"][0].get(
            "PitStops", []
        )

    # ── Driver Standings after this race ──
    standings_data = safe_fetch(
        f"{BASE_URL}/{actual_season}/{actual_round}/driverStandings.json",
        f"{actual_season}/{actual_round}/driverStandings"
    )
    driver_standings = []
    standings_lists = standings_data.get("MRData", {}).get(
        "StandingsTable", {}
    ).get("StandingsLists", [])
    if standings_lists:
        driver_standings = standings_lists[0].get("DriverStandings", [])

    # ── Constructor Standings ──
    constructor_data = safe_fetch(
        f"{BASE_URL}/{actual_season}/{actual_round}/constructorStandings.json",
        f"{actual_season}/{actual_round}/constructorStandings"
    )
    constructor_standings = []
    constructor_lists = constructor_data.get("MRData", {}).get(
        "StandingsTable", {}
    ).get("StandingsLists", [])
    if constructor_lists:
        constructor_standings = constructor_lists[0].get(
            "ConstructorStandings", []
        )

    return {
        "race_name": race_name,
        "circuit": circuit,
        "location": location,
        "date": date,
        "season": actual_season,
        "round": actual_round,
        "results": race["Results"],
        "qualifying": qualifying,
        "practice_1": practice_1,
        "practice_2": practice_2,
        "practice_3": practice_3,
        "pit_stops": pit_stops,
        "driver_standings": driver_standings,
        "constructor_standings": constructor_standings,
    }


def format_f1_data(raw_data: dict) -> str:
    """
    Format complete F1 weekend data into clean readable text for the LLM.
    Covers practice, qualifying, race, pit strategy, and championship context.
    """

    lines = []

    # Header
    lines.append(f"=== {raw_data['race_name'].upper()} ===")
    lines.append(f"Circuit: {raw_data['circuit']}")
    lines.append(f"Location: {raw_data['location']}")
    lines.append(f"Date: {raw_data['date']}")
    lines.append(f"Season: {raw_data['season']} | Round: {raw_data['round']}")
    lines.append("")

    # Practice 1
    if raw_data.get("practice_1"):
        lines.append("=== PRACTICE 1 ===")
        for r in raw_data["practice_1"][:10]:
            driver = f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            team = r["Constructor"]["name"]
            time_val = r.get("Time", {}).get("time", "No time")
            lines.append(f"P{r['position']}: {driver} ({team}) | {time_val}")
        lines.append("")

    # Practice 2
    if raw_data.get("practice_2"):
        lines.append("=== PRACTICE 2 ===")
        for r in raw_data["practice_2"][:10]:
            driver = f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            team = r["Constructor"]["name"]
            time_val = r.get("Time", {}).get("time", "No time")
            lines.append(f"P{r['position']}: {driver} ({team}) | {time_val}")
        lines.append("")

    # Practice 3
    if raw_data.get("practice_3"):
        lines.append("=== PRACTICE 3 ===")
        for r in raw_data["practice_3"][:10]:
            driver = f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            team = r["Constructor"]["name"]
            time_val = r.get("Time", {}).get("time", "No time")
            lines.append(f"P{r['position']}: {driver} ({team}) | {time_val}")
        lines.append("")

    # Qualifying
    if raw_data.get("qualifying"):
        lines.append("=== QUALIFYING ===")
        for q in raw_data["qualifying"]:
            driver = f"{q['Driver']['givenName']} {q['Driver']['familyName']}"
            team = q["Constructor"]["name"]
            q3 = q.get("Q3", q.get("Q2", q.get("Q1", "N/A")))
            lines.append(
                f"P{q['position']}: {driver} ({team}) | Best: {q3}"
            )
        lines.append("")

    # Race Results
    lines.append("=== RACE RESULTS ===")
    for result in raw_data["results"]:
        driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
        team = result["Constructor"]["name"]
        position = result["position"]
        status = result["status"]
        points = result.get("points", "0")
        grid = result.get("grid", "?")

        time_info = ""
        if "Time" in result:
            time_info = result["Time"]["time"]
        else:
            time_info = status

        fastest = ""
        if result.get("FastestLap", {}).get("rank") == "1":
            fastest_time = result["FastestLap"]["Time"]["time"]
            fastest = f" | FASTEST LAP: {fastest_time}"

        # Position gained/lost
        pos_change = int(grid) - int(position) if grid.isdigit() else 0
        change_str = ""
        if pos_change > 0:
            change_str = f" | +{pos_change} positions"
        elif pos_change < 0:
            change_str = f" | {pos_change} positions"

        lines.append(
            f"P{position} (Grid P{grid}): {driver} ({team}) | "
            f"{time_info} | {points} pts{fastest}{change_str}"
        )
    lines.append("")

    # Pit Stop Strategy
    if raw_data.get("pit_stops"):
        lines.append("=== PIT STOP STRATEGY ===")

        # Group by driver
        driver_pits = {}
        for pit in raw_data["pit_stops"]:
            driver_id = pit["driverId"]
            if driver_id not in driver_pits:
                driver_pits[driver_id] = []
            driver_pits[driver_id].append(pit)

        for driver_id, pits in driver_pits.items():
            stop_count = len(pits)
            stops_detail = " | ".join([
                f"Lap {p['lap']} ({p['duration']}s)"
                for p in pits
            ])
            lines.append(
                f"{driver_id}: {stop_count} stop(s) — {stops_detail}"
            )
        lines.append("")

    # Championship Standings (top 5)
    if raw_data.get("driver_standings"):
        lines.append("=== CHAMPIONSHIP STANDINGS (after this race) ===")
        for standing in raw_data["driver_standings"][:8]:
            driver = standing["Driver"]
            driver_name = f"{driver['givenName']} {driver['familyName']}"
            team = standing["Constructors"][0]["name"]
            points = standing["points"]
            wins = standing["wins"]
            lines.append(
                f"P{standing['position']}: {driver_name} ({team}) | "
                f"{points} pts | {wins} wins"
            )
        lines.append("")

    # Constructor Standings (top 5)
    if raw_data.get("constructor_standings"):
        lines.append("=== CONSTRUCTOR STANDINGS ===")
        for standing in raw_data["constructor_standings"][:5]:
            team = standing["Constructor"]["name"]
            points = standing["points"]
            wins = standing["wins"]
            lines.append(
                f"P{standing['position']}: {team} | {points} pts | {wins} wins"
            )

    return "\n".join(lines)


def f1_fetch_node(state: SportsCastState) -> dict:
    """
    LangGraph node that fetches complete F1 race weekend data.

    Accepts match_id as:
    - "latest" or empty — fetches most recent race
    - "2026/8" — fetches specific season/round
    - "8" — fetches round 8 of current season
    """

    match_id = state["match_id"]
    start_time = log_agent_start("F1FetchAgent")

    try:
        if not match_id or match_id == "latest":
            raw_data = fetch_race_weekend("current", "last")
        else:
            # Resolve friendly name (e.g. "monaco" → "2026/6") before hitting API
            resolved = F1_2026_ROUND_LOOKUP.get(match_id.lower().strip())
            if resolved:
                print(f"Resolved '{match_id}' → {resolved}")
                match_id = resolved

            if "/" in match_id:
                parts = match_id.split("/")
                raw_data = fetch_race_weekend(parts[0], parts[1])
            else:
                raw_data = fetch_race_weekend("current", match_id)

        print(f"Fetched: {raw_data['race_name']} ({raw_data['date']})")
        print(f"Practice sessions: FP1={len(raw_data['practice_1'])} "
              f"FP2={len(raw_data['practice_2'])} "
              f"FP3={len(raw_data['practice_3'])}")
        print(f"Qualifying: {len(raw_data['qualifying'])} drivers")
        print(f"Race results: {len(raw_data['results'])} drivers")
        print(f"Pit stops: {len(raw_data['pit_stops'])} recorded")

        log_agent_complete("F1FetchAgent", start_time)
        return {
            "raw_match_data": raw_data,
            "match_id": f"{raw_data['season']}/{raw_data['round']}"
        }

    except Exception as e:
        log_error("F1FetchAgent", str(e))
        return {"error": f"F1 data fetch failed: {str(e)}"}