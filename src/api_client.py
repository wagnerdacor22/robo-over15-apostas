import requests
import datetime
import re
import unicodedata
from src.config import API_FOOTBALL_KEY, ODDS_API_KEY, FOOTBALL_DATA_KEY

# Usa UTC para a data da API (evita problemas de fuso horário)
from datetime import timezone, timedelta
agora_utc = datetime.datetime.now(timezone.utc)

hoje = agora_utc.strftime("%Y-%m-%d")
ano_atual = agora_utc.year
mes_atual = agora_utc.month

# Temporada europeia: começa em agosto (mês 8)
if mes_atual >= 8:
    temporada_europa_tentativa = ano_atual
else:
    temporada_europa_tentativa = ano_atual - 1

# Brasileirão usa ano calendário
temporada_brasil_tentativa = ano_atual

LIGAS_MONITORADAS = [
    {"nome": "Brasileirão", "api_id": 71, "odds_key": "soccer_brazil_campeonato", "football_data_id": "BSA", "season": temporada_brasil_tentativa, "tipo": "brasil"},
    {"nome": "Premier League", "api_id": 39, "odds_key": "soccer_epl", "football_data_id": "PL", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "La Liga", "api_id": 140, "odds_key": "soccer_spain_la_liga", "football_data_id": "PD", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Serie A Itália", "api_id": 135, "odds_key": "soccer_italy_serie_a", "football_data_id": "SA", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Bundesliga", "api_id": 78, "odds_key": "soccer_germany_bundesliga", "football_data_id": "BL1", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Ligue 1 França", "api_id": 61, "odds_key": "soccer_france_ligue_one", "football_data_id": "FL1", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Champions League", "api_id": 2, "odds_key": "soccer_uefa_champs_league", "football_data_id": "CL", "season": temporada_europa_tentativa, "tipo": "europa"},
]

# Mapeamento de IDs de times da Football-Data.org para API-Football
# (usado para buscar estatísticas na API-Football)
TIMES_FOOTBALL_DATA_PARA_API = {
    # Premier League
    57: 42,   # Arsenal
    58: 66,   # Aston Villa
    61: 49,   # Chelsea
    62: 48,   # Everton
    63: 41,   # Fulham
    64: 40,   # Liverpool
    65: 50,   # Manchester City
    66: 33,   # Manchester United
    67: 34,   # Newcastle
    73: 46,   # Southampton
    76: 47,   # Tottenham
    # La Liga
    77: 531,  # Athletic Club
    78: 541,  # Barcelona
    79: 534,  # Betis
    81: 543,  # Atletico Madrid
    82: 536,  # Getafe
    86: 542,  # Real Madrid
    87: 538,  # Real Sociedad
    89: 548,  # Real Valladolid
    90: 533,  # Sevilla
    92: 540,  # Valencia
    94: 537,  # Villarreal
    # Serie A
    98: 505,  # AC Milan
    99: 497,  # AS Roma
    100: 487,  # Atalanta
    102: 496,  # Bologna
    103: 489,  # Cagliari
    104: 511,  # Empoli
    107: 494,  # Genoa
    108: 504,  # Inter
    109: 493,  # Juventus
    110: 490,  # Lazio
    112: 500,  # Napoli
    113: 495,  # Parma
    115: 503,  # Torino
    # Bundesliga
    1: 157,   # Bayern Munich
    2: 165,   # Borussia Dortmund
    3: 169,   # Bayer Leverkusen
    4: 170,   # RB Leipzig
    5: 163,   # Borussia M.Gladbach
    10: 168,  # Stuttgart
    11: 182,  # Wolfsburg
    12: 167,  # Hoffenheim
    15: 178,  # Mainz
    16: 162,  # Werder Bremen
    17: 180,  # Augsburg
    18: 174,  # Freiburg
    19: 176,  # Union Berlin
    20: 177,  # Eintracht Frankfurt
    28: 185,  # St. Pauli
    36: 179,  # Bochum
    44: 186,  # Heidenheim
    55: 183,  # Holstein Kiel
    # Ligue 1
    511: 82,  # Angers
    516: 79,   # Marseille
    518: 93,   # Montpellier
    521: 80,   # Lille
    522: 84,   # Nice
    523: 81,   # Lyon
    524: 85,   # PSG
    525: 77,   # Brest
    527: 76,   # Rennes
    528: 95,   # Lens
    529: 78,   # Saint-Etienne
    530: 94,   # Strasbourg
    533: 96,   # Toulouse
    536: 71,   # Auxerre
    541: 111,  # Le Havre
    543: 91,   # Nantes
    545: 106,  # Reims
    546: 75,   # Monaco
    # Champions League (alguns times)
    503: 86,   # Benfica
    504: 83,   # Porto
    559: 85,   # PSG
}


def _normalizar_nome(nome: str) -> str:
    """Remove acentos, pontuação e palavras genéricas para matching mais robusto."""
    if not nome:
        return ""
    nfkd = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())
    lixo = {
        "fc", "cf", "sc", "ac", "as", "ss", "ud", "cd", "rcd", "afc", "sfc",
        "club", "football", "soccer", "de", "da", "do", "dos", "das", "the",
        "united", "city", "town", "athletic", "sporting", "real", "atletico",
        "rj", "sp", "mg", "rs", "pr", "ba", "pe", "ce", "go", "sc", "es",
    }
    tokens = [t for t in limpo.split() if t and t not in lixo]
    return " ".join(tokens)


def _nomes_parecidos(a: str, b: str) -> bool:
    """Verifica se dois nomes de times se referem ao mesmo clube."""
    na = _normalizar_nome(a)
    nb = _normalizar_nome(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    ta = set(na.split())
    tb = set(nb.split())
    comuns = ta & tb
    if comuns and (len(comuns) >= 1 and (len(ta) <= 2 or len(tb) <= 2)):
        return True
    if len(comuns) >= 2:
        return True
    return False


def _to_float(valor):
    """Converte média de gols (string ou número) para float. Retorna None se inválido."""
    if valor is None:
        return None
    try:
        f = float(valor)
        if f < 0:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _buscar_fixtures_football_data(liga_id, headers_fd):
    """
    Busca jogos na Football-Data.org para uma liga específica.
    Retorna lista de jogos no formato padronizado.
    """
    url = f"https://api.football-data.org/v4/competitions/{liga_id}/matches"
    params = {
        "dateFrom": hoje,
        "dateTo": (agora_utc + timedelta(days=7)).strftime("%Y-%m-%d"),
        "status": "SCHEDULED",
    }
    
    try:
        resp = requests.get(url, headers=headers_fd, params=params, timeout=20)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        matches = data.get("matches", [])
        
        jogos_formatados = []
        for match in matches:
            try:
                home_team = match.get("homeTeam", {})
                away_team = match.get("awayTeam", {})
                
                home_name = home_team.get("name", "")
                away_name = away_team.get("name", "")
                home_id = home_team.get("id")
                away_id = away_team.get("id")
                
                # Converter ID da Football-Data.org para ID da API-Football
                api_home_id = TIMES_FOOTBALL_DATA_PARA_API.get(home_id, home_id)
                api_away_id = TIMES_FOOTBALL_DATA_PARA_API.get(away_id, away_id)
                
                utc_date = match.get("utcDate", "")
                
                jogos_formatados.append({
                    "time_casa": home_name,
                    "time_fora": away_name,
                    "id_casa": api_home_id,
                    "id_fora": api_away_id,
                    "fixture_id": match.get("id"),
                    "data": utc_date,
                    "status": "SCHEDULED",
                })
            except Exception:
                continue
        
        return jogos_formatados
        
    except requests.RequestException as e:
        print(f"   ⚠️ Erro Football-Data.org: {e}")
        return []


def _buscar_fixtures_api_football(data, liga_id, season, headers):
    """
    Busca fixtures na API-Football em uma data e temporada específicas.
    Retorna lista de jogos ou [].
    """
    url = "https://v3.football.api-sports.io/fixtures"
    params = {
        "date": data,
        "league": liga_id,
        "season": season,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("response", [])
        return []
    except Exception:
        return []


def coletar_dados_mercado():
    """
    Busca jogos nas ligas monitoradas + estatísticas + odds de Over 1.5.
    Tenta primeiro API-Football, depois Football-Data.org como fallback.
    Retorna lista de dicts prontos para o motor preditivo.
    """
    if not API_FOOTBALL_KEY:
        print("❌ API_FOOTBALL_KEY não configurada!")
        return []
    if not ODDS_API_KEY:
        print("⚠️ ODDS_API_KEY não configurada — odds ficarão vazias.")

    headers_api = {"x-apisports-key": API_FOOTBALL_KEY}
    headers_fd = {"X-Auth-Token": FOOTBALL_DATA_KEY} if FOOTBALL_DATA_KEY else None
    
    jogos_analisados = []

    print(f"📅 Data base (UTC): {hoje}")
    print(f"🏆 Temporadas tentativa → Europa: {temporada_europa_tentativa} | Brasil: {temporada_brasil_tentativa}")
    print(f"📡 Fontes: API-Football (primária) + Football-Data.org (fallback)")
    print("=" * 60)

    for liga in LIGAS_MONITORADAS:
        print(f"\n🔍 Verificando {liga['nome']}...")
        
        jogos_encontrados = []
        data_encontrada = None
        season_encontrada = None
        fonte_usada = ""
        
        # 1. Tentar API-Football (7 dias + 3 temporadas)
        seasons_para_testar = list(dict.fromkeys([
            liga["season"],
            liga["season"] - 1 if liga["season"] > 2020 else None,
            liga["season"] + 1 if liga["season"] < ano_atual + 1 else None,
        ]))
        seasons_para_testar = [s for s in seasons_para_testar if s is not None]
        
        for season in seasons_para_testar:
            for i in range(7):
                data = (agora_utc + timedelta(days=i)).strftime("%Y-%m-%d")
                jogos = _buscar_fixtures_api_football(data, liga["api_id"], season, headers_api)
                if jogos:
                    jogos_encontrados = jogos
                    data_encontrada = data
                    season_encontrada = season
                    fonte_usada = "API-Football"
                    break
            if jogos_encontrados:
                break
        
        # 2. Fallback: Football-Data.org
        if not jogos_encontrados and headers_fd:
            print(f"   🔄 API-Football sem jogos. Tentando Football-Data.org...")
            jogos_fd = _buscar_fixtures_football_data(liga["football_data_id"], headers_fd)
            if jogos_fd:
                # Converter para formato da API-Football
                jogos_convertidos = []
                for jogo_fd in jogos_fd:
                    # Buscar dados complementares na API-Football (se possível)
                    dados_extra = _buscar_fixtures_api_football(
                        jogo_fd["data"][:10] if jogo_fd.get("data") else hoje,
                        liga["api_id"],
                        liga["season"],
                        headers_api
                    )
                    
                    # Tenta encontrar o mesmo jogo na API-Football para pegar IDs corretos
                    match_api = None
                    if dados_extra:
                        for j_api in dados_extra:
                            if (_nomes_parecidos(jogo_fd["time_casa"], j_api["teams"]["home"]["name"]) and
                                _nomes_parecidos(jogo_fd["time_fora"], j_api["teams"]["away"]["name"])):
                                match_api = j_api
                                break
                    
                    if match_api:
                        jogos_convertidos.append(match_api)
                    else:
                        # Cria estrutura mínima compatível
                        jogos_convertidos.append({
                            "teams": {
                                "home": {"id": jogo_fd["id_casa"], "name": jogo_fd["time_casa"]},
                                "away": {"id": jogo_fd["id_fora"], "name": jogo_fd["time_fora"]},
                            },
                            "fixture": {
                                "id": jogo_fd["fixture_id"],
                                "status": {"short": jogo_fd["status"]},
                            },
                        })
                
                if jogos_convertidos:
                    jogos_encontrados = jogos_convertidos
                    data_encontrada = hoje
                    season_encontrada = liga["season"]
                    fonte_usada = "Football-Data.org"
                    print(f"   ✅ Encontrados {len(jogos_encontrados)} jogos via Football-Data.org")
        
        if not jogos_encontrados:
            print(f"   ❌ Nenhum jogo encontrado em nenhuma fonte")
            continue
        
        print(f"   ⚽ {len(jogos_encontrados)} jogo(s) via {fonte_usada} (season {season_encontrada})")
        
        # 2. Odds da liga
        odds_da_liga = []
        if ODDS_API_KEY:
            url_odds = f"https://api.the-odds-api.com/v4/sports/{liga['odds_key']}/odds/"
            params_odds = {
                "apiKey": ODDS_API_KEY,
                "regions": "eu,uk,us",
                "markets": "totals",
                "oddsFormat": "decimal",
            }
            try:
                resp_odds = requests.get(url_odds, params=params_odds, timeout=20)
                if resp_odds.status_code == 200:
                    odds_da_liga = resp_odds.json()
                    print(f"   📊 {len(odds_da_liga)} partidas com odds recebidas.")
                else:
                    print(f"   ⚠️ Status odds: {resp_odds.status_code}")
            except requests.RequestException as e:
                print(f"   ⚠️ Erro de rede em odds: {e}")

        # 3. Estatísticas por time (API-Football)
        for jogo in jogos_encontrados:
            try:
                time_casa = jogo["teams"]["home"]["name"]
                time_fora = jogo["teams"]["away"]["name"]
                id_casa = jogo["teams"]["home"]["id"]
                id_fora = jogo["teams"]["away"]["id"]
                fixture_id = jogo.get("fixture", {}).get("id")
            except (KeyError, TypeError):
                continue

            status = (jogo.get("fixture") or {}).get("status", {}).get("short", "")
            if status in ("FT", "AET", "PEN", "CANC", "PST", "ABD"):
                print(f"   ⏭️  {time_casa} vs {time_fora} já finalizado/cancelado ({status})")
                continue

            url_stats = "https://v3.football.api-sports.io/teams/statistics"
            try:
                stats_casa_req = requests.get(
                    url_stats,
                    headers=headers_api,
                    params={"league": liga["api_id"], "season": season_encontrada, "team": id_casa},
                    timeout=15,
                )
                stats_fora_req = requests.get(
                    url_stats,
                    headers=headers_api,
                    params={"league": liga["api_id"], "season": season_encontrada, "team": id_fora},
                    timeout=15,
                )
            except requests.RequestException:
                continue

            try:
                stats_casa = stats_casa_req.json().get("response") or {}
                stats_fora = stats_fora_req.json().get("response") or {}

                gc = _to_float((stats_casa.get("goals") or {}).get("for", {}).get("average", {}).get("all"))
                sc = _to_float((stats_casa.get("goals") or {}).get("against", {}).get("average", {}).get("all"))
                gf = _to_float((stats_fora.get("goals") or {}).get("for", {}).get("average", {}).get("all"))
                sf = _to_float((stats_fora.get("goals") or {}).get("against", {}).get("average", {}).get("all"))

                if None in (gc, sc, gf, sf):
                    print(f"   ⚠️ Stats incompletas: {time_casa} vs {time_fora}")
                    continue

                jogos_analisados.append({
                    "time_casa": time_casa,
                    "time_fora": time_fora,
                    "gc": gc,
                    "sc": sc,
                    "gf": gf,
                    "sf": sf,
                    "odds_lista": odds_da_liga,
                    "liga": liga["nome"],
                    "fixture_id": fixture_id,
                })
                print(f"   ✅ {time_casa} vs {time_fora} | GC={gc:.2f} SC={sc:.2f} GF={gf:.2f} SF={sf:.2f}")
            except Exception as e:
                print(f"   ⚠️ Erro ao processar stats de {time_casa} vs {time_fora}: {e}")
                continue

    print(f"\n{'='*60}")
    print(f"📦 Total de jogos com dados completos: {len(jogos_analisados)}")
    return jogos_analisados


def buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista):
    """
    Procura a odd de Over 1.5 na lista de odds da The Odds API.
    Usa matching flexível de nomes.
    Retorna o melhor preço (maior odd) encontrado, ou None.
    """
    if not odds_lista:
        return None

    melhores = []

    for partida in odds_lista:
        home = partida.get("home_team", "")
        away = partida.get("away_team", "")

        match_direto = _nomes_parecidos(time_casa, home) and _nomes_parecidos(time_fora, away)
        match_invertido = _nomes_parecidos(time_casa, away) and _nomes_parecidos(time_fora, home)

        if not (match_direto or match_invertido):
            continue

        for bookmaker in partida.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "totals":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == "Over" and float(outcome.get("point", 0)) == 1.5:
                        preco = outcome.get("price")
                        if preco:
                            melhores.append(float(preco))

    if not melhores:
        return None
    return max(melhores)


# Aliases para compatibilidade com main.py e app.py antigos
def buscar_jogos_e_estatisticas():
    return coletar_dados_mercado()


def buscar_odds_over15(time_casa, time_fora, odds_lista=None):
    if odds_lista is None:
        return None
    return buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista)