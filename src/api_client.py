import requests
import datetime
import re
import unicodedata
from src.config import API_FOOTBALL_KEY, ODDS_API_KEY

# Usa UTC para a data da API (evita problemas de fuso horário)
from datetime import timezone
agora_utc = datetime.datetime.now(timezone.utc)

hoje = agora_utc.strftime("%Y-%m-%d")
ano_atual = agora_utc.year
mes_atual = agora_utc.month

# Temporada europeia: começa em agosto (mês 8)
# Em julho/2026 ainda estamos na temporada 2025/26 → season = 2025
# A partir de agosto → tentamos season = ano_atual, mas com fallback para ano anterior
# se não houver jogos (temporada nova pode não ter começado ainda)
if mes_atual >= 8:
    temporada_europa_tentativa = ano_atual
else:
    temporada_europa_tentativa = ano_atual - 1

# Brasileirão usa ano calendário, com fallback similar
temporada_brasil_tentativa = ano_atual

LIGAS_MONITORADAS = [
    {"nome": "Brasileirão", "api_id": 71, "odds_key": "soccer_brazil_campeonato", "season": temporada_brasil_tentativa, "tipo": "brasil"},
    {"nome": "Premier League", "api_id": 39, "odds_key": "soccer_epl", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "La Liga", "api_id": 140, "odds_key": "soccer_spain_la_liga", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Serie A Itália", "api_id": 135, "odds_key": "soccer_italy_serie_a", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Bundesliga", "api_id": 78, "odds_key": "soccer_germany_bundesliga", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Ligue 1 França", "api_id": 61, "odds_key": "soccer_france_ligue_one", "season": temporada_europa_tentativa, "tipo": "europa"},
    {"nome": "Champions League", "api_id": 2, "odds_key": "soccer_uefa_champs_league", "season": temporada_europa_tentativa, "tipo": "europa"},
]


def _normalizar_nome(nome: str) -> str:
    """Remove acentos, pontuação e palavras genéricas para matching mais robusto."""
    if not nome:
        return ""
    # Remove acentos
    nfkd = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Minúsculo + só letras/números/espaços
    limpo = re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())
    # Remove palavras comuns que diferem entre APIs
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
    # Um contém o outro (ex: "palmeiras" vs "palmeiras sp")
    if na in nb or nb in na:
        return True
    # Tokens em comum (pelo menos 1 token significativo)
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


def _verificar_temporada_valida(liga_info):
    """
    Testa se a temporada configurada tem jogos na data atual.
    Retorna (bool, int) -> (tem_jogos, temporada_correta).
    """
    if not API_FOOTBALL_KEY:
        return False, liga_info["season"]
    
    headers_api = {"x-apisports-key": API_FOOTBALL_KEY}
    url_fixtures = "https://v3.football.api-sports.io/fixtures"
    
    # Testa temporada atual
    params = {
        "date": hoje,
        "league": liga_info["api_id"],
        "season": liga_info["season"],
    }
    try:
        resp = requests.get(url_fixtures, headers=headers_api, params=params, timeout=20)
        if resp.status_code == 200:
            jogos = resp.json().get("response", [])
            if jogos:
                return True, liga_info["season"]
    except:
        pass
    
    # Se não encontrou, tenta temporada anterior
    season_anterior = liga_info["season"] - 1
    params["season"] = season_anterior
    try:
        resp = requests.get(url_fixtures, headers=headers_api, params=params, timeout=20)
        if resp.status_code == 200:
            jogos = resp.json().get("response", [])
            if jogos:
                print(f"   🔄 Fallback: temporada {liga_info['season']} vazia, usando {season_anterior}")
                return True, season_anterior
    except:
        pass
    
    return False, liga_info["season"]


def coletar_dados_mercado():
    """
    Busca jogos de hoje nas ligas monitoradas + estatísticas + odds de Over 1.5.
    Retorna lista de dicts prontos para o motor preditivo.
    """
    if not API_FOOTBALL_KEY:
        print("❌ API_FOOTBALL_KEY não configurada!")
        return []
    if not ODDS_API_KEY:
        print("⚠️ ODDS_API_KEY não configurada — odds ficarão vazias.")

    headers_api = {"x-apisports-key": API_FOOTBALL_KEY}
    jogos_analisados = []

    print(f"📅 Data usada (UTC): {hoje} | Temporada Europa tentativa: {temporada_europa_tentativa} | Brasil tentativa: {temporada_brasil_tentativa}")

    for liga in LIGAS_MONITORADAS:
        # Verifica se a temporada é válida e ajusta se necessário
        tem_jogos, temporada_correta = _verificar_temporada_valida(liga)
        if not tem_jogos:
            print(f"\n🔍 Verificando {liga['nome']} (Temporada {temporada_correta})...")
            print(f"   ℹ️ Nenhum jogo hoje na {liga['nome']}.")
            continue
        
        # Atualiza a temporada para o loop
        liga["season"] = temporada_correta
        
        print(f"\n🔍 Verificando {liga['nome']} (Temporada {liga['season']})...")

        # 1. Fixtures do dia
        url_fixtures = "https://v3.football.api-sports.io/fixtures"
        params_fix = {
            "date": hoje,
            "league": liga["api_id"],
            "season": liga["season"],
        }
        try:
            resp_fix = requests.get(url_fixtures, headers=headers_api, params=params_fix, timeout=20)
        except requests.RequestException as e:
            print(f"   ⚠️ Erro de rede em fixtures: {e}")
            continue

        if resp_fix.status_code != 200:
            print(f"   ⚠️ Status fixtures: {resp_fix.status_code} → {resp_fix.text[:200]}")
            continue

        jogos = resp_fix.json().get("response", [])
        if not jogos:
            print(f"   ℹ️ Nenhum jogo hoje na {liga['nome']}.")
            continue

        print(f"   ⚽ {len(jogos)} jogo(s) encontrado(s).")

        # 2. Odds da liga (uma chamada só)
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

        # 3. Estatísticas por time
        for jogo in jogos:
            try:
                time_casa = jogo["teams"]["home"]["name"]
                time_fora = jogo["teams"]["away"]["name"]
                id_casa = jogo["teams"]["home"]["id"]
                id_fora = jogo["teams"]["away"]["id"]
                fixture_id = jogo.get("fixture", {}).get("id")
            except (KeyError, TypeError):
                continue

            # Pula jogos já finalizados
            status = (jogo.get("fixture") or {}).get("status", {}).get("short", "")
            if status in ("FT", "AET", "PEN", "CANC", "PST", "ABD"):
                print(f"   ⏭️  {time_casa} vs {time_fora} já finalizado/cancelado ({status})")
                continue

            url_stats = "https://v3.football.api-sports.io/teams/statistics"
            try:
                stats_casa_req = requests.get(
                    url_stats,
                    headers=headers_api,
                    params={"league": liga["api_id"], "season": liga["season"], "team": id_casa},
                    timeout=15,
                )
                stats_fora_req = requests.get(
                    url_stats,
                    headers=headers_api,
                    params={"league": liga["api_id"], "season": liga["season"], "team": id_fora},
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

    print(f"\n📦 Total de jogos com dados completos: {len(jogos_analisados)}")
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

        # Matching nos dois sentidos (às vezes APIs invertem casa/fora em amistosos etc.)
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
    # Retorna a maior odd (melhor preço para o apostador)
    return max(melhores)


# Aliases para compatibilidade com main.py e app.py antigos
def buscar_jogos_e_estatisticas():
    return coletar_dados_mercado()


def buscar_odds_over15(time_casa, time_fora, odds_lista=None):
    """
    Versão compatível. Se odds_lista não for passada, não consegue buscar
    (a API de odds é por liga, não por jogo isolado).
    Prefira usar buscar_odds_over15_na_lista com a lista já coletada.
    """
    if odds_lista is None:
        return None
    return buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista)