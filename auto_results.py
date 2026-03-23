#!/usr/bin/env python3
"""
TIMELESS TERMINAL — Auto-Ergebnis-Update
=========================================
Holt Spielergebnisse von kostenlosen APIs und schreibt
Win/Loss automatisch in Supabase.

Laeuft via GitHub Actions: 12:00 + 23:00 Uhr taeglich.

APIs:
  NBA      → balldontlie.io                         (free, Key noetig)
  Fussball → free-api-live-football-data.p.rapidapi (free, RapidAPI Key)
  Tennis   → sofascore.com                          (inoffiziell, kein Key)
"""

import re
import os
import time
import requests
from datetime import datetime, timedelta, timezone

# ══════════════════════════════════════════════════════
#  KONFIGURATION
# ══════════════════════════════════════════════════════
OUR_URL  = "https://fzkkfyxbenxbphchwiux.supabase.co"
OUR_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6a2tmeXhiZW54YnBoY2h3aXV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1NTgxNDYsImV4cCI6MjA4OTEzNDE0Nn0.vPvgHD66piV6YI53yPiEtGuI4toZ1WsY3AExPPWBc4w"
ADMIN_EMAIL = os.environ.get("SUPABASE_EMAIL", "fullerpeter762@gmail.com")
ADMIN_PASS  = os.environ.get("SUPABASE_PASSWORD", "xenxax-bejwyw-xaBca3")

# API Keys — in GitHub Secrets eintragen
BALLDONTLIE_KEY  = os.environ.get("BALLDONTLIE_KEY", "")   # balldontlie.io
RAPIDAPI_KEY     = os.environ.get("RAPIDAPI_KEY", "")      # RapidAPI (Fussball)

RAPIDAPI_HOST    = "free-api-live-football-data.p.rapidapi.com"

# Wie viele Tage rueckwirkend Ergebnisse suchen
LOOKBACK_DAYS = 5

# ══════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════
def login():
    """Einloggen und JWT Token + User ID holen."""
    r = requests.post(
        f"{OUR_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": OUR_ANON, "Content-Type": "application/json"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15
    )
    if r.status_code != 200:
        print(f"❌ Login fehlgeschlagen: {r.status_code} — {r.text[:200]}")
        return None, None

    data    = r.json()
    token   = data.get("access_token")
    user_id = data.get("user", {}).get("id")

    if not token or not user_id:
        print(f"❌ Kein Token oder User ID: {data}")
        return None, None

    print(f"✅ Eingeloggt — User ID: {user_id[:8]}...")
    return token, user_id

# ══════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════
def our_h(token):
    return {
        "apikey": OUR_ANON,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ══════════════════════════════════════════════════════
#  TEAM-NAMEN NORMALISIERUNG (1:1 aus oddify_api.py)
# ══════════════════════════════════════════════════════
NBA_NAMES = {
    'ATL':'atlanta hawks','BOS':'boston celtics','BKN':'brooklyn nets',
    'CHA':'charlotte hornets','CHI':'chicago bulls','CLE':'cleveland cavaliers',
    'DAL':'dallas mavericks','DEN':'denver nuggets','DET':'detroit pistons',
    'GSW':'golden state warriors','HOU':'houston rockets','IND':'indiana pacers',
    'LAC':'los angeles clippers','LAL':'los angeles lakers','MEM':'memphis grizzlies',
    'MIA':'miami heat','MIL':'milwaukee bucks','MIN':'minnesota timberwolves',
    'NOP':'new orleans pelicans','NYK':'new york knicks','OKC':'oklahoma city thunder',
    'ORL':'orlando magic','PHI':'philadelphia 76ers','PHX':'phoenix suns',
    'POR':'portland trail blazers','SAC':'sacramento kings','SAS':'san antonio spurs',
    'TOR':'toronto raptors','UTA':'utah jazz','WAS':'washington wizards',
}

def normalize_name(name):
    """Normalisiert Teamnamen fuer Matching — identisch mit oddify_api.py."""
    n = name.lower().strip()
    if n.upper() in NBA_NAMES:
        n = NBA_NAMES[n.upper()]
    n = n.replace('fc ', '').replace(' fc', '').replace(' cf', '')
    n = n.replace('afc ', '').replace(' afc', '').replace('sc ', '')
    n = n.replace('sv ', '').replace(' sv', '').replace('vfl ', '')
    n = n.replace('fsv ', '').replace('tsg ', '').replace('rb ', '')
    n = n.replace('1. ', '').replace('vfb ', '').replace('bsc ', '')
    n = n.replace('.', '').replace('-', ' ')
    n = n.replace('ue', 'ue').replace('ae', 'ae').replace('oe', 'oe')
    name_map = {
        'bvb': 'borussia dortmund',
        'man united': 'manchester united',
        'man city': 'manchester city',
        'atletico': 'atletico madrid',
        'inter': 'inter milan',
        'psg': 'paris saint germain',
        'paris saint germain': 'paris saint germain',
        'as monaco': 'monaco',
        'as roma': 'roma',
    }
    n = name_map.get(n, n)
    return n.strip()

def names_match(a, b):
    """
    Prueft ob zwei Team-Namen das gleiche Team meinen.
    Erst exakter Normalized-Match, dann Substring-Overlap.
    """
    na = normalize_name(a)
    nb = normalize_name(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # Wort-Overlap: min. 60% Uebereinstimmung
    wa = set(na.split())
    wb = set(nb.split())
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / max(len(wa), len(wb))
    return overlap >= 0.6

# ══════════════════════════════════════════════════════
#  SUPABASE — OFFENE WETTEN LADEN
# ══════════════════════════════════════════════════════
def get_open_bets(token):
    """Alle Eintraege mit result='open' oder result=null laden."""
    r = requests.get(
        f"{OUR_URL}/rest/v1/bets",
        params={
            "select": "id,match,sport,date,result,betteam,note",
            "or": "(result.eq.open,result.is.null)"
        },
        headers=our_h(token),
        timeout=15
    )
    if r.status_code != 200:
        print(f"❌ Fehler beim Laden offener Wetten: {r.text[:200]}")
        return []

    bets = r.json()
    print(f"📋 {len(bets)} offene Eintraege gefunden")
    return bets

# ══════════════════════════════════════════════════════
#  SUPABASE — ERGEBNIS SCHREIBEN
# ══════════════════════════════════════════════════════
def update_result(token, bet_id, result, match_str):
    """Win/Loss in Supabase schreiben. Ueberschreibt nie bereits gesetztes Ergebnis."""
    # Sicherheits-Check: aktuellen Status nochmal holen (Duplikat-Schutz)
    check = requests.get(
        f"{OUR_URL}/rest/v1/bets",
        params={"select": "result", "id": f"eq.{bet_id}"},
        headers=our_h(token),
        timeout=8
    )
    if check.status_code == 200 and check.json():
        current = check.json()[0].get("result")
        if current not in [None, "open"]:
            print(f"   🔒 Skip — bereits eingetragen: {current} ({match_str})")
            return False

    r = requests.patch(
        f"{OUR_URL}/rest/v1/bets?id=eq.{bet_id}",
        headers=our_h(token),
        json={"result": result},
        timeout=10
    )
    if r.status_code in [200, 204]:
        icon = "🟢" if result == "win" else "🔴"
        print(f"   {icon} {result.upper()} gesetzt — {match_str}")
        return True
    else:
        print(f"   ❌ Update fehlgeschlagen (ID {bet_id}): {r.text[:150]}")
        return False

# ══════════════════════════════════════════════════════
#  HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════
def parse_match(match_str):
    """'Team A vs Team B' → (team_a, team_b)"""
    parts = re.split(r'\s+vs\.?\s+', match_str, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return match_str, ""

def parse_date(date_str):
    """'DD.MM.YYYY' → datetime"""
    try:
        return datetime.strptime(date_str, "%d.%m.%Y")
    except Exception:
        return None

def date_range(lookback=LOOKBACK_DAYS):
    """Gibt Liste der letzten N Tage als 'YYYY-MM-DD' zurueck."""
    today = datetime.now()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(lookback + 1)]

# ══════════════════════════════════════════════════════
#  NBA — balldontlie.io
#  Rate Limit: 5 Requests/Min → sleep(13) zwischen Calls
# ══════════════════════════════════════════════════════
_nba_cache     = {}   # Cache: "YYYY-MM-DD" → Liste von Spielen
_nba_call_count = 0   # Zaehler fuer Rate-Limit

def fetch_nba_day(date_str):
    """NBA Ergebnisse fuer ein Datum holen. Gecacht + Rate-Limit-safe."""
    global _nba_call_count

    if date_str in _nba_cache:
        return _nba_cache[date_str]

    # Rate-Limit: nach jedem echten API Call 13s warten (5/min = 1 alle 12s)
    if _nba_call_count > 0:
        print(f"  ⏱️  Rate-Limit Pause (13s)...")
        time.sleep(13)

    headers = {}
    if BALLDONTLIE_KEY:
        headers["Authorization"] = BALLDONTLIE_KEY

    try:
        r = requests.get(
            "https://api.balldontlie.io/v1/games",
            headers=headers,
            params={"dates[]": date_str, "per_page": 100},
            timeout=15
        )
        _nba_call_count += 1

        if r.status_code == 401:
            print("  ⚠️  balldontlie: API Key fehlt oder ungueltig")
            _nba_cache[date_str] = []
            return []
        if r.status_code == 429:
            print("  ⚠️  balldontlie: Rate Limit erreicht — warte 60s...")
            time.sleep(60)
            # Nochmal versuchen
            r = requests.get(
                "https://api.balldontlie.io/v1/games",
                headers=headers,
                params={"dates[]": date_str, "per_page": 100},
                timeout=15
            )
        if r.status_code != 200:
            print(f"  ⚠️  balldontlie {date_str}: HTTP {r.status_code}")
            _nba_cache[date_str] = []
            return []

        games = r.json().get("data", [])
        _nba_cache[date_str] = games
        print(f"  📊 NBA {date_str}: {len(games)} Spiele geladen")
        return games

    except Exception as e:
        print(f"  ❌ balldontlie Exception: {e}")
        _nba_cache[date_str] = []
        return []

def resolve_nba(bet, date_str):
    """
    'win', 'loss' oder None zurueckgeben.
    None = nicht gefunden oder noch nicht fertig.
    """
    team_a, team_b = parse_match(bet["match"])
    betteam = bet.get("betteam", "")
    games   = fetch_nba_day(date_str)

    for g in games:
        home = g.get("home_team", {}).get("full_name", "")
        away = g.get("visitor_team", {}).get("full_name", "")

        match_found = (
            (names_match(team_a, home) and names_match(team_b, away)) or
            (names_match(team_a, away) and names_match(team_b, home))
        )
        if not match_found:
            continue

        status = g.get("status", "")
        if status != "Final" and "Final" not in str(status):
            print(f"  ⏳ Noch nicht fertig: {home} vs {away} (Status: {status})")
            return None

        home_score = int(g.get("home_team_score") or 0)
        away_score = int(g.get("visitor_team_score") or 0)
        home_won   = home_score > away_score

        bet_on_home = names_match(betteam, home)
        bet_on_away = names_match(betteam, away)

        if not bet_on_home and not bet_on_away:
            print(f"  ⚠️  betteam '{betteam}' nicht zuordenbar ({home} vs {away})")
            return None

        won = (bet_on_home and home_won) or (bet_on_away and not home_won)
        return "win" if won else "loss"

    return None

def proc_nba_bets(bets, token):
    """Alle offenen NBA-Wetten verarbeiten."""
    nba_bets = [b for b in bets if b.get("sport") == "nba"]
    print(f"\n🏀 NBA — {len(nba_bets)} offene Wetten")
    if not nba_bets:
        return 0

    # Alle benoenigten Daten vorher sammeln → minimiert API Calls
    needed_dates = set()
    for bet in nba_bets:
        dt = parse_date(bet.get("date", ""))
        if dt:
            needed_dates.add(dt.strftime("%Y-%m-%d"))
    for d in date_range():
        needed_dates.add(d)

    # API-Daten vorladen (mit Rate-Limit-Pausen)
    print(f"  🔄 Lade NBA Daten fuer {len(needed_dates)} Tage...")
    for d in sorted(needed_dates):
        fetch_nba_day(d)

    resolved = 0
    for bet in nba_bets:
        match_str = bet.get("match", "?")
        result    = None

        # Zuerst das eingetragene Datum probieren
        dt = parse_date(bet.get("date", ""))
        if dt:
            result = resolve_nba(bet, dt.strftime("%Y-%m-%d"))

        # Falls nicht gefunden → alle Lookback-Dates durchsuchen
        if result is None:
            for d in date_range():
                if dt and d == dt.strftime("%Y-%m-%d"):
                    continue
                result = resolve_nba(bet, d)
                if result is not None:
                    break

        if result in ["win", "loss"]:
            if update_result(token, bet["id"], result, match_str):
                resolved += 1
        else:
            print(f"  ❓ Nicht aufgeloest: {match_str}")

    return resolved

# ══════════════════════════════════════════════════════
#  FUSSBALL — RapidAPI Free Football Data
# ══════════════════════════════════════════════════════
_soccer_cache = {}  # Cache: "YYYY-MM-DD" → Liste von Spielen

def fetch_soccer_day(date_str):
    """Fussball-Ergebnisse fuer ein Datum via RapidAPI. Gecacht."""
    if date_str in _soccer_cache:
        return _soccer_cache[date_str]

    if not RAPIDAPI_KEY:
        print("  ⚠️  RAPIDAPI_KEY fehlt — in GitHub Secrets eintragen")
        _soccer_cache[date_str] = []
        return []

    try:
        r = requests.get(
            f"https://{RAPIDAPI_HOST}/football-get-matches-by-date",
            headers={
                "x-rapidapi-key":  RAPIDAPI_KEY,
                "x-rapidapi-host": RAPIDAPI_HOST
            },
            params={"date": date_str},
            timeout=15
        )

        if r.status_code == 429:
            print("  ⚠️  RapidAPI Rate Limit — warte 30s...")
            time.sleep(30)
            r = requests.get(
                f"https://{RAPIDAPI_HOST}/football-get-matches-by-date",
                headers={
                    "x-rapidapi-key":  RAPIDAPI_KEY,
                    "x-rapidapi-host": RAPIDAPI_HOST
                },
                params={"date": date_str},
                timeout=15
            )

        if r.status_code != 200:
            print(f"  ⚠️  RapidAPI Fussball {date_str}: HTTP {r.status_code} — {r.text[:150]}")
            _soccer_cache[date_str] = []
            return []

        data = r.json()
        # Response-Struktur: {"response": [...]} oder direkt Liste
        matches = data.get("response", data) if isinstance(data, dict) else data
        if not isinstance(matches, list):
            matches = []

        _soccer_cache[date_str] = matches
        print(f"  📊 Fussball {date_str}: {len(matches)} Spiele geladen")
        return matches

    except Exception as e:
        print(f"  ❌ RapidAPI Fussball Exception: {e}")
        _soccer_cache[date_str] = []
        return []

def resolve_soccer(bet, date_str):
    """
    'win', 'loss' oder None zurueckgeben.
    Draw-Wetten: betteam == 'Draw' → prueft ob Unentschieden.
    """
    team_a, team_b = parse_match(bet["match"])
    betteam        = bet.get("betteam", "")
    is_draw_bet    = betteam.lower() in ["draw", "unentschieden", "x"]
    games          = fetch_soccer_day(date_str)

    for g in games:
        # RapidAPI Response-Struktur — flexibel auslesen
        home = (
            g.get("homeTeam", {}).get("name") or
            g.get("home_team", {}).get("name") or
            g.get("home", {}).get("name") or
            g.get("homeName", "") or ""
        )
        away = (
            g.get("awayTeam", {}).get("name") or
            g.get("away_team", {}).get("name") or
            g.get("away", {}).get("name") or
            g.get("awayName", "") or ""
        )

        if not home or not away:
            continue

        match_found = (
            (names_match(team_a, home) and names_match(team_b, away)) or
            (names_match(team_a, away) and names_match(team_b, home))
        )
        if not match_found:
            continue

        # Status pruefen — Spiel muss abgeschlossen sein
        status = (
            g.get("status", {}).get("short") or
            g.get("status", {}).get("long") or
            g.get("statusShort") or
            g.get("matchStatus") or ""
        ).upper()

        # Noch nicht gespielt / verschoben / live
        if any(s in status for s in ["NS", "TBD", "PST", "CANC", "SUSP", "ABD", "AWD", "SCHED"]):
            print(f"  ⏳ {home} vs {away}: {status}")
            return None
        if any(s in status for s in ["1H", "HT", "2H", "ET", "BT", "P", "LIVE"]):
            print(f"  ⏳ Laeuft gerade: {home} vs {away}")
            return None
        if "FT" not in status and "AET" not in status and "PEN" not in status and "FINISH" not in status:
            print(f"  ⚠️  Unbekannter Status: '{status}' ({home} vs {away})")
            return None

        # Score auslesen — verschiedene moegliche Strukturen
        goals = g.get("goals") or g.get("score") or g.get("result") or {}
        h_goals = (
            goals.get("home") if isinstance(goals, dict) else None or
            g.get("homeScore") or g.get("home_score") or
            g.get("score", {}).get("fullTime", {}).get("home")
        )
        a_goals = (
            goals.get("away") if isinstance(goals, dict) else None or
            g.get("awayScore") or g.get("away_score") or
            g.get("score", {}).get("fullTime", {}).get("away")
        )

        if h_goals is None or a_goals is None:
            print(f"  ⚠️  Kein Score fuer {home} vs {away}")
            return None

        h_goals  = int(h_goals)
        a_goals  = int(a_goals)
        is_draw  = h_goals == a_goals
        home_won = h_goals > a_goals

        if is_draw_bet:
            return "win" if is_draw else "loss"

        bet_on_home = names_match(betteam, home)
        bet_on_away = names_match(betteam, away)

        if not bet_on_home and not bet_on_away:
            print(f"  ⚠️  betteam '{betteam}' nicht zuordenbar ({home} vs {away})")
            return None

        if is_draw:
            return "loss"  # Auf Team getippt, Unentschieden → verloren

        won = (bet_on_home and home_won) or (bet_on_away and not home_won)
        return "win" if won else "loss"

    return None

def proc_soccer_bets(bets, token):
    """Alle offenen Fussball-Wetten verarbeiten."""
    soccer_bets = [b for b in bets if b.get("sport") == "football"]
    print(f"\n⚽ Fussball — {len(soccer_bets)} offene Wetten")
    if not soccer_bets:
        return 0

    dates    = date_range()
    resolved = 0

    for bet in soccer_bets:
        match_str = bet.get("match", "?")
        result    = None

        dt = parse_date(bet.get("date", ""))
        if dt:
            result = resolve_soccer(bet, dt.strftime("%Y-%m-%d"))

        if result is None:
            for d in dates:
                if dt and d == dt.strftime("%Y-%m-%d"):
                    continue
                result = resolve_soccer(bet, d)
                if result is not None:
                    break

        if result in ["win", "loss"]:
            if update_result(token, bet["id"], result, match_str):
                resolved += 1
        else:
            print(f"  ❓ Nicht aufgeloest: {match_str}")

    return resolved

# ══════════════════════════════════════════════════════
#  TENNIS — Sofascore (inoffizielle API, kein Key noetig)
# ══════════════════════════════════════════════════════
_tennis_cache = {}  # Cache: "YYYY-MM-DD" → Liste von Events

def fetch_tennis_day(date_str):
    """Tennis-Ergebnisse via Sofascore. Gecacht."""
    if date_str in _tennis_cache:
        return _tennis_cache[date_str]

    try:
        r = requests.get(
            f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date_str}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.sofascore.com/"
            },
            timeout=15
        )
        if r.status_code != 200:
            print(f"  ⚠️  Sofascore {date_str}: HTTP {r.status_code}")
            _tennis_cache[date_str] = []
            return []

        events = r.json().get("events", [])
        _tennis_cache[date_str] = events
        print(f"  📊 Tennis {date_str}: {len(events)} Events geladen")
        return events

    except Exception as e:
        print(f"  ❌ Sofascore Exception: {e}")
        _tennis_cache[date_str] = []
        return []

def resolve_tennis(bet, date_str):
    """
    'win', 'loss' oder None zurueckgeben.
    Sofascore statusCode: 0=geplant, 6=live, 7=verschoben, 100=beendet, 93=retired.
    """
    team_a, team_b = parse_match(bet["match"])
    betteam = bet.get("betteam", "")
    events  = fetch_tennis_day(date_str)

    for ev in events:
        home = ev.get("homeTeam", {}).get("name", "") or ev.get("homeTeam", {}).get("shortName", "")
        away = ev.get("awayTeam", {}).get("name", "") or ev.get("awayTeam", {}).get("shortName", "")

        match_found = (
            (names_match(team_a, home) and names_match(team_b, away)) or
            (names_match(team_a, away) and names_match(team_b, home))
        )
        if not match_found:
            continue

        status_code = ev.get("status", {}).get("code")

        if status_code == 7:
            print(f"  ⏳ Verschoben: {home} vs {away}")
            return None
        if status_code in [0, 6]:
            print(f"  ⏳ Noch nicht fertig: {home} vs {away} (code {status_code})")
            return None
        if status_code not in [100, 93]:
            print(f"  ⚠️  Unbekannter Status Code {status_code}: {home} vs {away}")
            return None

        # winnerCode: 1 = Home gewonnen, 2 = Away gewonnen
        winner_code = ev.get("winnerCode")

        if winner_code is None:
            h_score = ev.get("homeScore", {}).get("current", 0) or 0
            a_score = ev.get("awayScore", {}).get("current", 0) or 0
            if h_score == a_score:
                print(f"  ⚠️  Kein eindeutiger Gewinner: {home} vs {away}")
                return None
            winner_code = 1 if h_score > a_score else 2

        home_won    = (winner_code == 1)
        bet_on_home = names_match(betteam, home)
        bet_on_away = names_match(betteam, away)

        if not bet_on_home and not bet_on_away:
            print(f"  ⚠️  betteam '{betteam}' nicht zuordenbar ({home} vs {away})")
            return None

        won = (bet_on_home and home_won) or (bet_on_away and not home_won)
        return "win" if won else "loss"

    return None

def proc_tennis_bets(bets, token):
    """Alle offenen Tennis-Wetten verarbeiten."""
    tennis_bets = [b for b in bets if b.get("sport") == "tennis"]
    print(f"\n🎾 Tennis — {len(tennis_bets)} offene Wetten")
    if not tennis_bets:
        return 0

    dates    = date_range()
    resolved = 0

    for bet in tennis_bets:
        match_str = bet.get("match", "?")
        result    = None

        dt = parse_date(bet.get("date", ""))
        if dt:
            result = resolve_tennis(bet, dt.strftime("%Y-%m-%d"))

        if result is None:
            for d in dates:
                if dt and d == dt.strftime("%Y-%m-%d"):
                    continue
                result = resolve_tennis(bet, d)
                if result is not None:
                    break

        if result in ["win", "loss"]:
            if update_result(token, bet["id"], result, match_str):
                resolved += 1
        else:
            print(f"  ❓ Nicht aufgeloest: {match_str}")

    return resolved

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    t0 = datetime.now()
    print(f"\n{'═'*55}")
    print(f"TIMELESS AUTO-RESULTS — {t0.strftime('%d.%m.%Y %H:%M')} Uhr")
    print(f"{'═'*55}")

    # 1. Login
    print("\n🔑 Login...")
    token, user_id = login()
    if not token:
        print("❌ Abbruch — kein Token")
        return

    # 2. Offene Wetten laden
    print("\n📋 Offene Wetten laden...")
    bets = get_open_bets(token)
    if not bets:
        print("✅ Nichts zu tun — keine offenen Wetten")
        return

    nba_c    = sum(1 for b in bets if b.get("sport") == "nba")
    soccer_c = sum(1 for b in bets if b.get("sport") == "football")
    tennis_c = sum(1 for b in bets if b.get("sport") == "tennis")
    print(f"   🏀 NBA: {nba_c} | ⚽ Fussball: {soccer_c} | 🎾 Tennis: {tennis_c}")

    # 3. Ergebnisse holen und eintragen
    total  = 0
    total += proc_nba_bets(bets, token)
    total += proc_soccer_bets(bets, token)
    total += proc_tennis_bets(bets, token)

    # 4. Zusammenfassung
    dt_s = (datetime.now() - t0).seconds
    print(f"\n{'═'*55}")
    print(f"✅ Fertig in {dt_s}s — {total}/{len(bets)} Ergebnisse eingetragen")
    print(f"{'═'*55}\n")

if __name__ == "__main__":
    main()
