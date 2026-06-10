import requests
import time

base = 'http://127.0.0.1:8000'

print('=== SPORTSCAST AI FULL USER SIMULATION ===')
print()

# 1. Health check
r = requests.get(f'{base}/health')
h = r.json()
uptime = h.get('uptime_seconds', 0)
cache_count = h.get('cache_count', 0)
print(f'1. HEALTH: {h["status"]} | uptime: {uptime:.0f}s | cache: {cache_count} games')
for api in h.get('apis', []):
    status = 'OK' if api.get('status') == 'ok' else 'FAIL'
    print(f'   [{status}] {api["name"]}: {api["status"]}')
print()

# 2. Games per sport
print('2. CACHED GAMES PER SPORT:')
for sport in ['nba', 'f1', 'soccer', 'valorant', 'mlb']:
    r = requests.get(f'{base}/games/?sport={sport}')
    games = r.json().get('games', [])
    print(f'   {sport.upper():<12} {len(games)} games')
    for g in games[:3]:
        print(f'      - {str(g.get("title", g["game_id"]))[:50]}')
print()

# 3. Discover latest for each sport
print('3. DISCOVER LATEST:')
for sport in ['nba', 'f1', 'soccer', 'valorant', 'mlb']:
    try:
        r = requests.get(f'{base}/discover/{sport}', timeout=15)
        d = r.json()
        if d.get('error'):
            print(f'   {sport.upper():<12} FAILED: {d["error"]}')
        else:
            dn = d.get('display_name', d.get('match_id', 'unknown'))
            print(f'   {sport.upper():<12} {dn}')
    except Exception as e:
        print(f'   {sport.upper():<12} ERROR: {e}')
print()

# 4. Start fresh analyses
print('4. FRESH ANALYSIS TEST:')
job_ids = {}
for sport, match_id in [('mlb', 'latest'), ('f1', 'monaco'), ('soccer', 'latest'), ('valorant', 'latest')]:
    r = requests.post(f'{base}/analyze/', json={
        'sport': sport, 'match_id': match_id, 'persona': 'espn_formal', 'force_refresh': False
    })
    data = r.json()
    job_id = data.get('job_id')
    job_ids[sport] = job_id
    cached = data.get('cached', False)
    print(f'   {sport.upper():<12} job_id: {job_id} cached={cached}')
print()
print('   Waiting 5 seconds for cached results...')
time.sleep(5)

# 5. Check job statuses
print('5. JOB STATUS CHECK:')
for sport, job_id in job_ids.items():
    if not job_id:
        continue
    r = requests.get(f'{base}/analyze/{job_id}')
    j = r.json()
    status = j.get('status')
    cost = j.get('cost', 0)
    narrative_len = len(j.get('result', {}).get('narrative', '')) if j.get('result') else 0
    print(f'   {sport.upper():<12} status={status} | cost=${cost:.4f} | narrative={narrative_len} chars')
    if status == 'failed':
        print(f'      ERROR: {j.get("error", "unknown")}')
print()

# 6. Chat test for each cached sport
print('6. CHAT AGENT TEST:')
try:
    from utils.cache import list_cached_games
    games = list_cached_games()
    tested_sports = set()
    questions = {
        'nba': 'Why did they win?',
        'f1': 'Who was the best driver?',
        'soccer': 'Who scored?',
        'valorant': 'Who carried the match?',
        'mlb': 'Who was the best pitcher?'
    }
    for game in games:
        sport = game['sport']
        if sport in tested_sports:
            continue
        tested_sports.add(sport)
        game_id = game['game_id']
        q = questions.get(sport, 'What happened in this game?')
        r = requests.post(f'{base}/chat/', json={
            'sport': sport,
            'game_id': game_id,
            'query': q,
            'chat_history': []
        })
        resp = r.json()
        if resp.get('response'):
            preview = resp['response'][:100].replace('\n', ' ')
            intent = resp.get('intent', 'unknown')
            cost_val = resp.get('cost', 0)
            print(f'   {sport.upper():<12} Q: {q}')
            print(f'               A: {preview}...')
            print(f'               intent={intent} cost=${cost_val:.4f}')
        else:
            print(f'   {sport.upper():<12} CHAT FAILED: {resp}')
except Exception as e:
    print(f'   Chat test error: {e}')
print()

# 7. TTS test
print('7. TTS TEST:')
r = requests.post(f'{base}/tts/', json={'text': 'SportsCast AI voice test.', 'voice_id': 'JBFqnCBsd6RMkjVDRZzb'})
d = r.json()
audio_len = len(d.get('audio', '') or d.get('audio_base64', ''))
fallback = d.get('fallback', True)
success = d.get('success', False)
print(f'   ElevenLabs: {"WORKING" if audio_len > 1000 else "FAILED"} | audio_length={audio_len} | fallback={fallback} | success={success}')
print()

# 8. Metrics
print('8. METRICS:')
r = requests.get(f'{base}/metrics')
m = r.json()
print(f'   total_analyses: {m.get("total_analyses", "N/A")}')
print(f'   total_cost: ${m.get("total_cost", "N/A")}')
print(f'   by_sport: {m.get("by_sport", {})}')
print()
print('=== SIMULATION COMPLETE ===')
