"""
SportsCast AI — Two-Tier Production Evaluation Suite

TIER 1 — Cache Quality Tests (free, runs every time)
    Verifies narrative quality, structure, content, sport terminology,
    enrichment behavior, cost behavior, and data integrity.

TIER 2 — Live Pipeline Tests (costs ~$0.42, run manually)
    Actually runs pipelines end-to-end to verify live behavior,
    bug fixes, and API connectivity.

Usage:
    python -m tests.test_production_eval           # Tier 1 only (free)
    python -m tests.test_production_eval --live    # Both tiers
"""

import time
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

RUN_LIVE = "--live" in sys.argv


# ─────────────────────────────────────────────
# TEST INFRASTRUCTURE
# ─────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.failed = False
        self.skipped = False
        self.message = ""
        self.duration = 0.0

    def pass_test(self, message: str = ""):
        self.passed = True
        self.message = message

    def fail_test(self, message: str):
        self.failed = True
        self.message = message

    def skip_test(self, message: str):
        self.skipped = True
        self.message = message


class TestSuite:
    def __init__(self, name: str):
        self.name = name
        self.results = []

    def run(self, test_name: str, test_fn):
        result = TestResult(test_name)
        start = time.time()
        try:
            test_fn(result)
        except Exception as e:
            result.fail_test(f"Unexpected exception: {str(e)}")
        result.duration = round(time.time() - start, 2)
        self.results.append(result)
        icon = "+" if result.passed else "x" if result.failed else "-"
        print(f"  [{icon}] {test_name} ({result.duration}s) — {result.message}")
        return result

    def summary(self):
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if r.failed)
        skipped = sum(1 for r in self.results if r.skipped)
        total = len(self.results)
        print(f"\n{'=' * 60}")
        print(f"{self.name} RESULTS: {passed}/{total} passed, {failed} failed, {skipped} skipped")
        print('=' * 60)
        if failed > 0:
            print("Failed tests:")
            for r in self.results:
                if r.failed:
                    print(f"  - {r.name}: {r.message}")
        return failed == 0


# ─────────────────────────────────────────────
# TIER 1 — ENVIRONMENT
# ─────────────────────────────────────────────

def run_environment_tests():
    suite = TestSuite("ENVIRONMENT")
    print(f"\n{'=' * 60}")
    print("TIER 1 — ENVIRONMENT TESTS")
    print('=' * 60)

    def test_openai_key(r):
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or len(key) < 20:
            r.fail_test("OPENAI_API_KEY missing or too short")
        else:
            r.pass_test(f"Key present ({key[:8]}...)")

    def test_anthropic_key(r):
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key or len(key) < 20:
            r.fail_test("ANTHROPIC_API_KEY missing or too short")
        else:
            r.pass_test(f"Key present ({key[:8]}...)")

    def test_bsd_key(r):
        key = os.getenv("BSD_API_KEY", "")
        if not key or len(key) < 10:
            r.fail_test("BSD_API_KEY missing or too short")
        else:
            r.pass_test(f"Key present ({key[:8]}...)")

    def test_riot_key(r):
        key = os.getenv("RIOT_API_KEY", "")
        if not key:
            r.skip_test("RIOT_API_KEY not set")
        elif "RGAPI" not in key:
            r.fail_test("RIOT_API_KEY format looks wrong")
        else:
            r.pass_test("Key present")

    def test_cache_dir(r):
        if not os.path.exists("cache"):
            os.makedirs("cache")
        cached = len([f for f in os.listdir("cache") if f.endswith(".json")])
        r.pass_test(f"Cache directory exists with {cached} cached games")

    def test_imports(r):
        try:
            from graph import run_analysis, run_nba_analysis
            from utils.cache import load_from_cache, save_to_cache
            from utils.cost_tracker import get_session_cost, reset_session_cost
            from agents.chat_agent import classify_intent
            from agents.enrichment_agent import enrichment_node
            from agents.narrative_agent import narrative_node
            r.pass_test("All core imports successful")
        except ImportError as e:
            r.fail_test(f"Import failed: {e}")

    suite.run("OpenAI API Key", test_openai_key)
    suite.run("Anthropic API Key", test_anthropic_key)
    suite.run("BSD API Key", test_bsd_key)
    suite.run("Riot API Key", test_riot_key)
    suite.run("Cache Directory", test_cache_dir)
    suite.run("Core Imports", test_imports)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — CACHE SYSTEM
# ─────────────────────────────────────────────

def run_cache_tests():
    suite = TestSuite("CACHE SYSTEM")
    print(f"\n{'=' * 60}")
    print("TIER 1 — CACHE SYSTEM TESTS")
    print('=' * 60)

    from utils.cache import save_to_cache, load_from_cache, cache_exists, invalidate_cache
    from utils.cost_tracker import reset_session_cost, get_session_cost

    TEST_ID = "test_game_eval_001"
    TEST_SPORT = "test"
    TEST_STATE = {
        "sport": "test", "match_id": TEST_ID,
        "match_analysis": "Test match analysis",
        "player_analysis": "Test player analysis",
        "narrative": "Test narrative content here",
        "persona": "espn_formal", "raw_match_data": {"test": True},
        "chat_history": [], "user_query": None,
        "chat_response": None, "error": None
    }

    def test_write(r):
        save_to_cache(TEST_ID, TEST_SPORT, TEST_STATE)
        r.pass_test("Write successful") if cache_exists(TEST_ID, TEST_SPORT) else r.fail_test("File not created")

    def test_read(r):
        cached = load_from_cache(TEST_ID, TEST_SPORT)
        if cached and cached.get("narrative") == "Test narrative content here":
            r.pass_test("Read returns correct data")
        else:
            r.fail_test(f"Read failed or wrong data")

    def test_speed(r):
        start = time.time()
        for _ in range(10):
            load_from_cache(TEST_ID, TEST_SPORT)
        elapsed = time.time() - start
        if elapsed < 1.0:
            r.pass_test(f"10 reads in {elapsed:.3f}s")
        else:
            r.fail_test(f"Too slow: {elapsed:.3f}s")

    def test_force_refresh(r):
        result = load_from_cache(TEST_ID, TEST_SPORT, force_refresh=True)
        r.pass_test("Force refresh bypasses cache") if result is None else r.fail_test("Should return None")

    def test_missing(r):
        result = load_from_cache("nonexistent_game_xyz", TEST_SPORT)
        r.pass_test("Missing cache returns None") if result is None else r.fail_test("Should return None")

    def test_zero_cost(r):
        reset_session_cost()
        load_from_cache(TEST_ID, TEST_SPORT)
        cost = get_session_cost()
        r.pass_test("Cache load costs $0.00") if cost == 0.0 else r.fail_test(f"Cache load cost ${cost}")

    def test_invalidation(r):
        invalidate_cache(TEST_ID, TEST_SPORT)
        r.pass_test("Invalidation successful") if not cache_exists(TEST_ID, TEST_SPORT) else r.fail_test("File still exists")

    suite.run("Cache Write", test_write)
    suite.run("Cache Read", test_read)
    suite.run("Cache Speed (10 reads)", test_speed)
    suite.run("Force Refresh Bypasses Cache", test_force_refresh)
    suite.run("Missing Cache Returns None", test_missing)
    suite.run("Cache Load Zero Cost", test_zero_cost)
    suite.run("Cache Invalidation", test_invalidation)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — INTENT CLASSIFIER
# ─────────────────────────────────────────────

def run_intent_tests():
    suite = TestSuite("INTENT CLASSIFIER")
    print(f"\n{'=' * 60}")
    print("TIER 1 — INTENT CLASSIFIER TESTS")
    print('=' * 60)

    from agents.chat_agent import classify_intent

    test_cases = [
        ("How many points did LeBron score?", "factual"),
        ("What was the final score?", "factual"),
        ("How many strikeouts did Bubba Chandler get?", "factual"),
        ("What was Verstappen's qualifying position?", "factual"),
        ("Why did the Lakers lose?", "analytical"),
        ("Why did Antonelli win from pole?", "analytical"),
        ("Why did FUT Esports win 2-0?", "analytical"),
        ("Why did Pittsburgh lose the lead?", "analytical"),
        ("Compare Brunson and Wembanyama", "comparative"),
        ("Who was better, Hart or Tatum?", "comparative"),
        ("Compare Hamilton and Russell's race", "comparative"),
        ("What should the Spurs do in Game 2?", "predictive"),
        ("What will happen next race?", "predictive"),
        ("What should Pittsburgh fix in their bullpen?", "predictive"),
        ("That performance was incredible!", "emotional"),
        ("Amazing game tonight", "emotional"),
        ("What do you mean by that?", "clarification"),
        ("Can you clarify what you said?", "clarification"),
        ("Who won the Super Bowl?", "out_of_scope"),
        ("What is the weather today?", "out_of_scope"),
    ]

    for query, expected in test_cases:
        def make_test(q, exp):
            def test_fn(r):
                result = classify_intent(q, [])
                if result == exp:
                    r.pass_test(f"'{q[:35]}' -> {result}")
                else:
                    r.fail_test(f"'{q[:35]}' -> got '{result}', expected '{exp}'")
            return test_fn
        suite.run(f"Intent: {expected}", make_test(query, expected))

    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — NBA CACHE QUALITY
# ─────────────────────────────────────────────

def run_nba_quality_tests():
    suite = TestSuite("NBA QUALITY")
    print(f"\n{'=' * 60}")
    print("TIER 1 — NBA CACHE QUALITY TESTS")
    print('=' * 60)

    from utils.cache import load_from_cache
    cached = load_from_cache("0042500401", "nba")

    if not cached:
        print("  [-] NBA cache not found — skipping all NBA quality tests")
        return True

    narrative = cached.get("narrative", "")
    player_analysis = cached.get("player_analysis", "")
    match_analysis = cached.get("match_analysis", "")

    def test_required_fields(r):
        required = ["match_analysis", "player_analysis", "narrative", "sport", "match_id"]
        missing = [f for f in required if not cached.get(f)]
        r.pass_test("All required fields present") if not missing else r.fail_test(f"Missing: {missing}")

    def test_narrative_length(r):
        words = len(narrative.split())
        if words >= 300:
            r.pass_test(f"{words} words")
        else:
            r.fail_test(f"Too short: {words} words (min 300)")

    def test_no_em_dashes(r):
        if " — " in narrative or " – " in narrative:
            r.fail_test("Em dashes found in narrative")
        else:
            r.pass_test("No em dashes found")

    def test_no_banned_words(r):
        banned = ["notably", "crucially", "underscore", "delve", "encapsulate"]
        found = [w for w in banned if w in narrative.lower()]
        r.pass_test("No banned words found") if not found else r.fail_test(f"Banned words: {found}")

    def test_player_structure(r):
        required_fields = ["PLAYER:", "RATING:", "STATS:", "INSIGHT:"]
        missing = [f for f in required_fields if f not in player_analysis]
        if missing:
            r.fail_test(f"Missing fields: {missing}")
        else:
            count = player_analysis.count("PLAYER:")
            r.pass_test(f"Correct structure — {count} players")

    def test_narrative_has_stats(r):
        import re
        numbers = re.findall(r'\b\d+\b', narrative)
        if len(numbers) >= 10:
            r.pass_test(f"{len(numbers)} specific numbers found in narrative")
        else:
            r.fail_test(f"Too few stats: {len(numbers)} numbers found (min 10)")

    def test_narrative_mentions_teams(r):
        raw = cached.get("raw_match_data", {})
        team_stats = raw.get("team_stats", {})
        teams_data = team_stats.get("data", [])
        headers = team_stats.get("headers", [])
        if not teams_data or "TEAM_NAME" not in headers:
            r.skip_test("Could not extract team names from raw data")
            return
        idx = headers.index("TEAM_NAME")
        teams = [t[idx] for t in teams_data if t[idx]]
        missing = [t for t in teams if t.split()[-1] not in narrative]
        r.pass_test(f"Both teams mentioned") if not missing else r.fail_test(f"Missing teams: {missing}")

    def test_enrichment_ran(r):
        count = player_analysis.count("PLAYER:")
        if count >= 3:
            r.pass_test(f"Enrichment ran — {count} player sections present")
        else:
            r.fail_test(f"Only {count} player sections — enrichment may not have run")

    suite.run("Required Fields Present", test_required_fields)
    suite.run("Narrative Length (300+ words)", test_narrative_length)
    suite.run("No Em Dashes", test_no_em_dashes)
    suite.run("No Banned Words", test_no_banned_words)
    suite.run("Player Analysis Structure", test_player_structure)
    suite.run("Narrative Contains Statistics", test_narrative_has_stats)
    suite.run("Narrative Mentions Both Teams", test_narrative_mentions_teams)
    suite.run("Enrichment Ran for NBA", test_enrichment_ran)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — F1 CACHE QUALITY
# ─────────────────────────────────────────────

def run_f1_quality_tests():
    suite = TestSuite("F1 QUALITY")
    print(f"\n{'=' * 60}")
    print("TIER 1 — F1 CACHE QUALITY TESTS")
    print('=' * 60)

    from utils.cache import load_from_cache
    cached = load_from_cache("2026_5", "f1")

    if not cached:
        print("  [-] F1 cache not found — skipping all F1 quality tests")
        return True

    narrative = cached.get("narrative", "")

    def test_required_fields(r):
        required = ["match_analysis", "player_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        r.pass_test("All required fields present") if not missing else r.fail_test(f"Missing: {missing}")

    def test_narrative_length(r):
        words = len(narrative.split())
        r.pass_test(f"{words} words") if words >= 300 else r.fail_test(f"Too short: {words} words")

    def test_no_em_dashes(r):
        if " — " in narrative or " – " in narrative:
            r.fail_test("Em dashes found")
        else:
            r.pass_test("No em dashes found")

    def test_f1_terminology(r):
        f1_terms = ["pit", "lap", "qualifying", "championship", "points"]
        found = [t for t in f1_terms if t.lower() in narrative.lower()]
        if len(found) >= 3:
            r.pass_test(f"F1 terminology present: {found}")
        else:
            r.fail_test(f"Missing F1 terms — only found: {found}")

    def test_driver_names(r):
        drivers = ["Antonelli", "Hamilton", "Verstappen", "Russell"]
        found = [d for d in drivers if d in narrative]
        if len(found) >= 3:
            r.pass_test(f"Driver names present: {found}")
        else:
            r.fail_test(f"Missing driver names — only found: {found}")

    def test_championship_context(r):
        keywords = ["championship", "standings", "points", "season"]
        found = [k for k in keywords if k.lower() in narrative.lower()]
        if len(found) >= 2:
            r.pass_test(f"Championship context present: {found}")
        else:
            r.fail_test(f"Missing championship context — only found: {found}")

    def test_player_analysis_content(r):
        player_analysis = cached.get("player_analysis", "")
        f1_terms = ["driver", "position", "qualifying", "race", "lap", "strategy"]
        found = [t for t in f1_terms if t.lower() in player_analysis.lower()]
        if len(found) >= 3:
            r.pass_test(f"F1 player analysis has driver content: {found}")
        else:
            r.fail_test(f"F1 player analysis missing driver content — only found: {found}")

    suite.run("Required Fields Present", test_required_fields)
    suite.run("Narrative Length (300+ words)", test_narrative_length)
    suite.run("No Em Dashes", test_no_em_dashes)
    suite.run("F1 Terminology Present", test_f1_terminology)
    suite.run("Driver Names Present", test_driver_names)
    suite.run("Championship Context Present", test_championship_context)
    suite.run("Player Analysis Has Sport-Specific Content", test_player_analysis_content)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — SOCCER CACHE QUALITY
# ─────────────────────────────────────────────

def run_soccer_quality_tests():
    suite = TestSuite("SOCCER QUALITY")
    print(f"\n{'=' * 60}")
    print("TIER 1 — SOCCER CACHE QUALITY TESTS")
    print('=' * 60)

    from utils.cache import load_from_cache
    cached = load_from_cache("374", "soccer")

    if not cached:
        print("  [-] Soccer cache not found — skipping all Soccer quality tests")
        return True

    narrative = cached.get("narrative", "")

    def test_required_fields(r):
        required = ["match_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        r.pass_test("All required fields present") if not missing else r.fail_test(f"Missing: {missing}")

    def test_narrative_length(r):
        words = len(narrative.split())
        r.pass_test(f"{words} words") if words >= 200 else r.fail_test(f"Too short: {words} words")

    def test_no_em_dashes(r):
        if " — " in narrative or " – " in narrative:
            r.fail_test("Em dashes found")
        else:
            r.pass_test("No em dashes found")

    def test_team_names_present(r):
        teams = ["Brighton", "Manchester United"]
        found = [t for t in teams if t in narrative]
        r.pass_test(f"Team names present: {found}") if len(found) == 2 else r.fail_test(f"Missing teams: {[t for t in teams if t not in narrative]}")

    def test_soccer_terminology(r):
        terms = ["goal", "half", "minutes", "match"]
        found = [t for t in terms if t.lower() in narrative.lower()]
        r.pass_test(f"Soccer terminology present: {found}") if len(found) >= 3 else r.fail_test(f"Missing terms: only found {found}")

    def test_incidents_referenced(r):
        # Narrative should reference Bruno Fernandes or Dorgu from real incident data
        key_players = ["Fernandes", "Dorgu", "Manchester United", "Bruno"]
        found = [p for p in key_players if p in narrative]
        r.pass_test(f"Incident players referenced: {found}") if found else r.fail_test("No incident players found in narrative")

    def test_no_hallucinated_stats(r):
        # Soccer has no individual player stats — narrative should not invent specific numbers
        # Check it doesn't claim fake shooting percentages or pass completion rates
        bad_patterns = ["% pass", "% shot", "xG of", "pass accuracy"]
        found = [p for p in bad_patterns if p.lower() in narrative.lower()]
        r.pass_test("No hallucinated individual stats found") if not found else r.fail_test(f"Possible hallucinated stats: {found}")

    suite.run("Required Fields Present", test_required_fields)
    suite.run("Narrative Length (200+ words)", test_narrative_length)
    suite.run("No Em Dashes", test_no_em_dashes)
    suite.run("Team Names Present", test_team_names_present)
    suite.run("Soccer Terminology Present", test_soccer_terminology)
    suite.run("Incident Players Referenced", test_incidents_referenced)
    suite.run("No Hallucinated Individual Stats", test_no_hallucinated_stats)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — VALORANT CACHE QUALITY
# ─────────────────────────────────────────────

def run_valorant_quality_tests():
    suite = TestSuite("VALORANT QUALITY")
    print(f"\n{'=' * 60}")
    print("TIER 1 — VALORANT CACHE QUALITY TESTS")
    print('=' * 60)

    from utils.cache import load_from_cache
    cached = load_from_cache("684611", "valorant")

    if not cached:
        print("  [-] Valorant cache not found — skipping all Valorant quality tests")
        return True

    narrative = cached.get("narrative", "")

    def test_required_fields(r):
        required = ["match_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        r.pass_test("All required fields present") if not missing else r.fail_test(f"Missing: {missing}")

    def test_narrative_length(r):
        words = len(narrative.split())
        r.pass_test(f"{words} words") if words >= 250 else r.fail_test(f"Too short: {words} words")

    def test_no_em_dashes(r):
        if " — " in narrative or " – " in narrative:
            r.fail_test("Em dashes found")
        else:
            r.pass_test("No em dashes found")

    def test_team_names_present(r):
        teams = ["FUT", "FULL SENSE"]
        found = [t for t in teams if t in narrative]
        r.pass_test(f"Team names present: {found}") if len(found) == 2 else r.fail_test(f"Missing teams: {[t for t in teams if t not in narrative]}")

    def test_player_igns_present(r):
        # Roster has s0pp, xeus, yetujey for FUT and Leviathan, Killua for FULL SENSE
        igns = ["s0pp", "xeus", "Leviathan", "Killua", "yetujey"]
        found = [p for p in igns if p in narrative]
        r.pass_test(f"Player IGNs present: {found}") if len(found) >= 2 else r.fail_test(f"Too few IGNs — only found: {found}")

    def test_tournament_context(r):
        keywords = ["Masters", "London", "Swiss", "tournament"]
        found = [k for k in keywords if k in narrative]
        r.pass_test(f"Tournament context present: {found}") if len(found) >= 2 else r.fail_test(f"Missing tournament context — only found: {found}")

    def test_player_analysis_content(r):
        player_analysis = cached.get("player_analysis", "")
        val_terms = ["agent", "team", "round", "FUT", "FULL SENSE", "winning", "tactical"]
        found = [t for t in val_terms if t.lower() in player_analysis.lower()]
        if len(found) >= 3:
            r.pass_test(f"Valorant player analysis has team content: {found}")
        else:
            r.fail_test(f"Valorant player analysis missing content — only found: {found}")

    suite.run("Required Fields Present", test_required_fields)
    suite.run("Narrative Length (250+ words)", test_narrative_length)
    suite.run("No Em Dashes", test_no_em_dashes)
    suite.run("Team Names Present", test_team_names_present)
    suite.run("Player IGNs Present in Narrative", test_player_igns_present)
    suite.run("Tournament Context Present", test_tournament_context)
    suite.run("Player Analysis Has Sport-Specific Content", test_player_analysis_content)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — MLB CACHE QUALITY
# ─────────────────────────────────────────────

def run_mlb_quality_tests():
    suite = TestSuite("MLB QUALITY")
    print(f"\n{'=' * 60}")
    print("TIER 1 — MLB CACHE QUALITY TESTS")
    print('=' * 60)

    from utils.cache import load_from_cache
    cached = load_from_cache("824916", "mlb")

    if not cached:
        print("  [-] MLB cache not found — skipping all MLB quality tests")
        return True

    narrative = cached.get("narrative", "")
    raw = cached.get("raw_match_data", {})

    def test_required_fields(r):
        required = ["match_analysis", "narrative", "raw_match_data"]
        missing = [f for f in required if not cached.get(f)]
        r.pass_test("All required fields present") if not missing else r.fail_test(f"Missing: {missing}")

    def test_narrative_length(r):
        words = len(narrative.split())
        r.pass_test(f"{words} words") if words >= 300 else r.fail_test(f"Too short: {words} words")

    def test_no_em_dashes(r):
        if " — " in narrative or " – " in narrative:
            r.fail_test("Em dashes found")
        else:
            r.pass_test("No em dashes found")

    def test_team_names_present(r):
        teams = ["Pittsburgh", "Atlanta"]
        found = [t for t in teams if t in narrative]
        r.pass_test(f"Team names present: {found}") if len(found) == 2 else r.fail_test(f"Missing teams: {[t for t in teams if t not in narrative]}")

    def test_pitcher_named(r):
        pitchers = ["Chandler", "Elder", "Horwitz"]
        found = [p for p in pitchers if p in narrative]
        r.pass_test(f"Key players named: {found}") if len(found) >= 2 else r.fail_test(f"Too few players — only found: {found}")

    def test_linescore_referenced(r):
        # Narrative should reference specific innings
        inning_terms = ["seventh", "inning", "6th", "7th", "sixth"]
        found = [t for t in inning_terms if t.lower() in narrative.lower()]
        r.pass_test(f"Linescore context present: {found}") if found else r.fail_test("No inning references found in narrative")

    def test_mlb_terminology(r):
        terms = ["pitch", "strikeout", "inning", "bullpen", "run"]
        found = [t for t in terms if t.lower() in narrative.lower()]
        r.pass_test(f"MLB terminology present: {found}") if len(found) >= 3 else r.fail_test(f"Missing MLB terms — only found: {found}")

    def test_player_analysis_content(r):
        player_analysis = cached.get("player_analysis", "")
        # MLB player analysis should contain pitching and batting content
        pitching_terms = ["IP", "strikeout", "pitch", "inning", "ERA", "ER", "K"]
        batting_terms = ["hit", "RBI", "batting", "homer", "run"]
        found_pitching = [t for t in pitching_terms if t.lower() in player_analysis.lower()]
        found_batting = [t for t in batting_terms if t.lower() in player_analysis.lower()]
        if len(found_pitching) >= 2 and len(found_batting) >= 1:
            r.pass_test(f"MLB player analysis has pitching and batting content")
        else:
            r.fail_test(f"MLB player analysis missing content — pitching: {found_pitching}, batting: {found_batting}")

    def test_top_performers_have_names(r):
        top = raw.get("top_performers", [])
        if not top:
            r.skip_test("No top performers in cache")
            return
        named = [p for p in top if p.get("name") and p["name"] != "Unknown"]
        r.pass_test(f"{len(named)}/{len(top)} top performers have names") if named else r.fail_test("No named top performers")

    suite.run("Required Fields Present", test_required_fields)
    suite.run("Narrative Length (300+ words)", test_narrative_length)
    suite.run("No Em Dashes", test_no_em_dashes)
    suite.run("Team Names Present", test_team_names_present)
    suite.run("Key Players Named", test_pitcher_named)
    suite.run("Linescore Referenced in Narrative", test_linescore_referenced)
    suite.run("MLB Terminology Present", test_mlb_terminology)
    suite.run("Player Analysis Has Sport-Specific Content", test_player_analysis_content)
    suite.run("Top Performers Have Names", test_top_performers_have_names)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 1 — ERROR HANDLING
# ─────────────────────────────────────────────

def run_error_handling_tests():
    suite = TestSuite("ERROR HANDLING")
    print(f"\n{'=' * 60}")
    print("TIER 1 — ERROR HANDLING TESTS")
    print('=' * 60)

    from graph import run_analysis
    from utils.cache import cache_exists

    def test_invalid_nba_team(r):
        result = run_analysis("nba", "InvalidTeamXYZ123", force_refresh=True)
        r.pass_test(f"Handled gracefully: {result['error'][:50]}") if result.get("error") else r.fail_test("Expected error not returned")

    def test_invalid_sport(r):
        result = run_analysis("cricket", "latest", force_refresh=True)
        r.pass_test("Invalid sport handled gracefully") if result.get("error") else r.skip_test("No error returned — defaulted gracefully")

    def test_empty_match_id(r):
        result = run_analysis("nba", "", force_refresh=True)
        r.pass_test("Empty match_id returns error") if result.get("error") else r.fail_test("Empty match_id should return error")

    def test_failed_not_cached(r):
        result = run_analysis("nba", "InvalidTeamXYZ123", force_refresh=True)
        if result.get("error"):
            game_id = result.get("match_id", "InvalidTeamXYZ123")
            r.pass_test("Failed analysis not cached") if not cache_exists(game_id, "nba") else r.fail_test("Failed analysis should not be cached")

    suite.run("Invalid NBA Team Name", test_invalid_nba_team)
    suite.run("Invalid Sport", test_invalid_sport)
    suite.run("Empty Match ID Returns Error", test_empty_match_id)
    suite.run("Failed Analysis Not Cached", test_failed_not_cached)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 2 — API CONNECTIVITY
# ─────────────────────────────────────────────

def run_api_tests():
    suite = TestSuite("API CONNECTIVITY")
    print(f"\n{'=' * 60}")
    print("TIER 2 — API CONNECTIVITY TESTS")
    print('=' * 60)

    import requests

    def test_nba_api(r):
        try:
            from nba_api.stats.static import teams
            all_teams = teams.get_teams()
            r.pass_test(f"NBA API working — {len(all_teams)} teams loaded") if all_teams else r.fail_test("No teams returned")
        except Exception as e:
            r.fail_test(f"NBA API failed: {e}")

    def test_f1_api(r):
        try:
            response = requests.get("https://api.jolpi.ca/ergast/f1/current/last/results.json", timeout=30)
            if response.status_code == 200:
                races = response.json()["MRData"]["RaceTable"]["Races"]
                r.pass_test(f"F1 API working — latest race: {races[0]['raceName']}") if races else r.fail_test("No races returned")
            else:
                r.fail_test(f"Status: {response.status_code}")
        except Exception as e:
            r.skip_test(f"Jolpica unreachable — not a blocker (has retry logic)")

    def test_bsd_api(r):
        try:
            key = os.getenv("BSD_API_KEY")
            response = requests.get(
                "https://sports.bzzoiro.com/api/v2/events/",
                headers={"Authorization": f"Token {key}"},
                params={"status": "finished", "limit": 1},
                timeout=15
            )
            if response.status_code == 200:
                r.pass_test(f"BSD API working — {response.json().get('count', 0)} matches available")
            else:
                r.fail_test(f"Status: {response.status_code}")
        except Exception as e:
            r.fail_test(f"BSD API failed: {e}")

    def test_vlr_api(r):
        try:
            response = requests.get("https://vlr.orlandomm.net/api/v1/results", params={"page": 1}, timeout=15)
            if response.status_code == 200:
                count = len(response.json().get("data", []))
                r.pass_test(f"VLR API working — {count} recent matches")
            else:
                r.fail_test(f"Status: {response.status_code}")
        except Exception as e:
            r.skip_test(f"VLR API unreachable — not a blocker")

    def test_mlb_api(r):
        try:
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            response = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule",
                params={"sportId": 1, "date": today},
                timeout=15
            )
            if response.status_code == 200:
                dates = response.json().get("dates", [])
                count = len(dates[0].get("games", [])) if dates else 0
                r.pass_test(f"MLB API working — {count} games today")
            else:
                r.fail_test(f"Status: {response.status_code}")
        except Exception as e:
            r.fail_test(f"MLB API failed: {e}")

    def test_anthropic_api(r):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=10, messages=[{"role": "user", "content": "Say OK"}])
            r.pass_test("Anthropic API responding") if msg.content else r.fail_test("Empty response")
        except Exception as e:
            r.fail_test(f"Anthropic API failed: {e}")

    def test_openai_api(r):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp = client.chat.completions.create(model="gpt-4o-mini", max_tokens=10, messages=[{"role": "user", "content": "Say OK"}])
            r.pass_test("OpenAI API responding") if resp.choices else r.fail_test("Empty response")
        except Exception as e:
            r.fail_test(f"OpenAI API failed: {e}")

    suite.run("NBA Stats API", test_nba_api)
    suite.run("F1 Jolpica API", test_f1_api)
    suite.run("BSD Soccer API", test_bsd_api)
    suite.run("VLR Esports API", test_vlr_api)
    suite.run("MLB Stats API", test_mlb_api)
    suite.run("Anthropic Claude API", test_anthropic_api)
    suite.run("OpenAI GPT API", test_openai_api)
    return suite.summary()


# ─────────────────────────────────────────────
# TIER 2 — LIVE PIPELINE TESTS
# ─────────────────────────────────────────────

def run_live_pipeline_tests():
    suite = TestSuite("LIVE PIPELINES")
    print(f"\n{'=' * 60}")
    print("TIER 2 — LIVE PIPELINE TESTS")
    print("WARNING: This will cost approximately $0.42")
    print('=' * 60)

    from graph import run_analysis
    from utils.cost_tracker import reset_session_cost, get_session_cost

    reset_session_cost()

    def test_nba_live(r):
        result = run_analysis("nba", "Knicks", force_refresh=True)
        if result.get("error"):
            r.fail_test(f"Pipeline failed: {result['error'][:60]}")
        elif result.get("narrative") and len(result["narrative"].split()) >= 200:
            cost = get_session_cost()
            r.pass_test(f"NBA pipeline working — {len(result['narrative'].split())} word narrative — ${cost:.4f}")
        else:
            r.fail_test("Narrative missing or too short")

    def test_f1_live(r):
        result = run_analysis("f1", "latest", force_refresh=True)
        if result.get("error"):
            r.fail_test(f"Pipeline failed: {result['error'][:60]}")
        elif result.get("narrative") and len(result["narrative"].split()) >= 200:
            r.pass_test(f"F1 pipeline working — {len(result['narrative'].split())} word narrative")
        else:
            r.fail_test("Narrative missing or too short")

    def test_soccer_live(r):
        result = run_analysis("soccer", "premier_league", force_refresh=True)
        if result.get("error"):
            r.fail_test(f"Pipeline failed: {result['error'][:60]}")
        elif result.get("narrative") and len(result["narrative"].split()) >= 150:
            r.pass_test(f"Soccer pipeline working — {len(result['narrative'].split())} word narrative")
        else:
            r.fail_test("Narrative missing or too short")

    def test_valorant_live(r):
        result = run_analysis("valorant", "latest", force_refresh=True)
        if result.get("error"):
            r.fail_test(f"Pipeline failed: {result['error'][:60]}")
        elif result.get("narrative") and len(result["narrative"].split()) >= 200:
            r.pass_test(f"Valorant pipeline working — {len(result['narrative'].split())} word narrative")
        else:
            r.fail_test("Narrative missing or too short")

    def test_mlb_live(r):
        result = run_analysis("mlb", "latest", force_refresh=True)
        if result.get("error"):
            r.fail_test(f"Pipeline failed: {result['error'][:60]}")
        elif result.get("narrative") and len(result["narrative"].split()) >= 200:
            # Verify bug fix — top performers should have team names now
            raw = result.get("raw_match_data", {})
            top = raw.get("top_performers", [])
            named_teams = [p for p in top if p.get("team")]
            if named_teams:
                r.pass_test(f"MLB pipeline working — top performers have team names: {[p['team'] for p in named_teams]}")
            else:
                r.fail_test("MLB top performers still missing team names — Bug 2 not fixed")
        else:
            r.fail_test("Narrative missing or too short")

    def test_enrichment_nba_only(r):
        # Verify enrichment only runs for NBA
        result_nba = run_analysis("nba", "Lakers", force_refresh=True)
        result_mlb = run_analysis("mlb", "latest", force_refresh=True)

        nba_pa = result_nba.get("player_analysis", "")
        mlb_pa = result_mlb.get("player_analysis", "")

        nba_has_structure = "PLAYER:" in nba_pa and "RATING:" in nba_pa
        mlb_has_structure = "PLAYER:" in mlb_pa and "RATING:" in mlb_pa

        if nba_has_structure and not mlb_has_structure:
            r.pass_test("Enrichment runs for NBA, correctly skipped for MLB")
        elif not nba_has_structure:
            r.fail_test("NBA enrichment not running — Bug 1 still present")
        else:
            r.fail_test("MLB incorrectly has NBA-style player structure")

    def test_total_cost(r):
        total = get_session_cost()
        if total <= 0.60:
            r.pass_test(f"Total live pipeline cost: ${total:.4f} (within budget)")
        else:
            r.fail_test(f"Cost too high: ${total:.4f} (expected under $0.60)")

    suite.run("NBA Live Pipeline", test_nba_live)
    suite.run("F1 Live Pipeline", test_f1_live)
    suite.run("Soccer Live Pipeline", test_soccer_live)
    suite.run("Valorant Live Pipeline", test_valorant_live)
    suite.run("MLB Live Pipeline + Bug 2 Verify", test_mlb_live)
    suite.run("Enrichment NBA-Only Verify (Bug 1)", test_enrichment_nba_only)
    suite.run("Total Cost Within Budget", test_total_cost)
    return suite.summary()


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SPORTSCAST AI — TWO-TIER PRODUCTION EVALUATION SUITE")
    if RUN_LIVE:
        print("MODE: TIER 1 (Cache) + TIER 2 (Live) — estimated cost $0.42")
    else:
        print("MODE: TIER 1 ONLY (Cache Quality) — cost $0.00")
        print("Run with --live flag to include live pipeline tests")
    print("=" * 60)

    results = []

    # ── TIER 1 (always runs) ──
    results.append(("Environment", run_environment_tests()))
    results.append(("Cache System", run_cache_tests()))
    results.append(("Intent Classifier", run_intent_tests()))
    results.append(("NBA Quality", run_nba_quality_tests()))
    results.append(("F1 Quality", run_f1_quality_tests()))
    results.append(("Soccer Quality", run_soccer_quality_tests()))
    results.append(("Valorant Quality", run_valorant_quality_tests()))
    results.append(("MLB Quality", run_mlb_quality_tests()))
    results.append(("Error Handling", run_error_handling_tests()))

    # ── TIER 2 (only with --live flag) ──
    if RUN_LIVE:
        results.append(("API Connectivity", run_api_tests()))
        results.append(("Live Pipelines", run_live_pipeline_tests()))

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for suite_name, passed in results:
        icon = "+" if passed else "x"
        status = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {suite_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("SYSTEM STATUS: PRODUCTION READY")
    else:
        print("SYSTEM STATUS: ISSUES FOUND — SEE ABOVE")
    print("=" * 60)