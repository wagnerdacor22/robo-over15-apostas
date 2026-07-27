import requests
import datetime
from src.config import API_FOOTBALL_KEY, ODDS_API_KEY

def buscar_jogos_e_estatisticas():
    print("🔍 Buscando jogos do dia na API-Football...")
    url = "https://v3.football.api-sports.io/fixtures"
    hoje = datetime.datetime.now().strftime("%Y-%m-%d")
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"date": hoje, "league": 39, "season": 2023} 
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200: return []
    
    jogos = response.json().get('response', [])
    jogos_analisados = []
    
    for jogo in jogos:
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        id_casa = jogo['teams']['home']['id']
        id_fora = jogo['teams']['away']['id']
        
        url_stats = "https://v3.football.api-sports.io/teams/statistics"
        stats_casa = requests.get(url_stats, headers=headers, params={"league": 39, "season": 2023, "team": id_casa}).json().get('response', {})
        stats_fora = requests.get(url_stats, headers=headers, params={"league": 39, "season": 2023, "team": id_fora}).json().get('response', {})
        
        try:
            # Blindagem: se não tiver dados, pula o time sem quebrar o código
            gc = stats_casa['goals']['for']['average']['all']
            sc = stats_casa['goals']['against']['average']['all']
            gf = stats_fora['goals']['for']['average']['all']
            sf = stats_fora['goals']['against']['average']['all']
            
            if gc and sc and gf and sf:
                jogos_analisados.append({
                    "time_casa": time_casa, "time_fora": time_fora,
                    "gc": gc, "sc": sc, "gf": gf, "sf": sf
                })
        except:
            print(f"⚠️ Dados incompletos para {time_casa} ou {time_fora}. Pulando.")
            continue
            
    return jogos_analisados

def buscar_odds_over15(time_casa, time_fora):
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "totals", "oddsFormat": "decimal"}
    response = requests.get(url, params=params)
    if response.status_code != 200: return None
        
    for partida in response.json():
        if time_casa.lower() in partida['home_team'].lower() and time_fora.lower() in partida['away_team'].lower():
            for bookmaker in partida['bookmakers']:
                for market in bookmaker['markets']:
                    if market['key'] == 'totals':
                        for outcome in market['outcomes']:
                            if outcome['name'] == 'Over' and outcome['point'] == 1.5:
                                return outcome['price']
    return None
