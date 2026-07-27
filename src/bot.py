import os
import requests
from src.motor import MotorPreditivo
from src.api_client import buscar_jogos_e_estatisticas, buscar_odds_over15

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BANCA_INICIAL = 1000.0

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)

def main():
    robo = MotorPreditivo(media_gols_liga=2.65)
    jogos_do_dia = buscar_jogos_e_estatisticas()
    apostas_valor = []
    
    for jogo in jogos_do_dia:
        xg_casa, xg_fora = robo.calcular_forcas(jogo["gc"], jogo["sc"], jogo["gf"], jogo["sf"])
        prob_real = robo.probabilidade_over_15(xg_casa, xg_fora)
        odd_casa = buscar_odds_over15(jogo["time_casa"], jogo["time_fora"])
        
        if odd_casa:
            if prob_real > (1 / odd_casa):
                kelly = robo.criterio_kelly(prob_real, odd_casa)
                if kelly > 0:
                    apostas_valor.append({
                        "jogo": f"{jogo['time_casa']} vs {jogo['time_fora']}",
                        "odd": odd_casa,
                        "prob": prob_real
                    })

    if len(apostas_valor) >= 3:
        apostas_valor.sort(key=lambda x: x['odd'], reverse=True)
        bilhete = apostas_valor[:3]
        odd_final = 1.0
        for aposta in bilhete: odd_final *= aposta['odd']
        
        mensagem = "🚨 <b>ALERTA DE APOSTA DE VALOR - OVER 1.5 GOLS</b> 🚨\n\n"
        for i, aposta in enumerate(bilhete, 1):
            mensagem += f"⚽ <b>Jogo {i}:</b> {aposta['jogo']}\n"
            mensagem += f"📈 Odd: {aposta['odd']} | Prob: {aposta['prob']*100:.1f}%\n\n"
        
        mensagem += f"💵 <b>Odd Final do Bilhete:</b> {odd_final:.2f}\n"
        mensagem += f"💰 <b>Banca:</b> R$ {BANCA_INICIAL:.2f}\n"
        
        enviar_telegram(mensagem)
    else:
        enviar_telegram("❌ O robô analisou o mercado e não encontrou 3 jogos com valor matemático para Over 1.5 hoje.")

if __name__ == "__main__":
    main()
