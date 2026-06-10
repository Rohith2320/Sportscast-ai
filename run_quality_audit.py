from utils.cache import list_cached_games, load_from_cache
import re

print('=== NARRATIVE QUALITY AUDIT ===')
banned = ['notably', 'crucially', 'underscore', 'delve', 'encapsulate']
em_dashes = [' — ', ' – ']

games = list_cached_games()
all_pass = True
for g in games:
    cached = load_from_cache(g['game_id'], g['sport'])
    if not cached:
        continue
    narrative = cached.get('narrative', '')
    words = len(narrative.split())
    found_banned = [w for w in banned if w.lower() in narrative.lower()]
    found_dashes = [d for d in em_dashes if d in narrative]
    numbers = len(re.findall(r'\b\d+\b', narrative))
    issues = []
    if words < 300:
        issues.append(f'too short ({words} words)')
    if found_banned:
        issues.append(f'banned words: {found_banned}')
    if found_dashes:
        issues.append('em dashes found')
    if numbers < 5:
        issues.append(f'few numbers ({numbers})')
    status = 'PASS' if not issues else 'FAIL'
    title = g.get('title', g['game_id'])[:40]
    print(f'[{status}] {g["sport"]:<10} {title:<40} words={words} nums={numbers}')
    if issues:
        all_pass = False
        for issue in issues:
            print(f'  ISSUE: {issue}')

print()
print('Quality audit:', 'ALL PASS' if all_pass else 'ISSUES FOUND')
