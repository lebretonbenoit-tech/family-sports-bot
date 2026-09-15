"""
Bot Telegram multi-sports — canal privé "toi + ton fils"
Sports couverts : NBA (Miami Heat), NFL (Denver Broncos),
Football (FC Barcelone, OM, Bayern, Man United, Équipe de France),
F1 (Red Bull, Alpine, Leclerc, Hamilton, Verstappen)

Architecture 0€ : ESPN API (NBA/NFL/Foot) + Jolpica API (F1, remplaçante gratuite d'Ergast)
Pensé pour tourner toutes les 10-15 min via GitHub Actions (cron), comme DUNKR LIVE.

Variables d'environnement nécessaires :
  TELEGRAM_BOT_TOKEN -> token du bot (via @BotFather)
  TELEGRAM_CHAT_ID -> id du canal privé (ex: -1001234567890)
"""

import os
import json
import requests

STATE_FILE = "state.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CONFIG = {
    "nba_team": "Miami Heat",
    "nfl_team": "Denver Broncos",
    "football_clubs": {
        "esp.1": ["Barcelona"],
        "fra.1": ["Marseille"],
        "ger.1": ["Bayern Munich"],
        "eng.1": ["Manchester United"],
        "uefa.champions": ["Barcelona", "Bayern Munich", "Manchester United", "Marseille"],
    },
    "national_team": "France",
    "f1_teams": ["Red Bull", "Alpine"],
    "f1_drivers": ["Leclerc", "Hamilton", "Verstappen"],
}

FOOTBALL_LEAGUES = {
    "esp.1": {"name": "Liga", "flag": "🇪🇸"},
    "fra.1": {"name": "Ligue 1", "flag": "🇫🇷"},
    "ger.1": {"name": "Bundesliga", "flag": "🇩🇪"},
    "eng.1": {"name": "Premier League", "flag": "🇬🇧"},
    "uefa.champions": {"name": "Champions League", "flag": "🇪🇺"},
}

CLUB_WIN_EMOJI = {
    "Manchester United": "😈",
    "Barcelona": "🔵🔴",
    "Marseille": "🐟",
    "Bayern Munich": "🍺",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"nba": [], "nfl": [], "football": [], "f1": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant — message non envoyé :")
        print(text)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=15)
    if not r.ok:
        print(f"[!] Erreur envoi Telegram : {r.status_code} {r.text}")


def check_nba(state):
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    data = requests.get(url, timeout=15).json()

    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if CONFIG["nba_team"] not in teams:
            continue
        if event["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        game_id = event["id"]
        if game_id in state["nba"]:
            continue

        heat = next(c for c in competitors if c["team"]["displayName"] == CONFIG["nba_team"])
        opp = next(c for c in competitors if c["team"]["displayName"] != CONFIG["nba_team"])
        heat_score, opp_score = int(heat["score"]), int(opp["score"])
        result = "Victoire 🔥" if heat_score > opp_score else "Défaite 🙈"

        leaders = heat.get("leaders", [])
        top_scorer_line = ""
        if leaders:
            pts_leader = leaders[0]["leaders"][0]
            top_scorer_line = f"\n🏀 Top marqueur Miami : {pts_leader['athlete']['displayName']} — {pts_leader['displayValue']}"

        heat_record = heat.get("records", [{}])[0].get("summary", "N/A")

        msg = (
            f"<b>🏀 NBA • {result}</b>\n"
            f"{CONFIG['nba_team']} {heat_score} - {opp_score} {opp['team']['displayName']}"
            f"{top_scorer_line}\n"
            f"📊 Bilan Miami : {heat_record}"
        )
        send_message(msg)
        state["nba"].append(game_id)


def check_nfl(state):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    data = requests.get(url, timeout=15).json()

    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if CONFIG["nfl_team"] not in teams:
            continue
        if event["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        game_id = event["id"]
        if game_id in state["nfl"]:
            continue

        broncos = next(c for c in competitors if c["team"]["displayName"] == CONFIG["nfl_team"])
        opp = next(c for c in competitors if c["team"]["displayName"] != CONFIG["nfl_team"])
        b_score, o_score = int(broncos["score"]), int(opp["score"])
        result = "Victoire 🐴" if b_score > o_score else "Défaite 🙈"

        leaders = broncos.get("leaders", [])
        top_player_line = ""
        if leaders:
            leader = leaders[0]["leaders"][0]
            top_player_line = f"\n🏈 Meilleur joueur Denver : {leader['athlete']['displayName']} — {leader['displayValue']}"

        broncos_record = broncos.get("records", [{}])[0].get("summary", "N/A")

        msg = (
            f"<b>🏈 NFL • {result}</b>\n"
            f"{CONFIG['nfl_team']} {b_score} - {o_score} {opp['team']['displayName']}"
            f"{top_player_line}\n"
            f"📊 Bilan Denver : {broncos_record}"
        )
        send_message(msg)
        state["nfl"].append(game_id)


def check_football(state):
    for league, clubs in CONFIG["football_clubs"].items():
        meta = FOOTBALL_LEAGUES.get(league, {"name": league, "flag": ""})
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
        data = requests.get(url, timeout=15).json()

        for event in data.get("events", []):
            competitors = event["competitions"][0]["competitors"]
            names = [c["team"]["displayName"] for c in competitors]
            if not any(club in names for club in clubs):
                continue
            if event["status"]["type"]["name"] != "STATUS_FULL_TIME":
                continue
            game_id = event["id"]
            if game_id in state["football"]:
                continue

            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")

            followed = next(c for c in competitors if c["team"]["displayName"] in clubs)
            other = home if followed is away else away
            f_score, o_score = int(followed["score"]), int(other["score"])
            if f_score > o_score:
                win_emoji = CLUB_WIN_EMOJI.get(followed["team"]["displayName"], "😁")
                result_text = f"Victoire {win_emoji}"
            elif f_score < o_score:
                result_text = "Défaite 🙈"
            else:
                result_text = "Nul"

            title = f"⚽ {meta['flag']} {meta['name']} • {result_text}"

            msg = (
                f"<b>{title}</b>\n"
                f"{home['team']['displayName']} {home['score']} - {away['score']} {away['team']['displayName']}"
            )
            send_message(msg)
            state["football"].append(game_id)


def check_f1(state):
    base = "https://api.jolpi.ca/ergast/f1"
    last_race = requests.get(f"{base}/current/last/results.json", timeout=15).json()

    try:
        race = last_race["MRData"]["RaceTable"]["Races"][0]
    except (KeyError, IndexError):
        return

    race_id = f"{race['season']}_{race['round']}"
    if race_id in state["f1"]:
        return

    results = race["Results"]
    lines = [f"<b>🏎️ F1 • {race['raceName']} ({race['season']})</b>"]

    watched_drivers = [r for r in results if r["Driver"]["familyName"] in CONFIG["f1_drivers"]]
    watched_teams_results = [r for r in results if r["Constructor"]["name"] in CONFIG["f1_teams"]]

    for r in watched_drivers:
        lines.append(f"🏁 {r['Driver']['familyName']} ({r['Constructor']['name']}) : P{r['position']}")

    if watched_teams_results:
        best_by_team = {}
        for r in watched_teams_results:
            team = r["Constructor"]["name"]
            if team not in best_by_team or int(r["position"]) < int(best_by_team[team]["position"]):
                best_by_team[team] = r
        for team, r in best_by_team.items():
            lines.append(f"🔧 Meilleure place {team} : P{r['position']} ({r['Driver']['familyName']})")

    standings = requests.get(f"{base}/current/driverStandings.json", timeout=15).json()
    try:
        driver_standings = standings["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        lines.append("\n📊 Classement pilotes (top des suivis) :")
        for d in driver_standings:
            if d["Driver"]["familyName"] in CONFIG["f1_drivers"]:
                lines.append(f" {d['position']}. {d['Driver']['familyName']} — {d['points']} pts")
    except (KeyError, IndexError):
        pass

    send_message("\n".join(lines))
    state["f1"].append(race_id)


def main():
    state = load_state()
    for check in (check_nba, check_nfl, check_football, check_f1):
        try:
            check(state)
        except Exception as e:
            print(f"[!] Erreur dans {check.__name__} : {e}")
    save_state(state)


if __name__ == "__main__":
    main()

