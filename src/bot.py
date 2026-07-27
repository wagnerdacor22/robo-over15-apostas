import os
import requests
from src.motor import MotorPreditivo
from src.api_client import coletar_dados_mercado, buscar_odds_over15_na_lista
from src.config import BANCA_INICIAL

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def enviar_telegram(mensagem: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram não configurado. Mensagem que seria enviada:")
        print(mensagem)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Falha ao enviar Telegram: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"⚠️ Erro Telegram: {e}")


def main():
    try:
        enviar_telegram("🤖 Robô iniciado. Analisando múltiplas ligas internacionais. Aguarde...")

        robo = MotorPreditivo(media_gols_liga=2.65)
        jogos_do_dia = coletar_dados_mercado()
        apostas_valor = []

        for jogo in jogos_do_dia:
            xg_casa, xg_fora = robo.calcular_forcas(jogo["gc"], jogo["sc"], jogo["gf"], jogo["sf"])
            prob_real = robo.probabilidade_over_15(xg_casa, xg_fora)

            odd_casa = buscar_odds_over15_na_lista(
                jogo["time_casa"], jogo["time_fora"], jogo.get("odds_lista", [])
            )

            if not odd_casa:
                print(f"   ℹ️ Sem odd Over 1.5 para {jogo['time_casa']} vs {jogo['time_fora']}")
                continue

            prob_implicita = 1.0 / odd_casa
            if prob_real > prob_implicita:
                kelly = robo.criterio_kelly(prob_real, odd_casa)
                if kelly > 0:
                    apostas_valor.append({
                        "jogo": f"{jogo['time_casa']} vs {jogo['time_fora']}",
                        "odd": odd_casa,
                        "prob": prob_real,
                        "kelly": kelly,
                        "liga": jogo.get("liga", ""),
                    })
                    print(
                        f"   💰 VALOR: {jogo['time_casa']} vs {jogo['time_fora']} | "
                        f"Odd {odd_casa:.2f} | Prob {prob_real*100:.1f}% | Kelly {kelly*100:.2f}%"
                    )

        if len(apostas_valor) >= 3:
            # Ordena pelo Kelly (mais valor primeiro)
            apostas_valor.sort(key=lambda x: x["kelly"], reverse=True)
            bilhete = apostas_valor[:3]
            odd_final = 1.0
            for aposta in bilhete:
                odd_final *= aposta["odd"]

            kelly_medio = sum(b["kelly"] for b in bilhete) / 3
            valor_aposta = BANCA_INICIAL * kelly_medio

            mensagem = "🚨 <b>ALERTA DE APOSTA DE VALOR - OVER 1.5 GOLS</b> 🚨\n\n"
            for i, aposta in enumerate(bilhete, 1):
                mensagem += f"⚽ <b>Jogo {i}:</b> {aposta['jogo']}\n"
                mensagem += f"📈 Odd: {aposta['odd']:.2f} | Prob: {aposta['prob']*100:.1f}%\n"
                if aposta.get("liga"):
                    mensagem += f"🏆 {aposta['liga']}\n"
                mensagem += "\n"

            mensagem += f"💵 <b>Odd Final do Bilhete:</b> {odd_final:.2f}\n"
            mensagem += f"📌 <b>Apostar:</b> R$ {valor_aposta:.2f}\n"
            mensagem += f"💰 <b>Banca:</b> R$ {BANCA_INICIAL:.2f}\n"

            enviar_telegram(mensagem)
        else:
            enviar_telegram(
                f"❌ O robô varreu todas as ligas, analisou {len(jogos_do_dia)} jogos, "
                f"mas não encontrou 3 partidas com valor matemático para Over 1.5 hoje."
            )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        enviar_telegram(f"⚠️ <b>O Robô deu um erro e travou:</b>\n\n{str(e)}")


if __name__ == "__main__":
    main()
