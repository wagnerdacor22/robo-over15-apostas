import datetime as dt
import re
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from src.config import (
    API_FOOTBALL_INTERVALO_SEGUNDOS,
    API_FOOTBALL_KEY,
    API_TIMEOUT,
    DIAS_ANALISE,
    FOOTBALL_DATA_KEY,
    FUSO_HORARIO,
    MAX_JOGOS_POR_LIGA,
    MAX_ODDS_EVENTOS_POR_EXECUCAO,
    MAX_ODDS_EVENTOS_POR_LIGA,
    ODDS_API_KEY,
    ODDS_REGIONS,
)


LIGAS_MONITORADAS = [
    {
        "nome": "Brasileirao",
        "api_id": 71,
        "odds_key": "soccer_brazil_campeonato",
        "football_data_id": "BSA",
        "tipo": "brasil",
        "media_gols": 2.45,
    },
    {
        "nome": "Premier League",
        "api_id": 39,
        "odds_key": "soccer_epl",
        "football_data_id": "PL",
        "tipo": "europa",
        "media_gols": 2.85,
    },
    {
        "nome": "La Liga",
        "api_id": 140,
        "odds_key": "soccer_spain_la_liga",
        "football_data_id": "PD",
        "tipo": "europa",
        "media_gols": 2.55,
    },
    {
        "nome": "Serie A Italia",
        "api_id": 135,
        "odds_key": "soccer_italy_serie_a",
        "football_data_id": "SA",
        "tipo": "europa",
        "media_gols": 2.65,
    },
    {
        "nome": "Bundesliga",
        "api_id": 78,
        "odds_key": "soccer_germany_bundesliga",
        "football_data_id": "BL1",
        "tipo": "europa",
        "media_gols": 3.10,
    },
    {
        "nome": "Ligue 1 Franca",
        "api_id": 61,
        "odds_key": "soccer_france_ligue_one",
        "football_data_id": "FL1",
        "tipo": "europa",
        "media_gols": 2.65,
    },
    {
        "nome": "Champions League",
        "api_id": 2,
        "odds_key": "soccer_uefa_champs_league",
        "football_data_id": "CL",
        "tipo": "europa",
        "media_gols": 3.00,
    },
]


@dataclass
class DiagnosticoColeta:
    inicio: str
    fim: str
    ligas_consultadas: int = 0
    eventos_com_odds: int = 0
    fixtures_encontradas: int = 0
    jogos_com_odds: int = 0
    jogos_com_estatisticas: int = 0
    chamadas_api_football: int = 0
    chamadas_odds: int = 0
    eventos_odds_api: int = 0
    consultas_alternate_totals: int = 0
    chamadas_football_data: int = 0
    quota_api_football: str = "desconhecida"
    quota_odds: str = "desconhecida"
    erros: list[str] = field(default_factory=list)

    def erro(self, fonte: str, mensagem: str):
        mensagem = " ".join(str(mensagem).split())[:300]
        item = f"{fonte}: {mensagem}"
        if item not in self.erros:
            self.erros.append(item)

    def resumo(self, limite_erros=4):
        if self.eventos_com_odds == 0:
            fixtures_resumo = "nao consultados (nenhum evento com odds)"
        elif self.chamadas_football_data > 0 and self.chamadas_api_football == 0:
            fixtures_resumo = "eventos da Odds API + historico Football-Data"
        else:
            fixtures_resumo = str(self.fixtures_encontradas)

        linhas = [
            f"Periodo: {self.inicio} a {self.fim}",
            f"Eventos encontrados na Odds API: {self.eventos_odds_api}",
            f"Consultas de linha Over 1.5: {self.consultas_alternate_totals}",
            f"Com odds Over 1.5: {self.eventos_com_odds} evento(s)",
            f"Fixtures/pareamento: {fixtures_resumo}",
            f"Com estatisticas: {self.jogos_com_estatisticas}",
        ]
        if self.quota_api_football != "desconhecida":
            linhas.append(f"Cota API-Football restante: {self.quota_api_football}")
        if self.quota_odds != "desconhecida":
            linhas.append(f"Cota Odds restante: {self.quota_odds}")
        if self.erros:
            linhas.append("Falhas detectadas:")
            linhas.extend(f"- {erro}" for erro in self.erros[:limite_erros])
        return "\n".join(linhas)


def _fuso(diagnostico=None):
    try:
        return ZoneInfo(FUSO_HORARIO)
    except ZoneInfoNotFoundError:
        if diagnostico:
            diagnostico.erro("configuracao", f"fuso invalido: {FUSO_HORARIO}; usando UTC")
        return dt.timezone.utc


def _janela_de_analise(agora=None):
    fuso = _fuso()
    agora = agora or dt.datetime.now(fuso)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=fuso)
    agora = agora.astimezone(fuso)
    inicio = agora.date()
    fim = inicio + dt.timedelta(days=DIAS_ANALISE - 1)
    inicio_local = dt.datetime.combine(inicio, dt.time.min, tzinfo=fuso)
    fim_local = dt.datetime.combine(fim, dt.time.max, tzinfo=fuso)
    return inicio, fim, inicio_local, fim_local


def _temporada(liga, data):
    if liga["tipo"] == "brasil":
        return data.year
    return data.year if data.month >= 7 else data.year - 1


def _iso_utc(valor):
    """Formata timestamps exatamente como exigido pela The Odds API.

    A API aceita YYYY-MM-DDTHH:MM:SSZ. Usar ``isoformat()`` em um
    datetime criado com ``time.max`` preserva microssegundos
    (ex.: 23:59:59.999999Z), o que faz ``commenceTimeTo`` retornar HTTP 422.
    """
    return valor.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mensagem_payload(payload):
    if not isinstance(payload, dict):
        return "resposta em formato inesperado"
    erros = payload.get("errors")
    if isinstance(erros, dict) and erros:
        return "; ".join(f"{k}: {v}" for k, v in erros.items())
    if isinstance(erros, list) and erros:
        return "; ".join(map(str, erros))
    if isinstance(erros, str) and erros:
        return erros
    return str(payload.get("message") or payload.get("error") or "sem detalhes")


class ApiFootballClient:
    def __init__(self, diagnostico):
        self.diagnostico = diagnostico
        self.ultima_chamada = 0.0
        self.quota_esgotada = False

    def get(self, endpoint, params):
        if self.quota_esgotada:
            return None

        espera = API_FOOTBALL_INTERVALO_SEGUNDOS - (time.monotonic() - self.ultima_chamada)
        if espera > 0:
            time.sleep(espera)

        url = f"https://v3.football.api-sports.io/{endpoint.lstrip('/')}"
        try:
            resposta = requests.get(
                url,
                headers={"x-apisports-key": API_FOOTBALL_KEY},
                params=params,
                timeout=API_TIMEOUT,
            )
            self.ultima_chamada = time.monotonic()
            self.diagnostico.chamadas_api_football += 1
        except requests.RequestException as exc:
            self.diagnostico.erro("API-Football", f"erro de rede: {exc}")
            return None

        restante = resposta.headers.get("x-ratelimit-requests-remaining")
        if restante is not None:
            self.diagnostico.quota_api_football = restante
            if str(restante).isdigit() and int(restante) <= 0:
                self.quota_esgotada = True

        try:
            payload = resposta.json()
        except ValueError:
            self.diagnostico.erro(
                "API-Football", f"HTTP {resposta.status_code} sem JSON valido"
            )
            return None

        if resposta.status_code != 200:
            self.diagnostico.erro(
                "API-Football",
                f"HTTP {resposta.status_code}: {_mensagem_payload(payload)}",
            )
            return None

        erros = payload.get("errors") if isinstance(payload, dict) else None
        if erros:
            self.diagnostico.erro("API-Football", _mensagem_payload(payload))
            return None

        if not isinstance(payload, dict) or "response" not in payload:
            self.diagnostico.erro("API-Football", "campo response ausente")
            return None
        return payload["response"]


class FootballDataClient:
    def __init__(self, diagnostico):
        self.diagnostico = diagnostico
        self.ultima_chamada = 0.0

    def get(self, endpoint, params):
        espera = API_FOOTBALL_INTERVALO_SEGUNDOS - (time.monotonic() - self.ultima_chamada)
        if espera > 0:
            time.sleep(espera)
        try:
            resposta = requests.get(
                f"https://api.football-data.org/v4/{endpoint.lstrip('/')}",
                headers={"X-Auth-Token": FOOTBALL_DATA_KEY},
                params=params,
                timeout=API_TIMEOUT,
            )
            self.ultima_chamada = time.monotonic()
            self.diagnostico.chamadas_football_data += 1
        except requests.RequestException as exc:
            self.diagnostico.erro("Football-Data", f"erro de rede: {exc}")
            return None

        try:
            payload = resposta.json()
        except ValueError:
            payload = {}
        if resposta.status_code != 200:
            self.diagnostico.erro(
                "Football-Data",
                f"HTTP {resposta.status_code}: {_mensagem_payload(payload)}",
            )
            return None
        return payload


_TERMOS_GENERICOS = {
    "fc",
    "cf",
    "sc",
    "ac",
    "afc",
    "sfc",
    "club",
    "football",
    "soccer",
    "de",
    "da",
    "do",
    "dos",
    "das",
    "the",
}

_ALIASES = {
    "man utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "inter milan": "internazionale",
    "inter": "internazionale",
    "psg": "paris saint germain",
    "bayern munich": "bayern munchen",
    "athletic bilbao": "athletic club bilbao",
    "atletico mineiro": "atletico mg",
    "athletico paranaense": "athletico pr",
}


def _normalizar_nome(nome):
    if not nome:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(nome))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())
    limpo = " ".join(limpo.split())
    limpo = _ALIASES.get(limpo, limpo)
    tokens = [t for t in limpo.split() if t not in _TERMOS_GENERICOS]
    return " ".join(tokens)


def _nomes_parecidos(a, b):
    na = _normalizar_nome(a)
    nb = _normalizar_nome(b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    ta, tb = set(na.split()), set(nb.split())
    if ta == tb:
        return True
    if min(len(ta), len(tb)) >= 2:
        cobertura = len(ta & tb) / min(len(ta), len(tb))
        if cobertura >= 0.80:
            return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.84


def _to_float(valor):
    try:
        numero = float(valor)
        return numero if numero >= 0 else None
    except (TypeError, ValueError):
        return None


def _detalhes_over15(partida):
    melhores = []
    for bookmaker in partida.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") not in ("totals", "alternate_totals"):
                continue
            for outcome in market.get("outcomes", []):
                ponto = _to_float(outcome.get("point"))
                preco = _to_float(outcome.get("price"))
                if (
                    str(outcome.get("name", "")).lower() == "over"
                    and ponto is not None
                    and abs(ponto - 1.5) < 0.001
                    and preco is not None
                    and 1.01 < preco < 10.0
                ):
                    melhores.append(
                        {
                            "odd": preco,
                            "bookmaker": bookmaker.get("title")
                            or bookmaker.get("key")
                            or "",
                        }
                    )
    return max(melhores, key=lambda item: item["odd"]) if melhores else None


def _encontrar_evento_odds(time_casa, time_fora, odds_lista):
    for partida in odds_lista:
        home = partida.get("home_team", "")
        away = partida.get("away_team", "")
        direto = _nomes_parecidos(time_casa, home) and _nomes_parecidos(time_fora, away)
        invertido = _nomes_parecidos(time_casa, away) and _nomes_parecidos(time_fora, home)
        if direto or invertido:
            detalhes = _detalhes_over15(partida)
            if detalhes:
                return partida, detalhes
    return None, None


def buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista):
    _, detalhes = _encontrar_evento_odds(time_casa, time_fora, odds_lista)
    return detalhes["odd"] if detalhes else None


def _atualizar_quota_odds(resposta, diagnostico):
    restante = resposta.headers.get("x-requests-remaining")
    if restante is not None:
        diagnostico.quota_odds = restante


def _buscar_eventos_liga(liga, inicio_local, fim_local, diagnostico):
    """Lista eventos sem gastar a cota da The Odds API."""
    url = f"https://api.the-odds-api.com/v4/sports/{liga['odds_key']}/events"
    params = {
        "apiKey": ODDS_API_KEY,
        "dateFormat": "iso",
        "commenceTimeFrom": _iso_utc(inicio_local),
        "commenceTimeTo": _iso_utc(fim_local),
    }
    try:
        resposta = requests.get(url, params=params, timeout=API_TIMEOUT)
    except requests.RequestException as exc:
        diagnostico.erro("The Odds API", f"erro de rede em {liga['nome']}: {exc}")
        return []

    _atualizar_quota_odds(resposta, diagnostico)
    try:
        payload = resposta.json()
    except ValueError:
        payload = {}
    if resposta.status_code != 200:
        diagnostico.erro(
            "The Odds API",
            f"{liga['nome']} eventos HTTP {resposta.status_code}: {_mensagem_payload(payload)}",
        )
        return []
    if not isinstance(payload, list):
        diagnostico.erro("The Odds API", f"resposta de eventos inesperada em {liga['nome']}")
        return []

    payload.sort(key=lambda item: item.get("commence_time", ""))
    diagnostico.eventos_odds_api += len(payload)
    return payload


def _buscar_alternate_totals_evento(liga, evento, diagnostico):
    """Busca linhas alternativas para um evento e extrai especificamente Over 1.5."""
    evento_id = evento.get("id")
    if not evento_id:
        return None
    url = (
        f"https://api.the-odds-api.com/v4/sports/{liga['odds_key']}"
        f"/events/{evento_id}/odds"
    )
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": ODDS_REGIONS,
        "markets": "alternate_totals",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        resposta = requests.get(url, params=params, timeout=API_TIMEOUT)
        diagnostico.chamadas_odds += 1
        diagnostico.consultas_alternate_totals += 1
    except requests.RequestException as exc:
        diagnostico.erro(
            "The Odds API",
            f"erro de rede nas linhas de {evento.get('home_team', '')} x {evento.get('away_team', '')}: {exc}",
        )
        return None

    _atualizar_quota_odds(resposta, diagnostico)
    try:
        payload = resposta.json()
    except ValueError:
        payload = {}
    if resposta.status_code != 200:
        diagnostico.erro(
            "The Odds API",
            f"{liga['nome']} evento {evento_id} HTTP {resposta.status_code}: {_mensagem_payload(payload)}",
        )
        return None
    if not isinstance(payload, dict):
        return None

    detalhes = _detalhes_over15(payload)
    if not detalhes:
        return None
    return payload


def _buscar_odds_liga(liga, inicio_local, fim_local, diagnostico, orcamento):
    if not ODDS_API_KEY:
        return []

    eventos = _buscar_eventos_liga(liga, inicio_local, fim_local, diagnostico)
    if not eventos:
        return []

    com_linha = []
    tentativas_liga = 0
    for evento in eventos:
        if orcamento["tentativas"] >= MAX_ODDS_EVENTOS_POR_EXECUCAO:
            break
        if tentativas_liga >= MAX_ODDS_EVENTOS_POR_LIGA:
            break
        orcamento["tentativas"] += 1
        tentativas_liga += 1
        payload = _buscar_alternate_totals_evento(liga, evento, diagnostico)
        if payload and _detalhes_over15(payload):
            com_linha.append(payload)

    diagnostico.eventos_com_odds += len(com_linha)
    return com_linha


def _media_stats(stats, lado, local):
    goals = stats.get("goals") or {}
    bloco = goals.get(lado) or {}
    medias = bloco.get("average") or {}
    valor_local = _to_float(medias.get(local))
    return valor_local if valor_local is not None else _to_float(medias.get("all"))


def _jogos_stats(stats, local):
    fixtures = stats.get("fixtures") or {}
    played = fixtures.get("played") or {}
    valor = _to_float(played.get(local))
    if valor is None:
        valor = _to_float(played.get("total"))
    return int(valor or 0)


def _stats_time_api_football(client, liga, season, team_id, cache):
    chave = (liga["api_id"], season, team_id)
    if chave not in cache:
        cache[chave] = client.get(
            "teams/statistics",
            {"league": liga["api_id"], "season": season, "team": team_id},
        )
    stats = cache[chave]
    return stats if isinstance(stats, dict) and stats else None


def _coletar_liga_api_football(
    liga, odds_liga, inicio, fim, season, client, diagnostico, stats_cache
):
    fixtures = client.get(
        "fixtures",
        {
            "league": liga["api_id"],
            "season": season,
            "from": inicio.isoformat(),
            "to": fim.isoformat(),
            "timezone": FUSO_HORARIO,
        },
    )
    if not isinstance(fixtures, list):
        return []
    diagnostico.fixtures_encontradas += len(fixtures)
    fixtures.sort(key=lambda item: (item.get("fixture") or {}).get("date", ""))

    prontos = []
    for fixture in fixtures:
        try:
            status = fixture["fixture"]["status"]["short"]
            if status not in ("NS", "TBD"):
                continue
            casa = fixture["teams"]["home"]
            fora = fixture["teams"]["away"]
            evento, detalhes = _encontrar_evento_odds(casa["name"], fora["name"], odds_liga)
            if not evento or not detalhes:
                continue
            diagnostico.jogos_com_odds += 1

            stats_casa = _stats_time_api_football(
                client, liga, season, casa["id"], stats_cache
            )
            stats_fora = _stats_time_api_football(
                client, liga, season, fora["id"], stats_cache
            )
            if not stats_casa or not stats_fora:
                continue

            gc = _media_stats(stats_casa, "for", "home")
            sc = _media_stats(stats_casa, "against", "home")
            gf = _media_stats(stats_fora, "for", "away")
            sf = _media_stats(stats_fora, "against", "away")
            if None in (gc, sc, gf, sf):
                continue

            amostra_casa = _jogos_stats(stats_casa, "home")
            amostra_fora = _jogos_stats(stats_fora, "away")

            prontos.append(
                {
                    "time_casa": casa["name"],
                    "time_fora": fora["name"],
                    "gc": gc,
                    "sc": sc,
                    "gf": gf,
                    "sf": sf,
                    "odd_over15": detalhes["odd"],
                    "bookmaker": detalhes["bookmaker"],
                    "odds_lista": [evento],
                    "liga": liga["nome"],
                    "media_gols_liga": liga["media_gols"],
                    "fixture_id": fixture["fixture"].get("id"),
                    "data": fixture["fixture"].get("date"),
                    "fonte_stats": "API-Football",
                    "amostra_casa": amostra_casa,
                    "amostra_fora": amostra_fora,
                }
            )
            diagnostico.jogos_com_estatisticas += 1
            if len(prontos) >= MAX_JOGOS_POR_LIGA:
                break
        except (KeyError, TypeError, ValueError) as exc:
            diagnostico.erro("processamento", f"{liga['nome']}: {exc}")
    return prontos


def _acumular_stats_fd(partidas):
    stats = {}

    def time_info(time_obj):
        nome = time_obj.get("name", "")
        chave = _normalizar_nome(nome)
        if chave not in stats:
            stats[chave] = {
                "nome": nome,
                "home_j": 0,
                "home_gf": 0,
                "home_ga": 0,
                "away_j": 0,
                "away_gf": 0,
                "away_ga": 0,
            }
        return stats[chave]

    for partida in partidas:
        if partida.get("status") != "FINISHED":
            continue
        placar = (partida.get("score") or {}).get("fullTime") or {}
        gols_casa = _to_float(placar.get("home"))
        gols_fora = _to_float(placar.get("away"))
        if gols_casa is None or gols_fora is None:
            continue
        casa = time_info(partida.get("homeTeam") or {})
        fora = time_info(partida.get("awayTeam") or {})
        casa["home_j"] += 1
        casa["home_gf"] += gols_casa
        casa["home_ga"] += gols_fora
        fora["away_j"] += 1
        fora["away_gf"] += gols_fora
        fora["away_ga"] += gols_casa
    return stats


def _encontrar_stats_fd(nome, stats):
    chave = _normalizar_nome(nome)
    if chave in stats:
        return stats[chave]
    for candidato in stats.values():
        if _nomes_parecidos(nome, candidato["nome"]):
            return candidato
    return None


def _media_fd(time_stats, campo_local, campo_outro, jogos_local, jogos_outro):
    if time_stats[jogos_local] > 0:
        return time_stats[campo_local] / time_stats[jogos_local]
    total_jogos = time_stats[jogos_local] + time_stats[jogos_outro]
    if total_jogos <= 0:
        return None
    return (time_stats[campo_local] + time_stats[campo_outro]) / total_jogos


def _coletar_liga_football_data(liga, odds_liga, season, client, diagnostico):
    payload = client.get(
        f"competitions/{liga['football_data_id']}/matches",
        {"season": season, "status": "FINISHED"},
    )
    if not isinstance(payload, dict):
        return []
    partidas = payload.get("matches") or []
    stats = _acumular_stats_fd(partidas)
    if not stats:
        diagnostico.erro("Football-Data", f"sem historico para {liga['nome']} {season}")
        return []

    prontos = []
    for evento in odds_liga:
        casa_nome = evento.get("home_team", "")
        fora_nome = evento.get("away_team", "")
        detalhes = _detalhes_over15(evento)
        casa = _encontrar_stats_fd(casa_nome, stats)
        fora = _encontrar_stats_fd(fora_nome, stats)
        if not detalhes or not casa or not fora:
            continue

        gc = _media_fd(casa, "home_gf", "away_gf", "home_j", "away_j")
        sc = _media_fd(casa, "home_ga", "away_ga", "home_j", "away_j")
        gf = _media_fd(fora, "away_gf", "home_gf", "away_j", "home_j")
        sf = _media_fd(fora, "away_ga", "home_ga", "away_j", "home_j")
        if None in (gc, sc, gf, sf):
            continue
        prontos.append(
            {
                "time_casa": casa_nome,
                "time_fora": fora_nome,
                "gc": gc,
                "sc": sc,
                "gf": gf,
                "sf": sf,
                "odd_over15": detalhes["odd"],
                "bookmaker": detalhes["bookmaker"],
                "odds_lista": [evento],
                "liga": liga["nome"],
                "media_gols_liga": liga["media_gols"],
                "fixture_id": evento.get("id"),
                "data": evento.get("commence_time"),
                "fonte_stats": "Football-Data",
                "amostra_casa": casa["home_j"],
                "amostra_fora": fora["away_j"],
            }
        )
        diagnostico.jogos_com_estatisticas += 1
        if len(prontos) >= MAX_JOGOS_POR_LIGA:
            break
    return prontos


def coletar_dados_mercado(com_diagnostico=False, agora=None):
    inicio, fim, inicio_local, fim_local = _janela_de_analise(agora)
    diagnostico = DiagnosticoColeta(inicio.isoformat(), fim.isoformat())
    jogos_analisados = []

    if not ODDS_API_KEY:
        diagnostico.erro("configuracao", "ODDS_API_KEY ausente")
    if not API_FOOTBALL_KEY and not FOOTBALL_DATA_KEY:
        diagnostico.erro(
            "configuracao",
            "API_FOOTBALL_KEY e FOOTBALL_DATA_KEY ausentes; nao ha fonte de estatisticas",
        )
    if diagnostico.erros:
        return (jogos_analisados, diagnostico) if com_diagnostico else jogos_analisados

    api_client = ApiFootballClient(diagnostico) if API_FOOTBALL_KEY else None
    fd_client = FootballDataClient(diagnostico) if FOOTBALL_DATA_KEY else None
    stats_cache = {}
    orcamento_odds = {"tentativas": 0}

    print(f"Periodo local ({FUSO_HORARIO}): {inicio} a {fim}")
    for liga in LIGAS_MONITORADAS:
        diagnostico.ligas_consultadas += 1
        print(f"\nVerificando {liga['nome']}...")
        odds_liga = _buscar_odds_liga(
            liga, inicio_local, fim_local, diagnostico, orcamento_odds
        )
        if not odds_liga:
            if orcamento_odds["tentativas"] >= MAX_ODDS_EVENTOS_POR_EXECUCAO:
                print("   Limite seguro de consultas de odds atingido nesta execucao.")
            else:
                print("   Sem evento com linha alternativa Over 1.5 no periodo.")
            continue

        season = _temporada(liga, inicio)
        jogos_liga = []

        # Football-Data.org e a fonte preferida para o plano gratuito: o Free
        # Tier cobre as principais ligas monitoradas e a temporada corrente.
        # A API-Football fica como fallback, pois o plano Free dela pode bloquear
        # temporadas recentes (como 2026).
        if fd_client:
            print("   Buscando historico pela Football-Data...")
            jogos_liga = _coletar_liga_football_data(
                liga, odds_liga, season, fd_client, diagnostico
            )

        if not jogos_liga and api_client:
            if fd_client:
                print("   Football-Data sem dados completos; tentando API-Football...")
            jogos_liga = _coletar_liga_api_football(
                liga,
                odds_liga,
                inicio,
                fim,
                season,
                api_client,
                diagnostico,
                stats_cache,
            )

        if (
            not jogos_liga
            and api_client
            and not fd_client
            and any(
                "free plans do not have access to this season" in erro.lower()
                for erro in diagnostico.erros
            )
        ):
            diagnostico.erro(
                "configuracao",
                "API-Football Free bloqueia a temporada atual; configure o secret "
                "FOOTBALL_DATA_KEY para usar a fonte gratuita suportada pelo robo",
            )

        jogos_analisados.extend(jogos_liga)
        print(f"   {len(jogos_liga)} jogo(s) com odds e estatisticas completas.")

    print("\n" + diagnostico.resumo())
    return (jogos_analisados, diagnostico) if com_diagnostico else jogos_analisados


# Compatibilidade com app.py e chamadas antigas.
def buscar_jogos_e_estatisticas():
    return coletar_dados_mercado()


def buscar_odds_over15(time_casa, time_fora, odds_lista=None):
    if odds_lista is None:
        return None
    return buscar_odds_over15_na_lista(time_casa, time_fora, odds_lista)
