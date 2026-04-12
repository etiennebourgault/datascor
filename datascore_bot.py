#!/usr/bin/env python3
# DataScore Bot — Notifications Telegram quotidiennes à 12h
# Analyse les matchs du jour, applique l'algorithme double chance
# et envoie les combinés les plus sûrs via Telegram

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import pytz

# ══════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════
TELEGRAM_TOKEN  = os.environ['TELEGRAM_TOKEN']
TELEGRAM_CHAT   = os.environ['TELEGRAM_CHAT_ID']
FOOTBALL_KEY    = os.environ['FOOTBALL_KEY']
BDL_KEY         = os.environ['BDL_KEY']
ODDS_KEY        = os.environ['ODDS_KEY']
ANTHROPIC_KEY   = os.environ['ANTHROPIC_KEY']

PARIS_TZ = pytz.timezone('Europe/Paris')
TODAY    = datetime.now(PARIS_TZ).strftime('%Y-%m-%d')

BANKROLL = 100  # €
CONF_MIN = 68   # Seuil de confiance minimum
COTE_MIN_COMBO = 1.35
COTE_MAX_COMBO = 1.50

# Compétitions football
COMP_CODES = {
    'Ligue 1':         'FL1',
    'Premier League':  'PL',
    'La Liga':         'PD',
    'Serie A':         'SA',
    'Bundesliga':      'BL1',
    'Champions League':'CL',
    'Europa League':   'EL',
}

BDL_PATHS = {
    'Ligue 1':         '/ligue1/v1',
    'Premier League':  '/epl/v2',
    'La Liga':         '/laliga/v1',
    'Serie A':         '/seriea/v1',
    'Bundesliga':      '/bundesliga/v1',
    'Champions League':'/ucl/v1',
}

# ══════════════════════════════════════════════
# HELPERS API
# ══════════════════════════════════════════════
def fetch(url, headers={}):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Erreur fetch {url}: {e}")
        return None

def football_api(path):
    return fetch(f'https://api.football-data.org{path}',
                 {'X-Auth-Token': FOOTBALL_KEY})

def bdl_api(path):
    return fetch(f'https://api.balldontlie.io{path}',
                 {'Authorization': BDL_KEY})

def odds_api(path):
    return fetch(f'https://api.the-odds-api.com{path}&apiKey={ODDS_KEY}')

def espn_api(path):
    return fetch(f'https://site.api.espn.com{path}')

# ══════════════════════════════════════════════
# CHARGEMENT STANDINGS BALLDONTLIE
# ══════════════════════════════════════════════
def load_standings(league):
    path = BDL_PATHS.get(league)
    if not path:
        return {}
    data = bdl_api(f'{path}/standings?season=2025')
    if not data or 'data' not in data:
        return {}
    result = {}
    for t in data['data']:
        gp = t.get('games_played', 1) or 1
        name = t['team']['name'].lower()
        short = (t['team'].get('short_name') or t['team']['name']).lower()
        entry = {
            'rank':          t.get('rank', 99),
            'wins':          t.get('wins', 0),
            'draws':         t.get('draws', 0),
            'losses':        t.get('losses', 0),
            'games_played':  gp,
            'goals_for':     t.get('goals_for', 0),
            'goals_against': t.get('goals_against', 0),
            'win_rate':      round(t.get('wins', 0) / gp * 100),
            'draw_rate':     round(t.get('draws', 0) / gp * 100),
            'loss_rate':     round(t.get('losses', 0) / gp * 100),
            'goals_for_avg': round(t.get('goals_for', 0) / gp, 2),
            'goals_against_avg': round(t.get('goals_against', 0) / gp, 2),
            'clean_sheet_pct': max(0, round((1 - t.get('goals_against', 0) / gp / 1.5) * 100)),
        }
        result[name]  = entry
        result[short] = entry
    return result

def find_team(standings, name):
    if not standings or not name:
        return None
    n = name.lower().strip()
    if n in standings:
        return standings[n]
    for k, v in standings.items():
        if k in n or n in k:
            return v
    return None

# ══════════════════════════════════════════════
# ALGORITHME DOUBLE CHANCE (même que DataScore)
# ══════════════════════════════════════════════
def compute_dc(hs, as_, o1=2.0, on=3.5, o2=3.0):
    gH  = float(hs['goals_for_avg'])     if hs else 1.4
    gA  = float(as_['goals_for_avg'])    if as_ else 1.1
    gcH = float(hs['goals_against_avg']) if hs else 1.2
    gcA = float(as_['goals_against_avg'])if as_ else 1.4
    hWin  = hs['win_rate']   if hs else 45
    hDraw = hs['draw_rate']  if hs else 25
    hLoss = hs['loss_rate']  if hs else 30
    aWin  = as_['win_rate']  if as_ else 35
    aDraw = as_['draw_rate'] if as_ else 25
    aLoss = as_['loss_rate'] if as_ else 40
    hCS   = hs['clean_sheet_pct']  if hs else 30
    aCS   = as_['clean_sheet_pct'] if as_ else 25

    s1X = (hWin*0.30 + hDraw*0.20 + aLoss*0.25
           + (15 if gcA > 1.3 else 8 if gcA > 1.0 else 3)
           + (10 if gH > 1.5 else 5 if gH > 1.2 else 0)
           + (5 if hCS > 40 else 2 if hCS > 25 else 0))

    sX2 = (aWin*0.30 + aDraw*0.20 + hLoss*0.25
           + (15 if gcH > 1.3 else 8 if gcH > 1.0 else 3)
           + (10 if gA > 1.3 else 5 if gA > 1.0 else 0)
           + (5 if aCS > 35 else 2 if aCS > 20 else 0))

    avg_goals = (gH + gA + gcH + gcA) / 2
    over25 = min(round(avg_goals / 3.2 * 100), 92)
    under25 = 100 - over25

    return {
        'dc1X': min(round(s1X), 95),
        'dcX2': min(round(sX2), 95),
        'over25': over25,
        'under25': under25,
        'avg_goals': round(avg_goals, 2),
        'both_attack': gH >= 1.4 and gA >= 1.1,
        'both_defense': gcH <= 1.1 and gcA <= 1.2,
    }

def safety_score(conf, stats, is_home):
    defense = max(0, (1.5 - float(stats['goals_against_avg'])) / 1.5 * 20) if stats else 10
    clean_s = (stats['clean_sheet_pct'] / 100 * 10) if stats else 5
    return round(conf * 0.70 + defense + clean_s)

def round_odd(o):
    return round(o * 100) / 100

# ══════════════════════════════════════════════
# RECHERCHE ABSENCES VIA WEB SEARCH
# ══════════════════════════════════════════════
def search_absences(home, away, league):
    try:
        prompt = f"""Recherche les blessés et suspensions pour le match {home} vs {away} ({league}) du {TODAY}.
Pour chaque équipe, liste les joueurs absents avec leur poste et leur importance (star/titulaire/remplaçant).
Réponds en JSON uniquement, format:
{{"home_absences":[{{"name":"...","position":"...","importance":"star|starter|backup"}}],"away_absences":[...],"source":"..."}}
Si aucune info trouvée, retourne {{"home_absences":[],"away_absences":[],"source":"inconnu"}}"""

        data = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01'
            }
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
            text = ''.join(b.get('text','') for b in resp.get('content',[]) if b.get('type')=='text')
            # Extraire le JSON
            start = text.find('{')
            end   = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
    except Exception as e:
        print(f"Erreur absences {home} vs {away}: {e}")
    return {"home_absences": [], "away_absences": [], "source": "inconnu"}

def absence_penalty(absences):
    """Calcule la pénalité de confiance selon les absences"""
    penalty = 0
    for p in absences:
        imp = p.get('importance','backup')
        if imp == 'star':     penalty += 15
        elif imp == 'starter': penalty += 8
        else:                  penalty += 3
    return penalty

# ══════════════════════════════════════════════
# CHARGEMENT MATCHS
# ══════════════════════════════════════════════
def load_matches():
    matches = []
    standings_cache = {}

    # Précharger les standings
    print("Chargement standings...")
    for league in BDL_PATHS:
        standings_cache[league] = load_standings(league)
        print(f"  {league}: {len(standings_cache[league])} équipes")

    # Charger les cotes
    print("Chargement cotes...")
    odds_map = {}
    for league, sport_key in [
        ('Ligue 1','soccer_france_ligue_one'), ('Premier League','soccer_epl'),
        ('La Liga','soccer_spain_la_liga'), ('Serie A','soccer_italy_serie_a'),
        ('Bundesliga','soccer_germany_bundesliga'),
        ('Champions League','soccer_uefa_champs_league')
    ]:
        data = odds_api(f'/v4/sports/{sport_key}/odds?regions=eu&markets=h2h&oddsFormat=decimal&bookmakers=winamax,betclic,unibet,bet365')
        if not data: continue
        for game in data:
            bm = game.get('bookmakers', [{}])[0] if game.get('bookmakers') else {}
            h2h = next((m for m in bm.get('markets',[]) if m['key']=='h2h'), None)
            if not h2h: continue
            home_odd = next((o['price'] for o in h2h['outcomes'] if o['name']==game['home_team']), None)
            away_odd = next((o['price'] for o in h2h['outcomes'] if o['name']==game['away_team']), None)
            draw_odd = next((o['price'] for o in h2h['outcomes'] if o['name']=='Draw'), None)
            key = (game['home_team']+'|'+game['away_team']).lower()
            odds_map[key] = {'o1': home_odd, 'oN': draw_odd, 'o2': away_odd, 'bookmaker': bm.get('title','')}

    def find_odds(home, away):
        h, a = home.lower(), away.lower()
        for k, v in odds_map.items():
            kh, ka = k.split('|')
            if (kh in h or h in kh) and (ka in a or a in ka):
                return v
        return {}

    # Charger matchs football
    print("Chargement matchs football...")
    for league, code in COMP_CODES.items():
        data = football_api(f'/v4/competitions/{code}/matches?dateFrom={TODAY}&dateTo={TODAY}')
        if not data or 'matches' not in data: continue
        standings = standings_cache.get(league, {})
        for m in data['matches']:
            home = m['homeTeam'].get('shortName') or m['homeTeam']['name']
            away = m['awayTeam'].get('shortName') or m['awayTeam']['name']
            odds = find_odds(m['homeTeam']['name'], m['awayTeam']['name'])
            hs  = find_team(standings, home)
            as_ = find_team(standings, away)
            matches.append({
                'sport': 'football', 'league': league,
                'home': home, 'away': away,
                'home_full': m['homeTeam']['name'],
                'away_full': m['awayTeam']['name'],
                'time': m['utcDate'][11:16],
                'standings_home': hs, 'standings_away': as_,
                'o1': odds.get('o1'), 'oN': odds.get('oN'), 'o2': odds.get('o2'),
                'bookmaker': odds.get('bookmaker',''),
            })

    # Charger matchs NBA via ESPN
    print("Chargement NBA...")
    espn_date = datetime.now(PARIS_TZ).strftime('%Y%m%d')
    nba = espn_api(f'/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}')
    if nba and 'events' in nba:
        for g in nba['events']:
            comp = g.get('competitions', [{}])[0]
            home_c = next((c for c in comp.get('competitors',[]) if c['homeAway']=='home'), None)
            away_c = next((c for c in comp.get('competitors',[]) if c['homeAway']=='away'), None)
            if not home_c or not away_c: continue
            matches.append({
                'sport': 'basket', 'league': 'NBA',
                'home': home_c['team'].get('shortDisplayName') or home_c['team']['name'],
                'away': away_c['team'].get('shortDisplayName') or away_c['team']['name'],
                'home_full': home_c['team']['name'],
                'away_full': away_c['team']['name'],
                'time': comp.get('date','')[-9:-4] or '?',
                'o1': None, 'oN': None, 'o2': None, 'bookmaker': '',
            })

    print(f"Total matchs chargés: {len(matches)}")
    return matches

# ══════════════════════════════════════════════
# GÉNÉRATEUR DE CANDIDATS
# ══════════════════════════════════════════════
def get_candidats(matches):
    candidats = []

    for m in matches:
        if m['sport'] == 'football' and m['o1'] and m['oN'] and m['o2']:
            hs  = m['standings_home']
            as_ = m['standings_away']
            dc  = compute_dc(hs, as_, m['o1'], m['oN'], m['o2'])

            # Double chance 1X
            c1X = round_odd(1/((1/m['o1'])+(1/m['oN'])))
            if 1.20 <= c1X <= 1.60 and dc['dc1X'] >= CONF_MIN:
                s = safety_score(dc['dc1X'], hs, True)
                detail = f"Dom. #{hs['rank']} · {hs['win_rate']}% victoires · {hs['clean_sheet_pct']}% CS" if hs else ''
                candidats.append({
                    'match_id': m['home']+'_'+m['away'],
                    'sport': '⚽', 'home': m['home'], 'away': m['away'],
                    'home_full': m['home_full'], 'away_full': m['away_full'],
                    'league': m['league'], 'time': m['time'],
                    'type': 'Double chance 1X', 'short': '1X',
                    'label': f"{m['home']} ou Nul",
                    'detail': detail,
                    'cote': c1X, 'conf': dc['dc1X'], 'safety': s,
                    'bookmaker': m['bookmaker'],
                })

            # Double chance X2
            cX2 = round_odd(1/((1/m['o2'])+(1/m['oN'])))
            if 1.20 <= cX2 <= 1.60 and dc['dcX2'] >= CONF_MIN:
                s = safety_score(dc['dcX2'], as_, False)
                detail = f"Ext. #{as_['rank']} · {as_['win_rate']}% victoires · {as_['clean_sheet_pct']}% CS" if as_ else ''
                candidats.append({
                    'match_id': m['home']+'_'+m['away']+'_x2',
                    'sport': '⚽', 'home': m['home'], 'away': m['away'],
                    'home_full': m['home_full'], 'away_full': m['away_full'],
                    'league': m['league'], 'time': m['time'],
                    'type': 'Double chance X2', 'short': 'X2',
                    'label': f"Nul ou {m['away']}",
                    'detail': detail,
                    'cote': cX2, 'conf': dc['dcX2'], 'safety': s,
                    'bookmaker': m['bookmaker'],
                })

            # Over 2.5
            if dc['over25'] >= 65 and dc['both_attack']:
                c = round(1.38 + 0.08, 2)
                if 1.20 <= c <= 1.60:
                    s = round(dc['over25'] * 0.70 + 15)
                    candidats.append({
                        'match_id': m['home']+'_'+m['away']+'_ov',
                        'sport': '⚽', 'home': m['home'], 'away': m['away'],
                        'home_full': m['home_full'], 'away_full': m['away_full'],
                        'league': m['league'], 'time': m['time'],
                        'type': 'Over 2,5 buts', 'short': 'O2.5',
                        'label': 'Plus de 2,5 buts',
                        'detail': f"Moy. {dc['avg_goals']} buts/match · Les deux équipes attaquent bien",
                        'cote': c, 'conf': dc['over25'], 'safety': s,
                        'bookmaker': m['bookmaker'],
                    })

            # Under 2.5
            if dc['under25'] >= 65 and dc['both_defense']:
                c = round(1.42, 2)
                if 1.20 <= c <= 1.60:
                    s = round(dc['under25'] * 0.70 + 18)
                    candidats.append({
                        'match_id': m['home']+'_'+m['away']+'_un',
                        'sport': '⚽', 'home': m['home'], 'away': m['away'],
                        'home_full': m['home_full'], 'away_full': m['away_full'],
                        'league': m['league'], 'time': m['time'],
                        'type': 'Under 2,5 buts', 'short': 'U2.5',
                        'label': 'Moins de 2,5 buts',
                        'detail': f"Moy. {dc['avg_goals']} buts/match · Les deux défenses solides",
                        'cote': c, 'conf': dc['under25'], 'safety': s,
                        'bookmaker': m['bookmaker'],
                    })

        # NBA
        elif m['sport'] == 'basket':
            fav = m['home'] if (m['o1'] and m['o2'] and m['o1'] <= m['o2']) else m['away']
            fav_cote = min(m['o1'] or 9, m['o2'] or 9) if m['o1'] and m['o2'] else None

            # Over total points
            nba_conf = 65
            nba_cote = round(1.85, 2)
            if nba_cote <= 1.60:
                s = round(nba_conf * 0.70 + 15)
                candidats.append({
                    'match_id': m['home']+'_'+m['away']+'_nov',
                    'sport': '🏀', 'home': m['home'], 'away': m['away'],
                    'home_full': m['home_full'], 'away_full': m['away_full'],
                    'league': 'NBA', 'time': m['time'],
                    'type': 'NBA Over 215.5 pts', 'short': 'NBA O',
                    'label': 'Total Over 215.5 points',
                    'detail': 'Rythme offensif NBA élevé',
                    'cote': nba_cote, 'conf': nba_conf, 'safety': s,
                    'bookmaker': '',
                })

            # Prop joueur Over 15.5 pts
            if fav_cote and fav_cote <= 1.50:
                prop_cote = round(1.75, 2)
                prop_conf = 67
                if 1.20 <= prop_cote <= 1.60:
                    s = round(prop_conf * 0.70 + 12)
                    candidats.append({
                        'match_id': m['home']+'_'+m['away']+'_prop',
                        'sport': '🏀', 'home': m['home'], 'away': m['away'],
                        'home_full': m['home_full'], 'away_full': m['away_full'],
                        'league': 'NBA', 'time': m['time'],
                        'type': 'NBA Prop joueur', 'short': 'PROP',
                        'label': f'Top scoreur {fav} Over 15.5 pts',
                        'detail': f'{fav} favori ({fav_cote}) · Star de l\'équipe Over 15.5 pts',
                        'cote': prop_cote, 'conf': prop_conf, 'safety': s,
                        'bookmaker': '',
                    })

    return sorted(candidats, key=lambda x: x['safety'], reverse=True)

# ══════════════════════════════════════════════
# GÉNÉRATEUR DE COMBINÉS
# ══════════════════════════════════════════════
def gen_combines(candidats, matches):
    combos = []
    checked_absences = {}

    for i, a in enumerate(candidats):
        for b in candidats[i+1:]:
            # Pas le même match
            base_a = a['match_id'].split('_ov')[0].split('_un')[0].split('_x2')[0].split('_nov')[0].split('_prop')[0]
            base_b = b['match_id'].split('_ov')[0].split('_un')[0].split('_x2')[0].split('_nov')[0].split('_prop')[0]
            if base_a == base_b: continue

            cote_combo = round(a['cote'] * b['cote'], 2)
            if not (COTE_MIN_COMBO <= cote_combo <= COTE_MAX_COMBO): continue

            # Vérifier absences pour les matchs football
            conf_a, conf_b = a['conf'], b['conf']

            for bet, conf_ref in [(a, 'a'), (b, 'b')]:
                if bet['sport'] == '⚽' and bet['match_id'] not in checked_absences:
                    m = next((x for x in matches if x['home'] == bet['home'] and x['away'] == bet['away']), None)
                    if m:
                        absences = search_absences(m['home_full'], m['away_full'], m['league'])
                        penalty = absence_penalty(absences.get('home_absences', []))
                        checked_absences[bet['match_id']] = {'absences': absences, 'penalty': penalty}
                    else:
                        checked_absences[bet['match_id']] = {'absences': {}, 'penalty': 0}

            pen_a = checked_absences.get(a['match_id'], {}).get('penalty', 0)
            pen_b = checked_absences.get(b['match_id'], {}).get('penalty', 0)
            conf_a_adj = max(0, a['conf'] - pen_a)
            conf_b_adj = max(0, b['conf'] - pen_b)

            # Écarter si confiance ajustée trop basse
            if conf_a_adj < CONF_MIN or conf_b_adj < CONF_MIN: continue

            safety_avg = round((a['safety'] - pen_a + b['safety'] - pen_b) / 2)
            combos.append({
                'bet1': a, 'bet2': b,
                'cote_combo': cote_combo,
                'conf_a': conf_a_adj, 'conf_b': conf_b_adj,
                'safety': safety_avg,
                'absences_a': checked_absences.get(a['match_id'], {}).get('absences', {}),
                'absences_b': checked_absences.get(b['match_id'], {}).get('absences', {}),
                'pen_a': pen_a, 'pen_b': pen_b,
            })

    return sorted(combos, key=lambda x: x['safety'], reverse=True)

# ══════════════════════════════════════════════
# FORMATAGE MESSAGE TELEGRAM
# ══════════════════════════════════════════════
def format_absence(absences, team):
    all_abs = absences.get('home_absences', []) + absences.get('away_absences', [])
    if not all_abs: return ''
    parts = []
    for p in all_abs[:3]:
        emoji = '🔴' if p.get('importance')=='star' else '🟡' if p.get('importance')=='starter' else '⚪'
        parts.append(f"{emoji} {p['name']} ({p.get('position','')})")
    return '\n'.join(parts)

def format_message(combos, candidats_count):
    date_str = datetime.now(PARIS_TZ).strftime('%d/%m/%Y')
    lines = [f"📊 *DataScore — Combinés du {date_str}*\n"]

    if not combos:
        lines.append("🛡️ *Pas de combiné assez sûr aujourd'hui*\n")
        lines.append(f"_{candidats_count} paris analysés — aucun ne passe les seuils de sécurité ({CONF_MIN}% de confiance minimum)._\n")
        lines.append("_Mieux vaut ne pas parier que miser sur des paris douteux. À demain !_")
        lines.append(f"\n📋 _Seuil : {CONF_MIN}% conf. min · Cote cible {COTE_MIN_COMBO}→{COTE_MAX_COMBO}_")
        return '\n'.join(lines)

    mise = round(BANKROLL * 0.03, 1)
    for idx, combo in enumerate(combos[:3]):
        a, b = combo['bet1'], combo['bet2']
        safety = combo['safety']
        lock = '🔒' if safety >= 70 else '⚡'
        gain = round(mise * (combo['cote_combo'] - 1), 2)

        lines.append(f"{'⭐ ' if idx==0 else ''}*Combiné #{idx+1}* — {lock} Sécurité {safety}%")
        lines.append(f"{a['sport']} *{a['type']}* · {a['home']} vs {a['away']}")
        lines.append(f"   {a['label']} @ {a['cote']} · {a['league']} {a['time']}")
        if a['detail']:
            lines.append(f"   _{a['detail']}_")
        if combo['pen_a'] > 0:
            lines.append(f"   ⚠️ _Absences détectées −{combo['pen_a']} pts_")
            abs_txt = format_absence(combo['absences_a'], a['home'])
            if abs_txt: lines.append(f"   {abs_txt}")

        lines.append(f"×")

        lines.append(f"{b['sport']} *{b['type']}* · {b['home']} vs {b['away']}")
        lines.append(f"   {b['label']} @ {b['cote']} · {b['league']} {b['time']}")
        if b['detail']:
            lines.append(f"   _{b['detail']}_")
        if combo['pen_b'] > 0:
            lines.append(f"   ⚠️ _Absences détectées −{combo['pen_b']} pts_")
            abs_txt = format_absence(combo['absences_b'], b['home'])
            if abs_txt: lines.append(f"   {abs_txt}")

        bk = a['bookmaker'] or b['bookmaker'] or 'Winamax'
        lines.append(f"💰 *Cote combinée : {combo['cote_combo']}* · Mise : {mise}€ → Gain : +{gain}€")
        lines.append(f"📱 Bookmaker suggéré : {bk}")
        lines.append("")

    lines.append(f"📋 _Seuil : {CONF_MIN}% conf. min · Cote cible {COTE_MIN_COMBO}→{COTE_MAX_COMBO} · Bankroll {BANKROLL}€_")
    lines.append(f"_Vérifiez toujours les absences de dernière minute avant de miser._")
    return '\n'.join(lines)

# ══════════════════════════════════════════════
# ENVOI TELEGRAM
# ══════════════════════════════════════════════
def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = json.dumps({
        'chat_id': TELEGRAM_CHAT,
        'text': message,
        'parse_mode': 'Markdown'
    }).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read())
        print("Telegram:", resp.get('ok'))
        return resp.get('ok')

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
if __name__ == '__main__':
    print(f"DataScore Bot — {TODAY}")
    print("=" * 50)

    matches    = load_matches()
    candidats  = get_candidats(matches)
    print(f"Candidats retenus : {len(candidats)}")

    combos = gen_combines(candidats, matches)
    print(f"Combinés valides : {len(combos)}")

    message = format_message(combos, len(candidats))
    print("\nMessage Telegram:")
    print(message)
    print("\nEnvoi...")
    send_telegram(message)
    print("Done ✓")
