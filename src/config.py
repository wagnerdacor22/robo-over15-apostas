import os

from dotenv import load_dotenv


load_dotenv()


def _inteiro(nome, padrao, minimo=0):
    try:
        return max(minimo, int(os.getenv(nome, str(padrao))))
    except (TypeError, ValueError):
        return padrao


def _decimal(nome, padrao, minimo=0.0):
    try:
        return max(minimo, float(os.getenv(nome, str(padrao))))
    except (TypeError, ValueError):
        return padrao

# API Keys
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Banca
BANCA_INICIAL = _decimal("BANCA_INICIAL", 1000.0, 0.0)

# Coleta e selecao
FUSO_HORARIO = os.getenv("FUSO_HORARIO", "America/Sao_Paulo")
DIAS_ANALISE = _inteiro("DIAS_ANALISE", 1, 1)
MAX_JOGOS_POR_LIGA = _inteiro("MAX_JOGOS_POR_LIGA", 8, 1)
MAX_JOGOS_ENVIO = _inteiro("MAX_JOGOS_ENVIO", 3, 1)
MARGEM_VALOR_MINIMA = _decimal("MARGEM_VALOR_MINIMA", 0.03, 0.0)

# Bilhete extra: duas selecoes fortes para buscar uma odd combinada maior sem
# transformar o robo em gerador de multiplas longas e muito improvaveis.
ATIVAR_BILHETE_EXTRA = os.getenv("ATIVAR_BILHETE_EXTRA", "true").lower() in {
    "1",
    "true",
    "sim",
    "yes",
}
EXTRA_QTD_JOGOS = _inteiro("EXTRA_QTD_JOGOS", 2, 2)
EXTRA_PROB_MINIMA_INDIVIDUAL = _decimal(
    "EXTRA_PROB_MINIMA_INDIVIDUAL", 0.78, 0.50
)
EXTRA_EDGE_MINIMO = _decimal("EXTRA_EDGE_MINIMO", 0.04, 0.0)
EXTRA_ODD_MINIMA = _decimal("EXTRA_ODD_MINIMA", 1.75, 1.01)
EXTRA_ODD_MAXIMA = _decimal("EXTRA_ODD_MAXIMA", 2.60, EXTRA_ODD_MINIMA)
EXTRA_PROB_MINIMA_COMBINADA = _decimal(
    "EXTRA_PROB_MINIMA_COMBINADA", 0.55, 0.0
)
EXTRA_MIN_JOGOS_AMOSTRA = _inteiro("EXTRA_MIN_JOGOS_AMOSTRA", 4, 1)
EXTRA_APOSTA_PCT = _decimal("EXTRA_APOSTA_PCT", 0.005, 0.0)

# APIs. No plano gratuito da API-Football o intervalo de 6,2 s evita
# estourar o limite documentado de 10 requisicoes por minuto.
API_TIMEOUT = _inteiro("API_TIMEOUT", 25, 5)
API_FOOTBALL_INTERVALO_SEGUNDOS = _decimal(
    "API_FOOTBALL_INTERVALO_SEGUNDOS", 6.2, 0.0
)
ODDS_REGIONS = os.getenv("ODDS_REGIONS", "eu")
