#!/usr/bin/env python3
"""
TIMELESS TERMINAL — Auto-Tracker
NBA + Fußball + Tennis — direkte Oddify API Calls
"""

import requests
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════
#  KONFIGURATION
# ══════════════════════════════════════════════════════
ODDIFY_URL  = "https://fouddhhpuyrxugfhuqmq.supabase.co"
ODDIFY_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZvdWRkaGhwdXlyeHVnZmh1cW1xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY5MjA3ODcsImV4cCI6MjA3MjQ5Njc4N30.WVnGOt-nuubcVQLDskLqZSrcezK4OkbUFOUOLXWbqv4"

OUR_URL     = "https://fzkkfyxbenxbphchwiux.supabase.co"
OUR_ANON    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6a2tmeXhiZW54YnBoY2h3aXV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1NTgxNDYsImV4cCI6MjA4OTEzNDE0Nn0.vPvgHD66piV6YI53yPiEtGuI4toZ1WsY3AExPPWBc4w"
ADMIN_EMAIL = "fullerpeter762@gmail.com"
ADMIN_PASS  = "xenxax-bejwyw-xaBca3"

BANKROLL = 150
KELLY    = 0.125

# ══════════════════════════════════════════════════════
#  THE ODDS API — Pinnacle Quoten
# ══════════════════════════════════════════════════════
ODDS_API_KEY = "07f70ed8f4c796f5bb59b1a102fa0e01"

# Sport-Keys für The Odds API
# Pinnacle-Ligen (große Ligen — hohe Liquidität)
SOCCER_API_LEAGUES = [
    "soccer_germany_bundesliga",
    "soccer_germany_bundesliga2",
    "soccer_epl",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
]

# Fallback-Ligen (kein Pinnacle → beste verfügbare Bookie-Quote)
SOCCER_FALLBACK_LEAGUES = [
    "soccer_england_championship",
    "soccer_england_league1",
    "soccer_england_league2",
    "soccer_spain_segunda_division",
    "soccer_france_ligue_two",
    "soccer_germany_liga3",
    "soccer_italy_serie_b",
    "soccer_portugal_primeira_liga",
    "soccer_turkey_super_league",
]

_odds_cache = {}
_soccer_odds_cache = None
_soccer_fallback_cache = None  # Fallback-Quoten für kleine Ligen

def _parse_odds_response(games_json):
    odds_map = {}
    for game in games_json:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_odds = away_odds = draw_odds = 0
        for bm in game.get("bookmakers", []):
            for mk in bm.get("markets", []):
                if mk["key"] == "h2h":
                    for oc in mk["outcomes"]:
                        if oc["name"] == home:
                            home_odds = max(home_odds, oc["price"])
                        elif oc["name"] == away:
                            away_odds = max(away_odds, oc["price"])
                        elif oc["name"] == "Draw":
                            draw_odds = max(draw_odds, oc["price"])
        key = f"{home}|{away}".lower()
        odds_map[key] = {"home": home_odds, "away": away_odds, "draw": draw_odds,
                         "home_team": home, "away_team": away}
    return odds_map

def fetch_all_soccer_odds():
    """Holt alle Fußball-Ligen — gemeinsamer Cache, spart Requests"""
    global _soccer_odds_cache
    print(f"  🌐 fetch_all_soccer_odds gestartet (cache={_soccer_odds_cache is not None})", flush=True)
    if _soccer_odds_cache is not None:
        print(f"  ♻️  Cache hit: {len(_soccer_odds_cache)} Spiele", flush=True)
        return _soccer_odds_cache
    all_odds = {}
    print(f"  🔄 Starte Odds API Calls für {len(SOCCER_API_LEAGUES)} Ligen...", flush=True)
    for league in SOCCER_API_LEAGUES:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                params={"apiKey": ODDS_API_KEY, "regions": "eu",
                        "markets": "h2h", "oddsFormat": "decimal",
                        "bookmakers": "pinnacle"},
                timeout=15
            )
            remaining = r.headers.get("x-requests-remaining", "?")
            if r.status_code == 200:
                parsed = _parse_odds_response(r.json())
                all_odds.update(parsed)
                print(f"  📊 {league}: {len(parsed)} Spiele | {remaining} übrig")
            elif r.status_code == 422:
                print(f"  ℹ️  {league}: keine Spiele gerade")
            else:
                print(f"  ⚠️  {league}: {r.status_code} — {r.text[:100]}")
                if r.status_code in [401, 429]:
                    print("  ❌ API Limit oder Key-Problem — Abbruch")
                    break
        except Exception as e:
            print(f"  ⚠️  {league}: {e}")
    print(f"  ✅ Fußball gesamt: {len(all_odds)} Pinnacle Spiele")
    if all_odds:
        print(f"  🔍 Beispiele: {list(all_odds.keys())[:3]}")
    _soccer_odds_cache = all_odds
    return all_odds

def fetch_all_soccer_fallback_odds():
    """Holt Quoten fuer kleine Ligen (kein Pinnacle) — beste verfuegbare Bookie-Quote."""
    global _soccer_fallback_cache
    if _soccer_fallback_cache is not None:
        print(f"  ♻️  Fallback-Cache hit: {len(_soccer_fallback_cache)} Spiele")
        return _soccer_fallback_cache
    all_odds = {}
    print(f"  🔄 Fallback Odds fuer {len(SOCCER_FALLBACK_LEAGUES)} kleine Ligen...", flush=True)
    for league in SOCCER_FALLBACK_LEAGUES:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                params={"apiKey": ODDS_API_KEY, "regions": "eu",
                        "markets": "h2h", "oddsFormat": "decimal"},
                timeout=15
            )
            remaining = r.headers.get("x-requests-remaining", "?")
            if r.status_code == 200:
                parsed = _parse_odds_response(r.json())
                all_odds.update(parsed)
                print(f"  📊 {league}: {len(parsed)} Spiele | {remaining} übrig")
            elif r.status_code == 422:
                print(f"  ℹ️  {league}: keine Spiele gerade")
            else:
                print(f"  ⚠️  {league}: {r.status_code}")
                if r.status_code in [401, 429]:
                    print("  ❌ API Limit — Abbruch Fallback")
                    break
        except Exception as e:
            print(f"  ⚠️  {league}: {e}")
    print(f"  ✅ Fallback gesamt: {len(all_odds)} Spiele")
    _soccer_fallback_cache = all_odds
    return all_odds

def fetch_pinnacle_odds(sport_key):
    if sport_key.startswith("football"):
        return fetch_all_soccer_odds()
    if sport_key == "nba":
        api_sport = "basketball_nba"
    else:
        print(f"  ℹ️  Kein Odds API Mapping für '{sport_key}'")
        return {}
    if api_sport in _odds_cache:
        return _odds_cache[api_sport]
    print(f"  🌐 Odds API: {api_sport}...")
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{api_sport}/odds/",
            params={"apiKey": ODDS_API_KEY, "regions": "eu",
                    "markets": "h2h", "oddsFormat": "decimal",
                    "bookmakers": "pinnacle"},
            timeout=15
        )
        remaining = r.headers.get("x-requests-remaining", "?")
        print(f"  → Status: {r.status_code} | {remaining} Requests übrig")
        if r.status_code != 200:
            print(f"  ❌ Odds API Fehler: {r.text[:200]}")
            return {}
        odds_map = _parse_odds_response(r.json())
        print(f"  📊 Pinnacle {api_sport}: {len(odds_map)} Spiele")
        if odds_map:
            print(f"  🔍 Beispiele: {list(odds_map.keys())[:2]}")
        _odds_cache[api_sport] = odds_map
        return odds_map
    except Exception as e:
        print(f"  ⚠️  Odds API Fehler ({api_sport}): {e}")
        return {}

# NBA Abkürzung → Vollname Mapping
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
    # Soccer shortcuts
    'BVB':'borussia dortmund','FCB':'fc barcelona','RMA':'real madrid',
}

def normalize_name(name):
    """Normalisiert Teamnamen für Matching"""
    n = name.lower().strip()
    # NBA Abkürzung aufläsen
    if n.upper() in NBA_NAMES:
        n = NBA_NAMES[n.upper()]
    # Fußball Team-Name Cleanup
    n = n.replace('fc ', '').replace(' fc', '').replace(' cf', '')
    n = n.replace('afc ', '').replace(' afc', '').replace('sc ', '')
    n = n.replace('sv ', '').replace(' sv', '').replace('vfl ', '')
    n = n.replace('fsv ', '').replace('tsg ', '').replace('rb ', '')
    n = n.replace('1. ', '').replace('vfb ', '').replace('bsc ', '')
    n = n.replace('.', '').replace('-', ' ').replace('ü','ue')
    n = n.replace('ä','ae').replace('ö','oe').replace('ß','ss')
    # Common name mappings
    name_map = {
        'bvb': 'borussia dortmund',
        'man united': 'manchester united',
        'man city': 'manchester city',
        'atletico madrid': 'atletico madrid',
        'atletico': 'atletico madrid',
        'inter': 'inter milan',
        'inter milan': 'inter milan',
        'psg': 'paris saint germain',
        'paris saint germain': 'paris saint germain',
        'as monaco': 'monaco',
        'as roma': 'roma',
    }
    n = name_map.get(n, n)
    return n.strip()

def find_pinnacle_odds(home_team, away_team, odds_map):
    """Sucht Pinnacle Quote — mit NBA Name Mapping"""
    if not odds_map:
        return 0, 0, 0

    home_n = normalize_name(home_team)
    away_n = normalize_name(away_team)

    best_match = None
    best_score = 0

    for k, v in odds_map.items():
        h, a = k.split('|')
        h_n = normalize_name(h)
        a_n = normalize_name(a)

        # Exakter Match
        if home_n == h_n and away_n == a_n:
            return v['home'], v['away'], v.get('draw', 0)
        if home_n == a_n and away_n == h_n:
            return v['away'], v['home'], v.get('draw', 0)

        # Partial match — score berechnen
        score = 0
        if home_n in h_n or h_n in home_n: score += 2
        if away_n in a_n or a_n in away_n: score += 2
        if home_n[:5] in h_n: score += 1
        if away_n[:5] in a_n: score += 1

        if score >= 4 and score > best_score:
            best_score = score
            best_match = (v['home'], v['away'], v.get('draw', 0))

        # Reversed
        score2 = 0
        if home_n in a_n or a_n in home_n: score2 += 2
        if away_n in h_n or h_n in away_n: score2 += 2
        if score2 >= 4 and score2 > best_score:
            best_score = score2
            best_match = (v['away'], v['home'], v.get('draw', 0))

    return best_match if best_match else (0, 0, 0)

# ══════════════════════════════════════════════════════
#  LOGIN — holt JWT Token und User ID
# ══════════════════════════════════════════════════════
def login():
    """Einloggen und JWT Token + User ID holen"""
    r = requests.post(
        f"{OUR_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": OUR_ANON, "Content-Type": "application/json"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15
    )
    if r.status_code != 200:
        print(f"❌ Login fehlgeschlagen: {r.status_code} — {r.text[:200]}")
        return None, None

    data       = r.json()
    token      = data.get("access_token")
    user_id    = data.get("user", {}).get("id")

    if not token or not user_id:
        print(f"❌ Kein Token oder User ID: {data}")
        return None, None

    print(f"✅ Eingeloggt — User ID: {user_id[:8]}...")
    return token, user_id

# ══════════════════════════════════════════════════════
#  HEADER FUNKTIONEN
# ══════════════════════════════════════════════════════
def oddify_h():
    return {
        "apikey": ODDIFY_KEY,
        "Authorization": f"Bearer {ODDIFY_KEY}",
        "Accept": "application/json"
    }

def our_h(token):
    return {
        "apikey": OUR_ANON,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ══════════════════════════════════════════════════════
#  BERECHNUNGEN
# ══════════════════════════════════════════════════════
def calc_edge(ws, q):
    return ((ws/100)*q - 1)*100

def calc_kelly(ws, q):
    b = q-1; p = ws/100
    return max(0, (b*p-(1-p))/b) if b>0 else 0

def calc_score(ep, q, ws):
    s = 0
    if 2.00<=q<2.50:  s+=3
    elif 1.80<=q<2.00: s+=2
    elif 2.50<=q<3.00: s+=1
    if ws>=70:   s+=3
    elif ws>=60: s+=2
    elif ws>=55: s+=1
    if 4<=ep<=12:    s+=2
    elif 12<ep<=25:  s+=1
    if q>=3.50 or ep>100: return s, 0, "AUTO-SKIP"
    if s>=8:   return s, 1.0, "WETTEN"
    elif s>=6: return s, 0.75, "WETTEN"
    elif s>=4: return s, 0.5, "ÜBERLEGEN"
    return s, 0, "SKIP"

def normalize_league(l):
    if not l: return 'football'
    l = l.lower()
    if 'bundesliga' in l and '2' in l: return 'football_2bundesliga'
    if 'bundesliga' in l: return 'football_bundesliga'
    if 'premier' in l:    return 'football_premier_league'
    if 'champions' in l:  return 'football_champions_league'
    if 'europa' in l:     return 'football_europa_league'
    if 'serie a' in l:    return 'football_serie_a'
    if 'laliga' in l or 'la liga' in l: return 'football_laliga'
    if 'ligue' in l:      return 'football_ligue1'
    if '3. liga' in l or 'liga 3' in l or 'dritte' in l: return 'football_3liga'
    if 'eredivisie' in l: return 'football_eredivisie'
    if 'segunda' in l:    return 'football_segunda'   # kein Pinnacle erwartet
    return 'football'

# ══════════════════════════════════════════════════════
#  SUPABASE SPEICHERN
# ══════════════════════════════════════════════════════
def already_today(token, match, sport):
    today = datetime.now().strftime("%d.%m.%Y")
    short = match[:15].replace("'","")
    try:
        r = requests.get(
            f"{OUR_URL}/rest/v1/bets",
            params={"date": f"eq.{today}", "sport": f"eq.{sport}",
                    "match": f"ilike.*{short}*", "select": "id"},
            headers=our_h(token), timeout=8
        )
        return r.status_code==200 and len(r.json())>0
    except:
        return False

def save_bet(token, user_id, game):
    # Spieldatum aus den Daten — NICHT das Scrape-Datum
    game_date = game.get('game_date') or datetime.now().strftime("%d.%m.%Y")
    sport_db = 'nba' if game['sport']=='nba' else 'tennis' if game['sport']=='tennis' else 'football'

    payload = {
        "user_id":       user_id,
        "match":         game['match'],
        "betteam":       game['team'],
        "date":          game_date,
        "stake":         game['stake'],
        "odds":          game['odds'],
        "edge":          game['edge'],
        "type":          "spotted" if game['edge']>=4 else "skip",
        "ows":           game['ws'],
        "impl":          game['impl'],
        "sport":         sport_db,
        "result":        "open",
        "note":          (
            f"Auto-Tracker | {game['league']} | {game['rec']} | {game['ws_home']}|{game['ws_draw']}|{game['ws_away']}"
            if game.get('ws_home') is not None and game.get('sport','').startswith('football')
            else f"Auto-Tracker | {game['league']} | {game['rec']}"
        ),
        "tracking_only": game['tracking_only'],
        "is_pick":       game['is_pick'],
        "created_at":    datetime.now().isoformat()
    }

    r = requests.post(
        f"{OUR_URL}/rest/v1/bets",
        headers={**our_h(token), "Prefer": "return=minimal"},
        json=payload,
        timeout=10
    )
    if r.status_code not in [200, 201]:
        print(f"    ❌ DB Fehler {r.status_code}: {r.text[:150]}")
        return False
    return True

# ══════════════════════════════════════════════════════
#  NBA
# ══════════════════════════════════════════════════════
def fetch_nba():
    today = datetime.now().strftime("%Y-%m-%d")
    r = requests.get(
        f"{ODDIFY_URL}/rest/v1/nba_predictions_lr",
        params={"select": "*", "game_key": f"like.{today}*"},
        headers=oddify_h(), timeout=15
    )
    data = r.json() if r.status_code==200 else []
    print(f"  NBA: {len(data)} Spiele")
    return data

def proc_nba(games):
    pinnacle = fetch_pinnacle_odds("nba")
    out = []
    for g in games:
        try:
            home = g.get('team_a_abbr') or g.get('team_a_name', '?')
            away = g.get('team_b_abbr') or g.get('team_b_name', '?')
            name = f"{home} vs {away}"

            # Spieldatum aus game_key: "2026-03-21_OKC_WAS" → "21.03.2026"
            game_key = g.get('game_key', '')
            try:
                date_part = game_key.split('_')[0]  # "2026-03-21"
                dt = datetime.strptime(date_part, "%Y-%m-%d")
                game_date = dt.strftime("%d.%m.%Y")
            except Exception:
                game_date = datetime.now().strftime("%d.%m.%Y")
            hws  = float(g.get('team_a_win_prob', 0) or 0) * 100
            aws  = float(g.get('team_b_win_prob', 0) or 0) * 100
            # Abkürzungen zu vollen Namen konvertieren für Pinnacle matching
            home_full = NBA_NAMES.get(home.upper(), home)
            away_full = NBA_NAMES.get(away.upper(), away)
            phq, paq, _ = find_pinnacle_odds(home_full, away_full, pinnacle)
            hq = phq if phq > 1 else float(g.get('home_odds_decimal', 0) or 0)
            aq = paq if paq > 1 else float(g.get('away_odds_decimal', 0) or 0)
            if phq > 1: print(f"    📊 Pinnacle: {home_full} {phq:.2f} | {away_full} {paq:.2f}")
            if hq<=1 and aq<=1: continue
            eh = calc_edge(hws, hq) if hq>1 else -99
            ea = calc_edge(aws, aq) if aq>1 else -99
            if eh>=ea: ws,q,ep,team = hws,hq,eh,home
            else:      ws,q,ep,team = aws,aq,ea,away
            sc,km,rec = calc_score(ep, q, ws)
            st = calc_kelly(ws,q)*KELLY*km*BANKROLL if q>1 else 0
            icon = "🟢" if rec=="WETTEN" else "👁 "
            print(f"  {icon} {name}: {team} {ws:.0f}% q{q:.2f} e{ep:.1f}% → {rec}")
            out.append({"match":name,"team":team,"ws":round(ws,1),"odds":round(q,3),
                "edge":round(ep,2),"impl":round(1/q*100,1) if q>0 else 0,
                "score":sc,"rec":rec,"stake":round(st,2),"sport":"nba","league":"NBA",
                "game_date": game_date,
                "tracking_only":rec in["SKIP","AUTO-SKIP"] or q<=1,
                "is_pick":rec=="WETTEN" and q>1})
        except Exception as e:
            print(f"  ❌ NBA parse error: {e}")
    return out

# ══════════════════════════════════════════════════════
#  FUSSBALL
# ══════════════════════════════════════════════════════
def fetch_soccer():
    now = datetime.now(timezone.utc).isoformat()
    r = requests.get(
        f"{ODDIFY_URL}/rest/v1/soccer_odds",
        params={"select": "id,league,home_team,away_team,commence_time,home_prob,draw_prob,away_prob",
                "commence_time": f"gt.{now}", "order": "commence_time.asc", "limit": "60"},
        headers=oddify_h(), timeout=15
    )
    data = r.json() if r.status_code==200 else []
    print(f"  Fußball: {len(data)} Spiele")
    return data

def proc_soccer(games):
    # Pinnacle Quoten pro Liga einmalig holen
    pinnacle_cache = {}
    out = []
    for g in games:
        try:
            home   = g.get('home_team', '?')
            away   = g.get('away_team', '?')
            name   = f"{home} vs {away}"
            league = g.get('league', '')
            sport_key = normalize_league(league)

            # Spieldatum aus commence_time: "2026-03-22T15:00:00+00:00" → "22.03.2026"
            try:
                ct = g.get('commence_time', '')
                dt = datetime.fromisoformat(ct.replace('Z', '+00:00'))
                game_date = dt.strftime("%d.%m.%Y")
            except Exception:
                game_date = datetime.now().strftime("%d.%m.%Y")
            hp = float(g.get('home_prob', 0) or 0)
            dp = float(g.get('draw_prob', 0) or 0)
            ap = float(g.get('away_prob', 0) or 0)
            if hp<=1: hp*=100; dp*=100; ap*=100

            # Pinnacle Quoten holen (gecacht pro Liga)
            if sport_key not in pinnacle_cache:
                pinnacle_cache[sport_key] = fetch_pinnacle_odds(sport_key)
            pinnacle = pinnacle_cache[sport_key]
            phq, paq, pdq = find_pinnacle_odds(home, away, pinnacle)

            # Edge berechnen wenn Pinnacle Quoten vorhanden
            if phq > 1 or paq > 1:
                print(f"    📊 Pinnacle: {home} {phq:.2f} | {away} {paq:.2f}")
                eh = calc_edge(hp, phq) if phq > 1 else -99
                ea = calc_edge(ap, paq) if paq > 1 else -99
                ed = calc_edge(dp, pdq) if pdq > 1 else -99
                best_edge = max(eh, ea, ed)
                if eh == best_edge:   team, ws, q, edge = home, hp, phq, eh
                elif ea == best_edge: team, ws, q, edge = away, ap, paq, ea
                else:                 team, ws, q, edge = "Draw", dp, pdq, ed
                sc, km, rec = calc_score(edge, q, ws)
                stake = calc_kelly(ws, q) * KELLY * km * BANKROLL if q > 1 else 0
                impl = round(1/q*100, 1) if q > 0 else round(ws, 1)
                tracking = rec in ["SKIP", "AUTO-SKIP"] or q <= 1
                is_pick = rec == "WETTEN" and q > 1
                icon = "🟢" if rec == "WETTEN" else "👁 "
                print(f"  {icon} {name} [{league}]: {team} {ws:.0f}% q{q:.2f} e{edge:.1f}% → {rec}")
            else:
                # Kein Pinnacle → Fallback-Quoten versuchen
                if 'fallback_odds' not in dir():
                    pass  # wird unten geladen
                fallback = fetch_all_soccer_fallback_odds()
                fbh, fba, fbd = find_pinnacle_odds(home, away, fallback)

                if fbh > 1 or fba > 1:
                    print(f"    📊 Fallback-Quote: {home} {fbh:.2f} | {away} {fba:.2f}")
                    eh = calc_edge(hp, fbh) if fbh > 1 else -99
                    ea = calc_edge(ap, fba) if fba > 1 else -99
                    ed = calc_edge(dp, fbd) if fbd > 1 else -99
                    best_edge = max(eh, ea, ed)
                    if eh == best_edge:   team, ws, q, edge = home, hp, fbh, eh
                    elif ea == best_edge: team, ws, q, edge = away, ap, fba, ea
                    else:                 team, ws, q, edge = "Draw", dp, fbd, ed
                    sc, km, rec = calc_score(edge, q, ws)
                    stake = calc_kelly(ws, q) * KELLY * km * BANKROLL if q > 1 else 0
                    impl = round(1/q*100, 1) if q > 0 else round(ws, 1)
                    tracking = rec in ["SKIP", "AUTO-SKIP"] or q <= 1
                    is_pick = rec == "WETTEN" and q > 1
                    icon = "🟢" if rec == "WETTEN" else "👁 "
                    print(f"  {icon} {name} [{league}]: {team} {ws:.0f}% q{q:.2f} e{edge:.1f}% → {rec} (Fallback)")
                else:
                    # Wirklich keine Quoten verfügbar
                    if hp>=ap and hp>=dp: team,ws = home,hp
                    elif ap>=hp and ap>=dp: team,ws = away,ap
                    else: team,ws = "Draw",dp
                    q, edge, sc, km, rec, stake, impl = 0, 0, 0, 0, "TRACK", 0, round(ws,1)
                    tracking, is_pick = True, False
                    print(f"  👁  {name} [{league}]: H{hp:.0f}% D{dp:.0f}% A{ap:.0f}% (kein Pinnacle, kein Fallback)")

            out.append({"match":name,"team":team,"ws":round(ws,1),"odds":round(q,3),
                "edge":round(edge,2),"impl":impl,"score":sc,"rec":rec,"stake":round(stake,2),
                "sport":sport_key,"league":league,"game_date":game_date,
                "tracking_only":tracking,"is_pick":is_pick,
                "ws_home":round(hp,1),"ws_draw":round(dp,1),"ws_away":round(ap,1)})
        except Exception as e:
            print(f"  ❌ Soccer parse error: {e}")
    return out

# ══════════════════════════════════════════════════════
#  TENNIS
# ══════════════════════════════════════════════════════
def fetch_tennis():
    """Holt Tennis aus tennis_predictions Tabelle"""
    # Erst tennis_predictions (hat echte WS%), dann tennis_ai_odds als Fallback
    r = requests.get(
        f"{ODDIFY_URL}/rest/v1/tennis_predictions",
        params={"select": "*", "order": "updated_at.desc", "limit": "60"},
        headers=oddify_h(), timeout=15
    )
    if r.status_code == 200 and r.json():
        data = r.json()
        print(f"  Tennis: {len(data)} Spiele (tennis_predictions)")
        if data: print(f"  Felder: {list(data[0].keys())}")
        return data, "predictions"
    # Fallback
    r2 = requests.get(
        f"{ODDIFY_URL}/rest/v1/tennis_ai_odds",
        params={"select": "*", "order": "commence_time.asc", "limit": "60"},
        headers=oddify_h(), timeout=15
    )
    data2 = r2.json() if r2.status_code==200 else []
    print(f"  Tennis: {len(data2)} Spiele (tennis_ai_odds fallback)")
    return data2, "ai_odds"

def proc_tennis(games_tuple):
    games, source = games_tuple
    out = []
    for g in games:
        try:
            if source == "predictions":
                p1 = g.get('p1_name', 'P1')
                p2 = g.get('p2_name', 'P2')
                ws1 = float(g.get('p1_win_prob', 0) or 0) * 100
                ws2 = float(g.get('p2_win_prob', 0) or 0) * 100
                q1 = float(g.get('best_home_odds') or g.get('home_odds') or 0)
                q2 = float(g.get('best_away_odds') or g.get('away_odds') or 0)
            else:
                p1 = g.get('p1_name') or g.get('home_team', 'P1')
                p2 = g.get('p2_name') or g.get('away_team', 'P2')
                q1 = float(g.get('best_home_odds', 0) or 0)
                q2 = float(g.get('best_away_odds', 0) or 0)
                ws1 = ws2 = 0

            # Spieldatum aus commence_time oder updated_at
            try:
                ct = g.get('commence_time') or g.get('updated_at') or ''
                dt = datetime.fromisoformat(ct.replace('Z', '+00:00'))
                game_date = dt.strftime("%d.%m.%Y")
            except Exception:
                game_date = datetime.now().strftime("%d.%m.%Y")

            name = f"{p1} vs {p2}"
            if p1 == 'P1' and p2 == 'P2': continue  # Kein gültiger Eintrag

            # WS% berechnen falls nicht vorhanden
            if ws1 == 0 and ws2 == 0 and q1 > 1 and q2 > 1:
                i1=1/q1; i2=1/q2; tot=i1+i2
                ws1=(i1/tot)*100; ws2=(i2/tot)*100
            elif ws1 == 0 and ws2 == 0:
                continue  # Keine Daten

            # Quoten berechnen falls nicht vorhanden
            if q1 <= 1 and ws1 > 0: q1 = round(100/ws1, 2)
            if q2 <= 1 and ws2 > 0: q2 = round(100/ws2, 2)

            # Pinnacle Quoten bevorzugen
            if not hasattr(proc_tennis, '_pinnacle'):
                proc_tennis._pinnacle = fetch_pinnacle_odds("tennis")
            pq1, pq2, _ = find_pinnacle_odds(p1, p2, proc_tennis._pinnacle)
            if pq1 > 1: q1 = pq1
            if pq2 > 1: q2 = pq2

            e1 = calc_edge(ws1,q1) if q1>1 else -99
            e2 = calc_edge(ws2,q2) if q2>1 else -99
            if e1>=e2: ws,q,ep,player = ws1,q1,e1,p1
            else:      ws,q,ep,player = ws2,q2,e2,p2
            sc,km,rec = calc_score(ep,q,ws)
            st = calc_kelly(ws,q)*KELLY*km*BANKROLL if q>1 else 0
            icon = "🟢" if rec=="WETTEN" else "👁 "
            print(f"  {icon} {name}: {player} {ws:.0f}% q{q:.2f} e{ep:.1f}% → {rec}")
            out.append({"match":name,"team":player,"ws":round(ws,1),"odds":round(q,3),
                "edge":round(ep,2),"impl":round(1/q*100,1) if q>0 else 0,
                "score":sc,"rec":rec,"stake":round(st,2),"sport":"tennis","league":"Tennis",
                "game_date": game_date,
                "tracking_only":rec in["SKIP","AUTO-SKIP"] or q<=1,
                "is_pick":rec=="WETTEN" and q>1})
        except Exception as e:
            print(f"  ❌ Tennis parse error: {e}")
    return out

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    t0 = datetime.now()
    print(f"\n{'═'*55}")
    print(f"TIMELESS AUTO-TRACKER — {t0.strftime('%d.%m.%Y %H:%M')} Uhr")
    print(f"{'═'*55}")

    # 1. Login
    print("\n🔑 Login...")
    token, user_id = login()
    if not token:
        print("❌ Abbruch — kein Token")
        return

    # 2. Daten holen
    all_games = []

    print("\n🏀 NBA")
    all_games.extend(proc_nba(fetch_nba()))

    print("\n⚽ Fußball")
    all_games.extend(proc_soccer(fetch_soccer()))

    print("\n🎾 Tennis")
    all_games.extend(proc_tennis(fetch_tennis()))  # fetch_tennis returns tuple

    # 3. Zusammenfassung
    wetten = [g for g in all_games if g['rec']=='WETTEN']
    print(f"\n{'═'*55}")
    print(f"Gesamt: {len(all_games)} | Wett-Empfehlungen: {len(wetten)}")
    for w in wetten:
        print(f"  🟢 {w['match']}: {w['team']} | {w['odds']:.2f} | {w['edge']:.1f}%")

    # 4. Speichern
    print(f"\n💾 Speichere...")
    saved = 0; skipped = 0

    for g in all_games:
        sport_db = 'nba' if g['sport']=='nba' else 'tennis' if g['sport']=='tennis' else 'football'
        if already_today(token, g['match'], sport_db):
            skipped += 1
            continue
        if save_bet(token, user_id, g):
            saved += 1
        
    dt = (datetime.now()-t0).seconds
    print(f"\n✅ Fertig in {dt}s — {saved} gespeichert, {skipped} übersprungen")
    print(f"{'═'*55}\n")

if __name__ == "__main__":
    main()
