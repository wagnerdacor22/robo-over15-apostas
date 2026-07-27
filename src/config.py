import os
from dotenv import load_dotenv

load_dotenv() # Carrega o arquivo .env

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BANCA_INICIAL = float(os.getenv("BANCA_INICIAL", 1000.0))
