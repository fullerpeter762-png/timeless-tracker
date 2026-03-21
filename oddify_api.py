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
    today   = datetime.now().strftime("%d.%m.%Y")
    sport_db = 'nba' if game['sport']=='nba' else 'tennis' if game['sport']=='tennis' else 'football'

    payload = {
        "user_id":       user_id,
        "match":         game['match'],
        "betteam":       game['team'],
        "date":          today,
        "stake":         game['stake'],
        "odds":          game['odds'],
        "edge":          game['edge'],
        "type":          "spotted" if game['edge']>=4 else "skip",
        "ows":           game['ws'],
        "impl":          game['impl'],
        "sport":         sport_db,
        "result":        "open",
        "note":          f"Auto-Tracker | {game['league']} | {game['rec']}",
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
    out = []
    for g in games:
        try:
            home = g.get('team_a_abbr') or g.get('team_a_name', '?')
            away = g.get('team_b_abbr') or g.get('team_b_name', '?')
            name = f"{home} vs {away}"
            hws  = float(g.get('team_a_win_prob', 0) or 0) * 100
            aws  = float(g.get('team_b_win_prob', 0) or 0) * 100
            hq   = float(g.get('home_odds_decimal', 0) or 0)
            aq   = float(g.get('away_odds_decimal', 0) or 0)
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
    out = []
    for g in games:
        try:
            home   = g.get('home_team', '?')
            away   = g.get('away_team', '?')
            name   = f"{home} vs {away}"
            league = g.get('league', '')
            sport_key = normalize_league(league)
            hp = float(g.get('home_prob', 0) or 0)
            dp = float(g.get('draw_prob', 0) or 0)
            ap = float(g.get('away_prob', 0) or 0)
            if hp<=1: hp*=100; dp*=100; ap*=100
            if hp>=ap and hp>=dp: team,ws = home,hp
            elif ap>=hp and ap>=dp: team,ws = away,ap
            else: team,ws = "Draw",dp
            print(f"  👁  {name} [{league}]: H{hp:.0f}% D{dp:.0f}% A{ap:.0f}%")
            out.append({"match":name,"team":team,"ws":round(ws,1),"odds":0,
                "edge":0,"impl":round(ws,1),"score":0,"rec":"TRACK","stake":0,
                "sport":sport_key,"league":league,"tracking_only":True,"is_pick":False})
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
            # tennis_predictions Felder ermitteln
            if source == "predictions":
                # Zeige erstes Entry komplett beim ersten Mal
                # Korrekte Felder aus tennis_predictions
                # Echte Feldnamen aus tennis_predictions:
                p1 = g.get('p1_name', 'P1')
                p2 = g.get('p2_name', 'P2')
                ws1 = float(g.get('p1_win_prob', 0) or 0) * 100  # Dezimal → Prozent
                ws2 = float(g.get('p2_win_prob', 0) or 0) * 100
                q1 = float(g.get('best_home_odds') or g.get('home_odds') or 0)
                q2 = float(g.get('best_away_odds') or g.get('away_odds') or 0)
            else:
                p1 = g.get('p1_name') or g.get('home_team', 'P1')
                p2 = g.get('p2_name') or g.get('away_team', 'P2')
                q1 = float(g.get('best_home_odds', 0) or 0)
                q2 = float(g.get('best_away_odds', 0) or 0)
                ws1 = ws2 = 0

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
