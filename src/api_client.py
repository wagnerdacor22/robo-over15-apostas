import requests
import datetime
from src.config import API_FOOTBALL_KEY, ODDS_API_KEY

# Lista das ligas que o robô vai analisar
LIGAS_MONITORADAS = [
    {"nome": "Brasileirão", "api_id": 71, "odds_key": "soccer_brazil_campeonato", "season": 2026},
    {"nome": "Premier League", "api_id": 39, "odds_key": "soccer_epl", "season": 2025},
    {"nome": "La Liga", "api_id": 140, "odds_key": "soccer_spain_la_liga", "season": 2025},
    {"nome": "Serie A Itália", "api_id": 135, "odds_key": "soccer_italy_serie_a", "season": 2025},
    {"nome": "Bundesliga", "api_id": 78, "odds_key": "soccer_germany_bundesliga", "season": 2025},
    {"nome": "Ligue 1 França", "api_id": 61, "odds_key": "soccer_france_ligue_one", "season": 2025},
    {"nome": "Champions League", "api_id": 2, "odds_key": "soccer_uefa_champs_league", "season": 2026}
]

def coletar_dados_mercado():
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    headers_api = {"x-apisports-key": API_FOOTBALL_KEY}
    
    jogos_analisados = []
    
    for liga in LIGAS_MONITORADAS:
        print(f"🔍 Verificando {liga['nome']}...")
        
        # 1. Busca os jogos da liga hoje
        url_fixtures = "https://v3.football.api-sports.io/fixtures"
        params_fix = {"date": hoje, "league": liga["api_id"], "season": liga["season"]}
        resp_fix = requests.get(url_fixtures, headers=headers_api, params=params_fix)
        
        if resp_fix.status_code != 200: continue
        jogos = resp_fix.json().get('response', [])
        
        if not jogos: continue # Se não tem jogos hoje nessa liga, pula pra próxima
            
        print(f"⚽ {len(jogos)} jogo(s) encontrado(s) na {liga['nome']}. Buscando odds...")

        # 2. Busca as ODDS da liga inteira de uma vez (economiza API)
        url_odds = f"https://api.the-odds-api.com/v4/sports/{liga['odds_key']}/odds/"
        params_odds = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "totals", "oddsFormat": "decimal"}
        resp_odds = requests.get(url_odds, params=params_odds)
        
        odds_da_liga = []
        if resp_odds.status_code == 200:
            odds_da_liga = resp_odds.json()
        else:
            print(f"⚠️ A API de Odds não retornou dados para {liga['nome']}.")

        # 3. Busca estatísticas dos times e salva tudo
        for jogo in jogos:
            time_casa = jogo['teams']['home']['name']
            time_fora = jogo['teams']['away']['name']
            id_casa = jogo['teams']['home']['id']
            id_fora = jogo['teams']['away']['id']
            
            url_stats = "https://v3.football.api-sports.io/teams/statistics"
            stats_casa_req = requests.get(url_stats, headers=headers_api, params={"league": liga["api_id"], "season": liga["season"], "team": id_casa})
            stats_fora_req = requests.get(url_stats, headers=headers_api, params={"league": liga["api_id"], "season": liga["season"], "team": id_fora})
            
            try:
                stats_casa = stats_casa_req.json().get('response', {})
                stats_fora = stats_fora_req.json().get('response', {})
                
                gc = stats_casa['goals']['for']['average']['all']
                sc = stats_casa['goals']['against']['average']['all']
                gf = stats_fora['goals']['for']['average']['all']
                sf = stats_fora['goals']['against']['average']['all']
                
                if gc and sc and gf and sf:
                    jogos_analisados.append({
                        "time_casa": time_casa, "time_fora": time_fora,
                        "gc": gc, "sc": sc, "gf": gf, "sf": sf,
                        "odds_lista": odds_da_liga # Guardamos as odds junto com o jogo
                    })
            except:
                continue
                
    return jogos_analisados

def buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista):
    # Procura a odd do jogo dentro da lista que já baixamos
    for partida in odds_lista:
        if time_casa.lower() in partida['home_team'].lower() and time_fora.lower() in partida['away_team'].lower():
            for bookmaker in partida['bookmakers']:
                for market in bookmaker['markets']:
                    if market['key'] == 'totals':
                        for outcome in market['outcomes']:
                            if outcome['name'] == 'Over' and outcome['point'] == 1.5:
                                return outcome['price']
    return None
