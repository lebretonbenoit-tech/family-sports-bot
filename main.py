"""
Bot Telegram multi-sports — canal privé "toi + ton fils"
Sports couverts : NBA (Miami Heat), NFL (Denver Broncos),
Football (FC Barcelone, OM, Bayern, Man United, Équipe de France),
F1 (Red Bull, Alpine, Leclerc, Hamilton, Verstappen)

Architecture 0€ : ESPN API (NBA/NFL/Foot) + Jolpica API (F1, remplaçante gratuite d'Ergast)
Pensé pour tourner toutes les 10-15 min via GitHub Actions (cron), comme DUNKR LIVE.

Variables d'environnement nécessaires :
  TELEGRAM_BOT_TOKEN   -> token du bot (via @BotFather)
  TELEGRAM_CHAT_ID     -> id du canal privé (ex: -1001234567890)
"""

import os
import json
import re
import requests
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

STATE_FILE = "state.json"

# À modifier à chaque mise à jour du bot : le bot enverra automatiquement
# ce message une seule fois, dès qu'il détecte un numéro de version différent
# de celui déjà annoncé.
BOT_VERSION = "2.2"
CHANGELOG = [
    "Ajout du suivi de l'équipe de France (Ligue des Nations + matchs amicaux)",
    "Ajout de l'alerte Top 100 Beatport pour Sonico BCN",
]

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ----------------------------------------------------------------------
# CONFIG — modifiable librement : ajoute/retire équipes, clubs, sports ici
# ----------------------------------------------------------------------
CONFIG = {
    "nba_team": "Miami Heat",
    "nfl_team": "Denver Broncos",
    "football_clubs": {
        "esp.1": ["Barcelona"],       # La Liga
        "fra.1": ["Marseille"],       # Ligue 1
        "ger.1": ["Bayern Munich"],   # Bundesliga
        "eng.1": ["Manchester United"],  # Premier League
        "uefa.champions": ["Barcelona", "Bayern Munich", "Manchester United", "Marseille"],  # C1
        "uefa.europa": ["Barcelona", "Bayern Munich", "Manchester United", "Marseille"],  # Europa League
        "uefa.nations": ["France"],  # Ligue des Nations, équipe nationale
        "fifa.friendly": ["France"],  # Matchs amicaux, équipe nationale
    },
    "f1_teams": ["Red Bull", "Alpine"],
    "f1_drivers": ["Leclerc", "Hamilton", "Verstappen"],
    "people": [
        {"name": "Arthur", "birth_date": "11-06", "birth_year": 2011, "nameday": "11-15"},
        {"name": "Benoit", "birth_date": "06-10", "birth_year": 1983, "nameday": "07-11"},
    ],
    "beatport_labels": {
        "Sonico BCN": {"id": 122893, "slug": "sonico-bcn"},
    },
    "beatport_label_emoji": {
        "Sonico BCN": "⚡",
        "Deep Over Records": "🌴",
    },
    "beatport_genres": [
        {"slug": "techno-peak-time-driving", "id": 6, "name": "Techno (Peak Time / Driving)"},
        {"slug": "techno-raw-deep-hypnotic", "id": 92, "name": "Techno (Raw / Deep / Hypnotic)"},
        {"slug": "tech-house", "id": 11, "name": "Tech House"},
        {"slug": "melodic-house-techno", "id": 90, "name": "Melodic House & Techno"},
        {"slug": "minimal-deep-tech", "id": 14, "name": "Minimal / Deep Tech"},
    ],
}

# Nom affiché + drapeau par compétition (uniquement les championnats/C1 :
# les matchs de coupe ne sont pas suivis, pas besoin de journée pour eux)
FOOTBALL_LEAGUES = {
    "esp.1": {"name": "Liga", "flag": "🇪🇸"},
    "fra.1": {"name": "Ligue 1", "flag": "🇫🇷"},
    "ger.1": {"name": "Bundesliga", "flag": "🇩🇪"},
    "eng.1": {"name": "Premier League", "flag": "🇬🇧"},
    "uefa.champions": {"name": "Champions League", "flag": "🌟"},
    "uefa.europa": {"name": "Europa League", "flag": "🏆"},
    "uefa.nations": {"name": "Ligue des Nations", "flag": "🇫🇷"},
    "fifa.friendly": {"name": "Match amical", "flag": "🇫🇷"},
}

# Emoji de victoire personnalisé par club (par défaut 😁 si non précisé ici)
CLUB_WIN_EMOJI = {
    "Manchester United": "😈",   # Red Devils
    "Barcelona": "🔵🔴",         # Blaugrana
    "Marseille": "⚪🔵",         # Blanc et bleu ciel
    "Bayern Munich": "🔴⚪",     # Rouge et blanc
}

# Traduction des noms de Grand Prix (nom renvoyé par l'API -> nom français)
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

# Drapeau du pays hôte, par Grand Prix (même clé que RACE_NAME_FR)
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


# ----------------------------------------------------------------------
# Utilitaires génériques
# ----------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"nba": [], "nfl": [], "football": [], "f1": [], "matchday_sent_date": "", "birthday_sent_date": "", "monthly_age_sent_date": "", "special_day_sent_date": "", "beatport_sent_date": "", "beatport_status": {}, "last_announced_version": ""}


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


def clean_team_name(name):
    """Retire les préfixes numériques de certains noms de clubs allemands
    (ex: '1. FC Union Berlin' -> 'FC Union Berlin'), purement cosmétique."""
    if name[:3] == "1. ":
        return name[3:]
    return name


# ----------------------------------------------------------------------
# NBA — Miami Heat : résultat + meilleurs marqueurs Miami + classement
# ----------------------------------------------------------------------

def check_nba(state):
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    data = requests.get(url, timeout=15).json()

    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if not any(name_matches(CONFIG["nba_team"], t) for t in teams):
            continue
        if event["status"]["type"]["name"] != "STATUS_FINAL":
            continue  # on ne poste qu'au résultat final pour l'instant
        game_id = event["id"]
        if game_id in state["nba"]:
            continue

        heat = next(c for c in competitors if name_matches(CONFIG["nba_team"], c["team"]["displayName"]))
        opp = next(c for c in competitors if not name_matches(CONFIG["nba_team"], c["team"]["displayName"]))
        heat_score, opp_score = int(heat["score"]), int(opp["score"])

        # Meilleur marqueur Miami
        leaders = heat.get("leaders", [])
        top_scorer_line = ""
        if leaders:
            pts_leader = leaders[0]["leaders"][0]
            top_scorer_line = f"\n\n🏀 Top marqueur Miami : {pts_leader['athlete']['displayName']} — {pts_leader['displayValue']}"

        # Classement (record) après le match
        heat_record = heat.get("records", [{}])[0].get("summary", "N/A")

        msg = (
            f"<b>🏀 NBA</b>\n\n"
            f"{CONFIG['nba_team']} {heat_score} - {opp_score} {opp['team']['displayName']}"
            f"{top_scorer_line}"
            f"\n\n📊 Bilan Miami : {heat_record}"
        )
        send_message(msg)
        state["nba"].append(game_id)


# ----------------------------------------------------------------------
# NFL — Denver Broncos : même format que Miami Heat
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Football — clubs suivis (résultat en direct/final)
# ----------------------------------------------------------------------

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
            team_names_by_id = {c["team"]["id"]: clean_team_name(c["team"]["displayName"]) for c in competitors}
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
                f"{clean_team_name(home['team']['displayName'])} {home['score']} - {away['score']} {clean_team_name(away['team']['displayName'])}"
                f"{scorers_block}"
            )
            send_message(msg)
            state["football"].append(game_id)


# ----------------------------------------------------------------------
# F1 — dernière course : résultat + classement pilotes/constructeurs
# ----------------------------------------------------------------------

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

    # Classement pilotes après la course (top 3)
    standings = requests.get(f"{base}/current/driverStandings.json", timeout=15).json()
    try:
        driver_standings = standings["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        lines.append("\n📊 Classement pilotes (top 3) :")
        for d in driver_standings[:3]:
            lines.append(f"  {d['position']}. {d['Driver']['familyName']} — {d['points']} pts")
    except (KeyError, IndexError):
        pass

    # Classement constructeurs après la course (top 3)
    constructor_standings_data = requests.get(f"{base}/current/constructorStandings.json", timeout=15).json()
    try:
        constructor_standings = constructor_standings_data["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
        lines.append("\n📊 Classement constructeurs (top 3) :")
        for c in constructor_standings[:3]:
            lines.append(f"  {c['position']}. {c['Constructor']['name']} — {c['points']} pts")
    except (KeyError, IndexError):
        pass

    send_message("\n".join(lines))
    state["f1"].append(race_id)


# ----------------------------------------------------------------------
# Message du matin — "Aujourd'hui, jour de match !" (9h heure française,
# uniquement s'il y a au moins un match, une seule fois par jour)
# ----------------------------------------------------------------------

def check_matchday_announcement(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("matchday_sent_date") == today_str:
        return  # déjà traité aujourd'hui
    if now_paris.hour < 9:
        return  # on n'agit qu'entre 9h00 et 9h59 heure française

    date_param = now_paris.strftime("%Y%m%d")
    matches_today = []  # liste de tuples (datetime_paris, texte_affiché)

    def event_time_paris(event):
        dt_utc = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        return dt_utc.astimezone(ZoneInfo("Europe/Paris"))

    # NBA
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_param}"
    data = requests.get(url, timeout=15).json()
    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if any(name_matches(CONFIG["nba_team"], t) for t in teams):
            home = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "home")
            away = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "away")
            when = event_time_paris(event)
            matches_today.append((when, f"{when.strftime('%Hh%M')} — 🏀 NBA : {away} @ {home}"))

    # NFL
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_param}"
    data = requests.get(url, timeout=15).json()
    for event in data.get("events", []):
        competitors = event["competitions"][0]["competitors"]
        teams = [c["team"]["displayName"] for c in competitors]
        if any(name_matches(CONFIG["nfl_team"], t) for t in teams):
            home = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "home")
            away = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "away")
            when = event_time_paris(event)
            matches_today.append((when, f"{when.strftime('%Hh%M')} — 🏈 NFL : {away} @ {home}"))

    # Football
    for league, clubs in CONFIG["football_clubs"].items():
        meta = FOOTBALL_LEAGUES.get(league, {"name": league, "flag": ""})
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_param}"
        data = requests.get(url, timeout=15).json()
        for event in data.get("events", []):
            competitors = event["competitions"][0]["competitors"]
            teams = [c["team"]["displayName"] for c in competitors]
            if any(name_matches(club, t) for club in clubs for t in teams):
                home = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "home")
                away = next(c["team"]["displayName"] for c in competitors if c["homeAway"] == "away")
                when = event_time_paris(event)
                matches_today.append((when, f"{when.strftime('%Hh%M')} — ⚽ {meta['name']} {meta['flag']} {clean_team_name(home)} vs {clean_team_name(away)}"))

    # F1 (course du jour)
    has_race = False
    try:
        base = "https://api.jolpi.ca/ergast/f1"
        next_race_data = requests.get(f"{base}/current/next.json", timeout=15).json()
        race = next_race_data["MRData"]["RaceTable"]["Races"][0]
        if race["date"] == now_paris.strftime("%Y-%m-%d"):
            race_name_fr = RACE_NAME_FR.get(race["raceName"], race["raceName"])
            race_flag = RACE_FLAG.get(race["raceName"], "")
            race_time_str = race.get("time", "")
            if race_time_str:
                dt_utc = datetime.fromisoformat(f"{race['date']}T{race_time_str.replace('Z', '+00:00')}")
                when = dt_utc.astimezone(ZoneInfo("Europe/Paris"))
                time_prefix = f"{when.strftime('%Hh%M')} — "
            else:
                when = now_paris  # pas d'heure connue : affiché en premier par défaut
                time_prefix = ""
            matches_today.append((when, f"{time_prefix}🏁 F1 : {race_name_fr} {race_flag}"))
            has_race = True
    except (KeyError, IndexError):
        pass

    if matches_today:
        matches_today.sort(key=lambda item: item[0])
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
        lines.extend(text for _, text in matches_today)
        if send_message("\n".join(lines)):
            state["matchday_sent_date"] = today_str  # marqué seulement si l'envoi a réussi
    else:
        state["matchday_sent_date"] = today_str  # rien à envoyer, on marque quand même la journée


# ----------------------------------------------------------------------
# Anniversaires et fêtes — 7h heure française, une fois par jour
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Âge mensuel (ex: "Arthur a 14 ans et 8 mois") — le jour du mois
# correspondant à la date de naissance, sauf le mois de l'anniversaire
# (déjà couvert par check_birthday_announcement). 7h heure française.
# ----------------------------------------------------------------------

def check_monthly_age_announcement(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("monthly_age_sent_date") == today_str:
        return
    if now_paris.hour < 7:
        return

    lines = []

    for person in CONFIG["people"]:
        birth_date = person.get("birth_date")
        if not birth_date:
            continue
        birth_month, birth_day = (int(x) for x in birth_date.split("-"))

        if now_paris.day != birth_day:
            continue
        if now_paris.month == birth_month:
            continue  # c'est le mois de l'anniversaire, déjà géré ailleurs

        months_total = (now_paris.year - person["birth_year"]) * 12 + (now_paris.month - birth_month)
        years, months = divmod(months_total, 12)
        age_str = f"{years} ans" if months == 0 else f"{years} ans et {months} mois"
        lines.append(f"🎈 Aujourd'hui, {person['name']} a {age_str} !")

    if lines:
        if send_message("\n".join(lines)):
            state["monthly_age_sent_date"] = today_str
    else:
        state["monthly_age_sent_date"] = today_str


# ----------------------------------------------------------------------
# Jours spéciaux (Noël, 14 Juillet, Halloween, Nouvel An, Saint-Valentin,
# 1er Mai, Fête des Mères/Pères) — 7h heure française, une fois par jour
# ----------------------------------------------------------------------

def easter_date(year):
    """Calcule la date de Pâques (algorithme de Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_sunday_of_month(year, month, n):
    first_day = date(year, month, 1)
    offset = (6 - first_day.weekday()) % 7
    first_sunday = first_day + timedelta(days=offset)
    return first_sunday + timedelta(weeks=n - 1)


def last_sunday_of_month(year, month):
    next_month_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = next_month_first - timedelta(days=1)
    offset = (last_day.weekday() - 6) % 7
    return last_day - timedelta(days=offset)


def fete_des_meres(year):
    """Dernier dimanche de mai, sauf si ça tombe le jour de la Pentecôte
    (Pâques + 49 jours), auquel cas c'est reporté au 1er dimanche de juin."""
    candidate = last_sunday_of_month(year, 5)
    pentecost = easter_date(year) + timedelta(days=49)
    if candidate == pentecost:
        return nth_sunday_of_month(year, 6, 1)
    return candidate


def fete_des_peres(year):
    return nth_sunday_of_month(year, 6, 3)  # 3e dimanche de juin


def get_special_days(year):
    """Retourne un dict {'MM-DD': message} pour l'année donnée."""
    days = {
        "01-01": f"🎉 Une toute nouvelle année démarre, {year} ! Que la santé, le bonheur et de belles réussites vous accompagnent tout au long de l'année, à vous, la famille Lebreton !",
        "02-14": "❤️ Aujourd'hui c'est la Saint-Valentin, une pensée pour tous ceux que vous aimez !",
        "05-01": "🤍 Bon 1er mai ! Un brin de muguet blanc et une belle journée de repos.",
        "07-14": "🇫🇷 Joyeuse Fête Nationale ! Liberté, Égalité, Fraternité — vive la France !",
        "10-31": "🎃👻 Joyeux Halloween ! Que la chasse aux bonbons soit fructueuse.",
        "12-25": "🎄✨ Joyeux Noël à vous, la famille Lebreton ! Que cette journée soit pleine de magie et de moments partagés.",
    }
    days[fete_des_meres(year).strftime("%m-%d")] = "💐 C'est la Fête des Mères aujourd'hui, n'oubliez pas de lui montrer tout votre amour !"
    days[fete_des_peres(year).strftime("%m-%d")] = "👔🏆 Bonne Fête des Pères, Benoit ! Arthur a bien de la chance de t'avoir."
    return days


def check_special_day_announcement(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("special_day_sent_date") == today_str:
        return
    if now_paris.hour < 7:
        return

    today_md = now_paris.strftime("%m-%d")
    message = get_special_days(now_paris.year).get(today_md)

    if message:
        if send_message(f"<b>{message}</b>"):
            state["special_day_sent_date"] = today_str
    else:
        state["special_day_sent_date"] = today_str


# ----------------------------------------------------------------------
# Beatport — alerte quand un des labels entre dans un Top 100 suivi
# (une vérification par jour, à partir de 10h heure française)
# ----------------------------------------------------------------------

def find_chart_position(page_html, label_marker):
    """Cherche le numéro de position (1-100) le plus proche avant le lien du
    label dans la page. Best-effort : dépend de la structure HTML de
    Beatport, peut ne rien trouver si la page change de forme."""
    idx = page_html.find(label_marker)
    if idx == -1:
        return None
    snippet = page_html[max(0, idx - 1000):idx]
    matches = re.findall(r">(\d{1,3})<", snippet)
    for m in reversed(matches):
        n = int(m)
        if 1 <= n <= 100:
            return n
    return None


def check_beatport_charts(state):
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now_paris.strftime("%Y-%m-%d")

    if state.get("beatport_sent_date") == today_str:
        return
    if now_paris.hour < 10:
        return

    if "beatport_status" not in state:
        state["beatport_status"] = {}

    chart_types = [("top-100", "Top 100 Tracks"), ("top-100-releases", "Top 100 Releases")]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; family-sports-bot/1.0)"}
    messages = []

    for genre in CONFIG["beatport_genres"]:
        for chart_slug, chart_label in chart_types:
            url = f"https://www.beatport.com/genre/{genre['slug']}/{genre['id']}/{chart_slug}"
            try:
                page = requests.get(url, timeout=15, headers=headers).text
            except Exception:
                continue

            for label_name, label_info in CONFIG["beatport_labels"].items():
                key = f"{label_name}|{genre['slug']}|{chart_slug}"
                marker = f"/label/{label_info['slug']}/{label_info['id']}"
                is_in = marker in page
                was_in = state["beatport_status"].get(key, False)
                if is_in and not was_in:
                    emoji = CONFIG["beatport_label_emoji"].get(label_name, "🎵")
                    position = find_chart_position(page, marker)
                    place = f" à la {position}e place" if position else ""
                    messages.append(f"{emoji} {label_name} est entré{place} dans le {chart_label} de {genre['name']} !")
                state["beatport_status"][key] = is_in

    state["beatport_sent_date"] = today_str

    if messages:
        send_message("<b>🎧 Beatport</b>\n\n" + "\n".join(messages))


# ----------------------------------------------------------------------
# Annonce de mise à jour du bot — envoyée une seule fois par version,
# dès la prochaine exécution après un changement de BOT_VERSION
# ----------------------------------------------------------------------

def check_version_announcement(state):
    if state.get("last_announced_version") == BOT_VERSION:
        return

    changelog_lines = "\n\n".join(CHANGELOG)
    msg = f"<b>🤖 Mise à jour du bot — version {BOT_VERSION}</b>\n\n{changelog_lines}"
    if send_message(msg):
        state["last_announced_version"] = BOT_VERSION


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    state = load_state()
    for check in (check_version_announcement, check_nba, check_nfl, check_football, check_f1, check_matchday_announcement, check_birthday_announcement, check_monthly_age_announcement, check_special_day_announcement, check_beatport_charts):
        try:
            check(state)
        except Exception as e:
            print(f"[!] Erreur dans {check.__name__} : {e}")
    save_state(state)


if __name__ == "__main__":
    main()
