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
from datetime import datetime
from zoneinfo import ZoneInfo

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
    "people": [
        {"name": "Arthur", "birth_date": "11-06", "birth_year": 2011, "nameday": "11-15"},
        {"name": "Benoit", "birth_date": "06-10", "birth_year": 1983, "nameday": "07-11"},
    ],
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
    "Marseille": "⚪🔵",
    "Bayern Munich": "🔴⚪",
}

RACE_NAME_FR = {
    "Bahrain Grand Prix": "Grand Prix de Bahreïn",
    "Saudi Arabian Grand Prix": "Grand Prix d'Arabie Saoudite",
    "Australian Grand Prix": "Grand Prix d'Australie",
    "Chinese Grand Prix": "Grand Prix de Chine",
    "Japanese Grand Prix": "Grand Prix du Japon",
    "Miami Grand Prix": "Grand Prix de Miami",
    "Canadian Grand Prix": "Grand Prix du Canada",
    "Monaco Grand Prix": "Grand Prix de Monaco",
    "Spanish Grand Prix": "Grand Prix d'Espagne",
    "Austrian Grand Prix": "Grand Prix d'Autriche",
    "British Grand Prix": "Grand Prix de Grande-Bretagne",
    "Belgian Grand Prix": "Grand Prix de Belgique",
    "Hungarian Grand Prix": "Grand Prix de Hongrie",
    "Dutch Grand Prix": "Grand Prix des Pays-Bas",
    "Italian Grand Prix": "Grand Prix d'Italie",
    "Madrid Grand Prix": "Grand Prix de Madrid",
    "Azerbaijan Grand Prix": "Grand Prix d'Azerbaïdjan",
    "Singapore Grand Prix": "Grand Prix de Singapour",
    "United States Grand Prix": "Grand Prix des États-Unis",
    "Mexico City Grand Prix": "Grand Prix de Mexico",
    "São Paulo Grand Prix": "Grand Prix de São Paulo",
    "Las Vegas Grand Prix": "Grand Prix de Las Vegas",
    "Qatar Grand Prix": "Grand Prix du Qatar",
    "Abu Dhabi Grand Prix": "Grand Prix d'Abou Dabi",
}

RACE_FLAG = {
    "Bahrain Grand Prix": "🇧🇭",
    "Saudi Arabian Grand Prix": "🇸🇦",
    "Australian Grand Prix": "🇦🇺",
    "Chinese Grand Prix": "🇨🇳",
    "Japanese Grand Prix": "🇯🇵",
    "Miami Grand Prix": "🇺🇸",
    "Canadian Grand Prix": "🇨🇦",
    "Monaco Grand Prix": "🇲🇨",
    "Spanish Grand Prix": "🇪🇸",
    "Austrian Grand Prix": "🇦🇹",
    "British Grand Prix": "🇬🇧",
    "Belgian Grand Prix": "🇧🇪",
    "Hungarian Grand Prix": "🇭🇺",
    "Dutch Grand Prix": "🇳🇱",
    "Italian Grand Prix": "🇮🇹",
    "Madrid Grand Prix": "🇪🇸",
    "Azerbaijan Grand Prix": "🇦🇿",
    "Singapore Grand Prix": "🇸🇬",
    "United States Grand Prix": "🇺🇸",
    "Mexico City Grand Prix": "🇲🇽",
    "São Paulo Grand Prix": "🇧🇷",
    "Las Vegas Grand Prix": "🇺🇸",
    "Qatar Grand Prix": "🇶🇦",
    "Abu Dhabi Grand Prix": "🇦🇪",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"nba": [], "nfl": [], "football": [], "f1": [], "matchday_sent_date": "", "birthday_sent_date": ""}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant — message non envoyé :")
        print(text)
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=15)
    if not r.ok:
        print(f"[!] Erreur envoi Telegram : {r.status_code} {r.text}")
        return False
    return True


def name_matches(keyword, full_name):
    """Compare par mot-clé plutôt que par égalité stricte, car l'API peut
    renvoyer un nom complet différent de celui saisi dans CONFIG
    (ex: 'FC Barcelona' pour la clé 'Barcelona')."""
    return keyword.lower() in full_name.lower()


def check_nba(state):
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    data = requests.get(url, timeout=15).json()

    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if not any(name_matches(CONFIG["nba_team"], t) for t in teams):
            continue
        if event["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        game_id = event["id"]
        if game_id in state["nba"]:
            continue

        heat = next(c for c in competitors if name_matches(CONFIG["nba_team"], c["team"]["displayName"]))
        opp = next(c for c in competitors if not name_matches(CONFIG["nba_team"], c["team"]["displayName"]))
        heat_score, opp_score = int(heat["score"]), int(opp["score"])

        leaders = heat.get("leaders", [])
        top_scorer_line = ""
        if leaders:
            pts_leader = leaders[0]["leaders"][0]
            top_scorer_line = f"\n\n🏀 Top marqueur Miami : {pts_leader['athlete']['displayName']} — {pts_leader['displayValue']}"

        heat_record = heat.get("records", [{}])[0].get("summary", "N/A")

        msg = (
            f"<b>🏀 NBA</b>\n\n"
            f"{CONFIG['nba_team']} {heat_score} - {opp_score} {opp['team']['displayName']}"
            f"{top_scorer_line}"
            f"\n\n📊 Bilan Miami : {heat_record}"
        )
        send_message(msg)
        state["nba"].append(game_id)


def check_nfl(state):
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    data = requests.get(url, timeout=15).json()

    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if not any(name_matches(CONFIG["nfl_team"], t) for t in teams):
            continue
        if event["status"]["type"]["name"] != "STATUS_FINAL":
            continue
        game_id = event["id"]
        if game_id in state["nfl"]:
            continue

        broncos = next(c for c in competitors if name_matches(CONFIG["nfl_team"], c["team"]["displayName"]))
        opp = next(c for c in competitors if not name_matches(CONFIG["nfl_team"], c["team"]["displayName"]))
        b_score, o_score = int(broncos["score"]), int(opp["score"])

        leaders = broncos.get("leaders", [])
        top_player_line = ""
        if leaders:
            leader = leaders[0]["leaders"][0]
            top_player_line = f"\n\n🏈 Meilleur joueur Denver : {leader['athlete']['displayName']} — {leader['displayValue']}"

        broncos_record = broncos.get("records", [{}])[0].get("summary", "N/A")

        msg = (
            f"<b>🏈 NFL</b>\n\n"
            f"{CONFIG['nfl_team']} {b_score} - {o_score} {opp['team']['displayName']}"
            f"{top_player_line}"
            f"\n\n📊 Bilan Denver : {broncos_record}"
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
            if not any(name_matches(club, n) for club in clubs for n in names):
                continue
            if event["status"]["type"]["name"] != "STATUS_FULL_TIME":
                continue
            game_id = event["id"]
            if game_id in state["football"]:
                continue

            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")

            title = f"⚽ {meta['name']} {meta['flag']}"

            scorers_lines = []
            team_names_by_id = {c["team"]["id"]: c["team"]["displayName"] for c in competitors}
            details = event["competitions"][0].get("details", [])
            goals = [d for d in details if d.get("scoringPlay")]
            goals.sort(key=lambda d: d.get("clock", {}).get("value", 0))
            for goal in goals:
                minute = goal.get("clock", {}).get("displayValue", "?")
                scorer_team = team_names_by_id.get(goal.get("team", {}).get("id"), "?")
                athletes = goal.get("athletesInvolved", [])
                scorer_name = athletes[0]["displayName"] if athletes else "?"
                og = " (csc)" if goal.get("ownGoal") else ""
                scorers_lines.append(f"{minute} {scorer_name}{og} ({scorer_team})")

            scorers_block = ""
            if scorers_lines:
                scorers_block = "\n\n⚽ Buts :\n" + "\n".join(scorers_lines)

            msg = (
                f"<b>{title}</b>\n\n"
                f"{home['team']['displayName']} {home['score']} - {away['score']} {away['team']['displayName']}"
                f"{scorers_block}"
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
    race_name_fr = RACE_NAME_FR.get(race["raceName"], race["raceName"])
    race_flag = RACE_FLAG.get(race["raceName"], "")
    lines = [f"<b>🏁 F1 • {race_name_fr} {race_flag} ({race['season']})</b>"]

    podium = sorted(results, key=lambda r: int(r["position"]))[:3]
    lines.append("\n🏆 Podium :")
    for r in podium:
        lines.append(f"{r['position']}. {r['Driver']['familyName']} ({r['Constructor']['name']})")

    standings = requests.get(f"{base}/current/driverStandings.json", timeout=15).json()
    try:
        driver_standings = standings["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        lines.append("\n📊 Classement pilotes (top 3) :")
        for d in driver_standings[:3]:
            lines.append(f" {d['position']}. {d['Driver']['familyName']} — {d['points']} pts")
    except (KeyError, IndexError):
        pass

    constructor_standings_data = requests.get(f"{base}/current/constructorStandings.json", timeout=15).json()
    try:
        constructor_standings = constructor_standings_data["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
        lines.append("\n📊 Classement constructeurs (top 3) :")
        for c in constructor_standings[:3]:
            lines.append(f" {c['position']}. {c['Constructor']['name']} — {c['points']} pts")
    except (KeyError, IndexError):
        pass

    send_message("\n".join(lines))
    state["f1"].append(race_id)


def check_matchday_announcement(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("matchday_sent_date") == today_str:
        return
    if now_paris.hour < 9:
        return

    date_param = now_paris.strftime("%Y%m%d")
    matches_today = []

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_param}"
    data = requests.get(url, timeout=15).json()
    for event in data.get("events", []):
        teams = [c["team"]["displayName"] for c in event["competitions"][0]["competitors"]]
        if any(name_matches(CONFIG["nba_team"], t) for t in teams):
            opp = next(t for t in teams if not name_matches(CONFIG["nba_team"], t))
            matches_today.append(f"🏀 NBA : {CONFIG['nba_team']} vs {opp}")

    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_param}"
    data = requests.get(url, timeout=15).json()
    for event in data.get("events", []):
        teams = [c["team"]["displayName"] for c in event["competitions"][0]["competitors"]]
        if any(name_matches(CONFIG["nfl_team"], t) for t in teams):
            opp = next(t for t in teams if not name_matches(CONFIG["nfl_team"], t))
            matches_today.append(f"🏈 NFL : {CONFIG['nfl_team']} vs {opp}")

    for league, clubs in CONFIG["football_clubs"].items():
        meta = FOOTBALL_LEAGUES.get(league, {"name": league, "flag": ""})
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_param}"
        data = requests.get(url, timeout=15).json()
        for event in data.get("events", []):
            teams = [c["team"]["displayName"] for c in event["competitions"][0]["competitors"]]
            followed = next((t for t in teams if any(name_matches(club, t) for club in clubs)), None)
            if followed:
                opp = next(t for t in teams if t != followed)
                matches_today.append(f"⚽ {meta['name']} {meta['flag']} {followed} vs {opp}")

    has_race = False
    try:
        base = "https://api.jolpi.ca/ergast/f1"
        next_race_data = requests.get(f"{base}/current/next.json", timeout=15).json()
        race = next_race_data["MRData"]["RaceTable"]["Races"][0]
        if race["date"] == now_paris.strftime("%Y-%m-%d"):
            race_name_fr = RACE_NAME_FR.get(race["raceName"], race["raceName"])
            race_flag = RACE_FLAG.get(race["raceName"], "")
            matches_today.append(f"🏁 F1 : {race_name_fr} {race_flag}")
            has_race = True
    except (KeyError, IndexError):
        pass

    if matches_today:
        nb_matches = len(matches_today) - (1 if has_race else 0)
        if has_race and nb_matches == 0:
            titre = "Aujourd'hui, jour de course !"
        elif has_race and nb_matches == 1:
            titre = "Aujourd'hui, jour de course et de match !"
        elif has_race:
            titre = "Aujourd'hui, jour de course et de matchs !"
        elif nb_matches == 1:
            titre = "Aujourd'hui, jour de match !"
        else:
            titre = "Aujourd'hui, jour de matchs !"
        lines = [f"<b>📅 {titre}</b>", ""]
        lines.extend(matches_today)
        if send_message("\n".join(lines)):
            state["matchday_sent_date"] = today_str
    else:
        state["matchday_sent_date"] = today_str


def check_birthday_announcement(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("birthday_sent_date") == today_str:
        return
    if now_paris.hour < 7:
        return

    today_md = now_paris.strftime("%m-%d")
    lines = []

    for person in CONFIG["people"]:
        if person.get("birth_date") == today_md:
            age = now_paris.year - person["birth_year"]
            lines.append(f"🎂 Aujourd'hui, c'est le {age}e anniversaire de {person['name']} !")
        if person.get("nameday") == today_md:
            lines.append(f"🎉 Aujourd'hui, c'est la fête de {person['name']} !")

    if lines:
        if send_message("\n".join(lines)):
            state["birthday_sent_date"] = today_str
    else:
        state["birthday_sent_date"] = today_str


def main():
    state = load_state()
    for check in (check_nba, check_nfl, check_football, check_f1, check_matchday_announcement, check_birthday_announcement):
        try:
            check(state)
        except Exception as e:
            print(f"[!] Erreur dans {check.__name__} : {e}")
    save_state(state)


if __name__ == "__main__":
    main()
