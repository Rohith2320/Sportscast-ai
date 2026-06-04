from nba_api.live.nba.endpoints import scoreboard

print("Testing NBA live scoreboard...")

games = scoreboard.ScoreBoard()
data = games.get_dict()

game_list = data["scoreboard"]["games"]

if not game_list:
    print("No games today")
    print(f"Date: {data['scoreboard']['gameDate']}")
else:
    print(f"Found {len(game_list)} games:")
    for game in game_list:
        home = game["homeTeam"]
        away = game["awayTeam"]
        status = game["gameStatusText"]
        print(f"\n{away['teamCity']} {away['teamName']} {away['score']} vs "
              f"{home['score']} {home['teamCity']} {home['teamName']}")
        print(f"Status: {status}")
        print(f"Game ID: {game['gameId']}")