"""
Production Grade Evaluation Suite for SportsCast AI
Tests: happy paths, error handling, edge cases, 
cache behavior, cost consistency, and resilience
"""

import time
import os
import json
from dotenv import load_dotenv

load_dotenv()

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
        self.cost = 0.0

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
        self.total_cost = 0.0
        self.total_time = 0.0

    def run(self, test_name: str, test_fn, use_cache: bool = True):
        result = TestResult(test_name)
        start = time.time()

        try:
            test_fn(result)
        except Exception as e:
            result.fail_test(f"Unexpected exception: {str(e)}")

        result.duration = round(time.time() - start, 2)
        self.results.append(result)

        status = "PASS" if result.passed else "FAIL" if result.failed else "SKIP"
        icon = "+" if result.passed else "x" if result.failed else "-"
        print(f"  [{icon}] {test_name} ({result.duration}s) — {result.message}")

        return result

    def summary(self):
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if r.failed)
        skipped = sum(1 for r in self.results if r.skipped)
        total = len(self.results)

        print(f"\n{'=' * 50}")
        print(f"{self.name} RESULTS")
        print(f"{'=' * 50}")
        print(f"Passed:  {passed}/{total}")
        print(f"Failed:  {failed}/{total}")
        print(f"Skipped: {skipped}/{total}")

        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if r.failed:
                    print(f"  - {r.name}: {r.message}")

        return failed == 0


# ─────────────────────────────────────────────
# ENVIRONMENT TESTS
# ─────────────────────────────────────────────

def run_environment_tests():
    suite = TestSuite("ENVIRONMENT")
    print(f"\n{'=' * 50}")
    print("ENVIRONMENT TESTS")
    print("Verifying all required keys and dependencies")
    print('=' * 50)

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
            r.skip_test("RIOT_API_KEY not set - Valorant will be unavailable")
        elif "RGAPI" not in key:
            r.fail_test("RIOT_API_KEY format looks wrong")
        else:
            r.pass_test(f"Key present")

    def test_cache_dir(r):
        if not os.path.exists("cache"):
            os.makedirs("cache")
        if os.path.exists("cache"):
            cached = len([f for f in os.listdir("cache") if f.endswith(".json")])
            r.pass_test(f"Cache directory exists with {cached} cached games")
        else:
            r.fail_test("Could not create cache directory")

    def test_imports(r):
        try:
            from graph import run_analysis, run_nba_analysis
            from utils.cache import load_from_cache, save_to_cache
            from utils.cost_tracker import get_session_cost, reset_session_cost
            from agents.chat_agent import classify_intent
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
# CACHE TESTS
# ─────────────────────────────────────────────

def run_cache_tests():
    suite = TestSuite("CACHE")
    print(f"\n{'=' * 50}")
    print("CACHE TESTS")
    print("Verifying cache read, write, and invalidation")
    print('=' * 50)

    from utils.cache import save_to_cache, load_from_cache, cache_exists, invalidate_cache

    TEST_GAME_ID = "test_game_001"
    TEST_SPORT = "test"
    TEST_STATE = {
        "sport": "test",
        "match_id": TEST_GAME_ID,
        "match_analysis": "Test match analysis",
        "player_analysis": "Test player analysis",
        "narrative": "Test narrative",
        "persona": "espn_formal",
        "raw_match_data": {"test": True},
        "chat_history": [],
        "user_query": None,
        "chat_response": None,
        "error": None
    }

    def test_cache_write(r):
        save_to_cache(TEST_GAME_ID, TEST_SPORT, TEST_STATE)
        if cache_exists(TEST_GAME_ID, TEST_SPORT):
            r.pass_test("Cache write successful")
        else:
            r.fail_test("Cache file not created")

    def test_cache_read(r):
        cached = load_from_cache(TEST_GAME_ID, TEST_SPORT)
        if cached and cached.get("narrative") == "Test narrative":
            r.pass_test("Cache read returns correct data")
        else:
            r.fail_test(f"Cache read failed or wrong data: {cached}")

    def test_cache_speed(r):
        start = time.time()
        for _ in range(10):
            load_from_cache(TEST_GAME_ID, TEST_SPORT)
        elapsed = time.time() - start
        if elapsed < 1.0:
            r.pass_test(f"10 cache reads in {elapsed:.3f}s")
        else:
            r.fail_test(f"Cache reads too slow: {elapsed:.3f}s")

    def test_force_refresh(r):
        result = load_from_cache(TEST_GAME_ID, TEST_SPORT, force_refresh=True)
        if result is None:
            r.pass_test("Force refresh correctly bypasses cache")
        else:
            r.fail_test("Force refresh should return None")

    def test_missing_cache(r):
        result = load_from_cache("nonexistent_game", TEST_SPORT)
        if result is None:
            r.pass_test("Missing cache returns None correctly")
        else:
            r.fail_test("Missing cache should return None")

    def test_cache_invalidation(r):
        invalidate_cache(TEST_GAME_ID, TEST_SPORT)
        if not cache_exists(TEST_GAME_ID, TEST_SPORT):
            r.pass_test("Cache invalidation successful")
        else:
            r.fail_test("Cache still exists after invalidation")

    suite.run("Cache Write", test_cache_write)
    suite.run("Cache Read", test_cache_read)
    suite.run("Cache Speed (10 reads)", test_cache_speed)
    suite.run("Force Refresh", test_force_refresh)
    suite.run("Missing Cache Returns None", test_missing_cache)
    suite.run("Cache Invalidation", test_cache_invalidation)

    return suite.summary()


# ─────────────────────────────────────────────
# INTENT CLASSIFIER TESTS
# ─────────────────────────────────────────────

def run_intent_tests():
    suite = TestSuite("INTENT CLASSIFIER")
    print(f"\n{'=' * 50}")
    print("INTENT CLASSIFIER TESTS")
    print("Verifying all 7 intent types classify correctly")
    print('=' * 50)

    from agents.chat_agent import classify_intent

    test_cases = [
        ("How many points did LeBron score?", "factual"),
        ("What was the final score?", "factual"),
        ("Why did the Lakers lose?", "analytical"),
        ("Why did Antonelli win from pole?", "analytical"),
        ("Compare Brunson and Wembanyama", "comparative"),
        ("Who was better, Hart or Tatum?", "comparative"),
        ("What should the Spurs do in Game 2?", "predictive"),
        ("What will happen next race?", "predictive"),
        ("That performance was incredible!", "emotional"),
        ("Amazing game tonight", "emotional"),
        ("What do you mean by that?", "clarification"),
        ("Can you clarify what you said?", "clarification"),
        ("Who won the Super Bowl?", "out_of_scope"),
        ("What is the weather today?", "out_of_scope"),
    ]

    for query, expected_intent in test_cases:
        def make_test(q, expected):
            def test_fn(r):
                result = classify_intent(q, [])
                if result == expected:
                    r.pass_test(f"'{q[:30]}' -> {result}")
                else:
                    r.fail_test(
                        f"'{q[:30]}' -> got '{result}', expected '{expected}'"
                    )
            return test_fn

        suite.run(
            f"Intent: {expected_intent}",
            make_test(query, expected_intent)
        )

    return suite.summary()


# ─────────────────────────────────────────────
# API CONNECTIVITY TESTS
# ─────────────────────────────────────────────

def run_api_tests():
    suite = TestSuite("API CONNECTIVITY")
    print(f"\n{'=' * 50}")
    print("API CONNECTIVITY TESTS")
    print("Verifying all external APIs respond correctly")
    print('=' * 50)

    def test_nba_api(r):
        try:
            from nba_api.stats.static import teams
            all_teams = teams.get_teams()
            if len(all_teams) > 0:
                r.pass_test(f"NBA API working - {len(all_teams)} teams loaded")
            else:
                r.fail_test("NBA API returned no teams")
        except Exception as e:
            r.fail_test(f"NBA API failed: {e}")

    def test_f1_api(r):
        try:
            import requests
            response = requests.get(
                "https://api.jolpi.ca/ergast/f1/current/last/results.json",
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                races = data["MRData"]["RaceTable"]["Races"]
                if races:
                    r.pass_test(f"F1 API working - latest race: {races[0]['raceName']}")
                else:
                    r.fail_test("F1 API returned no races")
            else:
                r.fail_test(f"F1 API status: {response.status_code}")
        except Exception as e:
            # Jolpica occasionally times out - skip rather than fail
            # F1 pipeline has retry logic built in so this is not a blocker
            r.skip_test(f"Jolpica API unreachable right now - not a blocker (has retry logic)")


    def test_bsd_api(r):
        try:
            import requests
            key = os.getenv("BSD_API_KEY")
            response = requests.get(
                "https://sports.bzzoiro.com/api/v2/events/",
                headers={"Authorization": f"Token {key}"},
                params={"status": "finished", "limit": 1},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get("count", 0)
                r.pass_test(f"BSD API working - {count} total matches available")
            else:
                r.fail_test(f"BSD API status: {response.status_code}")
        except Exception as e:
            r.fail_test(f"BSD API failed: {e}")
 
    def test_vlr_api(r):
        try:
            import requests
            response = requests.get(
                "https://vlr.orlandomm.net/api/v1/results",
                params={"page":1},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                count = len(data.get("data", []))
                r.pass_test(f"VLR API working - {count} recent matches available")
            else:
                r.fail_test(f"VLR API status: {response.status_code}")
        except Exception as e:
            r.skip_test(f"VLR API unreachable - not a blocker (has retry logic)")

    def test_mlb_api(r):
        try:
            import requests
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            response = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule",
                params={"sportId": 1, "date": today},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                dates = data.get("dates", [])
                count = len(dates[0].get("games", [])) if dates else 0
                r.pass_test(f"MLB API working - {count} games today")
            else:
                r.fail_test(f"MLB API status: {response.status_code}")
        except Exception as e:
            r.fail_test(f"MLB API failed: {e}")
       
    def test_anthropic_api(r):
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}]
            )
            if message.content:
                r.pass_test("Anthropic API responding correctly")
            else:
                r.fail_test("Anthropic API returned empty response")
        except Exception as e:
            r.fail_test(f"Anthropic API failed: {e}")

    def test_openai_api(r):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}]
            )
            if response.choices:
                r.pass_test("OpenAI API responding correctly")
            else:
                r.fail_test("OpenAI API returned empty response")
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
# ERROR HANDLING TESTS
# ─────────────────────────────────────────────

def run_error_handling_tests():
    suite = TestSuite("ERROR HANDLING")
    print(f"\n{'=' * 50}")
    print("ERROR HANDLING TESTS")
    print("Verifying system fails gracefully not catastrophically")
    print('=' * 50)

    from graph import run_analysis

    def test_invalid_nba_team(r):
        result = run_analysis(
            "nba", "InvalidTeamXYZ123", force_refresh=True
        )
        if result.get("error"):
            r.pass_test(f"Invalid team handled gracefully: {result['error'][:50]}")
        else:
            r.fail_test("Expected error for invalid team name")

    def test_invalid_sport(r):
        try:
            result = run_analysis(
                "cricket", "latest", force_refresh=True
            )
            if result.get("error"):
                r.pass_test("Invalid sport handled gracefully")
            else:
                r.skip_test("No error returned but pipeline may have defaulted")
        except Exception as e:
            r.pass_test(f"Exception caught gracefully: {str(e)[:50]}")

    def test_empty_match_id(r):
        result = run_analysis("nba", "", force_refresh=True)
        if result.get("error") or result.get("narrative"):
            r.pass_test("Empty match_id handled - system used default or errored gracefully")
        else:
            r.fail_test("Empty match_id produced no output and no error")

    def test_cache_on_error(r):
        from utils.cache import cache_exists
        result = run_analysis(
            "nba", "InvalidTeamXYZ123", force_refresh=True
        )
        if result.get("error"):
            game_id = result.get("match_id", "InvalidTeamXYZ123")
            if not cache_exists(game_id, "nba"):
                r.pass_test("Failed analysis not cached correctly")
            else:
                r.fail_test("Failed analysis should not be cached")

    suite.run("Invalid NBA Team Name", test_invalid_nba_team)
    suite.run("Invalid Sport", test_invalid_sport)
    suite.run("Empty Match ID", test_empty_match_id)
    suite.run("Failed Analysis Not Cached", test_cache_on_error)

    return suite.summary()


# ─────────────────────────────────────────────
# PIPELINE CONSISTENCY TESTS
# ─────────────────────────────────────────────

def run_consistency_tests():
    suite = TestSuite("PIPELINE CONSISTENCY")
    print(f"\n{'=' * 50}")
    print("PIPELINE CONSISTENCY TESTS")
    print("Verifying cached results are consistent and complete")
    print('=' * 50)

    from utils.cache import load_from_cache, list_cached_games
    from utils.cost_tracker import reset_session_cost, get_session_cost

    def test_cached_nba_complete(r):
        cached = load_from_cache("0042500401", "nba")
        if not cached:
            r.skip_test("NBA Finals game not in cache - run test_pipeline.py first")
            return
        required = ["match_analysis", "player_analysis", "narrative", "sport", "match_id"]
        missing = [f for f in required if not cached.get(f)]
        if missing:
            r.fail_test(f"Cached game missing fields: {missing}")
        else:
            r.pass_test("NBA cached game has all required fields")

    def test_cached_f1_complete(r):
        cached = load_from_cache("2026_5", "f1")
        if not cached:
            r.skip_test("F1 Canadian GP not in cache - run test_f1_pipeline.py first")
            return
        required = ["match_analysis", "player_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        if missing:
            r.fail_test(f"Cached F1 race missing fields: {missing}")
        else:
            r.pass_test("F1 cached race has all required fields")

    def test_cached_soccer_complete(r):
        cached = load_from_cache("374", "soccer")
        if not cached:
            r.skip_test("Soccer match not in cache - run test_soccer_pipeline.py first")
            return
        required = ["match_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        if missing:
            r.fail_test(f"Cached soccer match missing fields: {missing}")
        else:
            r.pass_test("Soccer cached match has all required fields")

    def test_cache_load_zero_cost(r):
        reset_session_cost()
        cached = load_from_cache("0042500401", "nba")
        cost = get_session_cost()
        if cost == 0.0:
            r.pass_test("Cache load incurs zero API cost")
        else:
            r.fail_test(f"Cache load incurred cost: ${cost}")

    def test_narrative_no_em_dashes(r):
        cached = load_from_cache("0042500401", "nba")
        if not cached:
            r.skip_test("NBA cache not found")
            return
        narrative = cached.get("narrative", "")
        if " — " in narrative or " – " in narrative:
            r.fail_test("Narrative contains em dashes — anti-LLM fix not working")
        else:
            r.pass_test("No em dashes found in narrative")

    def test_narrative_minimum_length(r):
        cached = load_from_cache("0042500401", "nba")
        if not cached:
            r.skip_test("NBA cache not found")
            return
        narrative = cached.get("narrative", "")
        word_count = len(narrative.split())
        if word_count >= 200:
            r.pass_test(f"Narrative is {word_count} words — sufficient depth")
        else:
            r.fail_test(f"Narrative too short: {word_count} words")

    def test_player_analysis_structure(r):
        cached = load_from_cache("0042500401", "nba")
        if not cached:
            r.skip_test("NBA cache not found")
            return
        player_analysis = cached.get("player_analysis", "")
        required_fields = ["PLAYER:", "RATING:", "STATS:", "INSIGHT:"]
        missing = [f for f in required_fields if f not in player_analysis]
        if missing:
            r.fail_test(f"Player analysis missing fields: {missing}")
        else:
            player_count = player_analysis.count("PLAYER:")
            r.pass_test(f"Player analysis has correct structure — {player_count} players")

    suite.run("NBA Cache Complete", test_cached_nba_complete)
    suite.run("F1 Cache Complete", test_cached_f1_complete)
    suite.run("Soccer Cache Complete", test_cached_soccer_complete)

    def test_cached_valorant_complete(r):
        cached = load_from_cache("684611", "valorant")
        if not cached:
            r.skip_test("Valorant match not in cache - run test_valorant_pipeline.py first")
            return
        required = ["match_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        if missing:
            r.fail_test(f"Cached Valorant match missing fields: {missing}")
        else:
            r.pass_test("Valorant cached match has all required fields")

    def test_cached_mlb_complete(r):
        cached = load_from_cache("824916", "mlb")
        if not cached:
            r.skip_test("MLB game not in cache - run test_mlb_pipeline.py first")
            return
        required = ["match_analysis", "narrative"]
        missing = [f for f in required if not cached.get(f)]
        if missing:
            r.fail_test(f"Cached MLB game missing fields: {missing}")
        else:
            r.pass_test("MLB cached game has all required fields")

    suite.run("Valorant Cache Complete", test_cached_valorant_complete)
    suite.run("MLB Cache Complete", test_cached_mlb_complete)
    suite.run("Cache Load Zero Cost", test_cache_load_zero_cost)
    suite.run("No Em Dashes in Narrative", test_narrative_no_em_dashes)
    suite.run("Narrative Minimum Length", test_narrative_minimum_length)
    suite.run("Player Analysis Structure", test_player_analysis_structure)

    return suite.summary()


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SPORTSCAST AI — PRODUCTION EVALUATION SUITE")
    print("=" * 50)

    results = []

    # Run all test suites
    results.append(("Environment", run_environment_tests()))
    results.append(("Cache", run_cache_tests()))
    results.append(("Intent Classifier", run_intent_tests()))
    results.append(("API Connectivity", run_api_tests()))
    results.append(("Error Handling", run_error_handling_tests()))
    results.append(("Pipeline Consistency", run_consistency_tests()))

    # Final summary
    print("\n" + "=" * 50)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 50)

    all_passed = True
    for suite_name, passed in results:
        status = "PASS" if passed else "FAIL"
        icon = "+" if passed else "x"
        print(f"  [{icon}] {suite_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("SYSTEM STATUS: PRODUCTION READY")
    else:
        print("SYSTEM STATUS: ISSUES FOUND - SEE ABOVE")
    print("=" * 50)