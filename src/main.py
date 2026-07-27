from src.config import BANCA_INICIAL
from src.motor import MotorPreditivo
from src.api_client import coletar_dados_mercado, buscar_odds_over15_na_lista


def main():
    robo = MotorPreditivo(media_gols_liga=2.65)
    jogos_do_dia = coletar_dados_mercado()
    apostas_valor = []

    print("\n🧮 Iniciando Motor Matemático...\n")
    for jogo in jogos_do_dia:
        xg_casa, xg_fora = robo.calcular_forcas(jogo["gc"], jogo["sc"], jogo["gf"], jogo["sf"])
        prob_real = robo.probabilidade_over_15(xg_casa, xg_fora)
        odd_casa = buscar_odds_over15_na_lista(
            jogo["time_casa"], jogo["time_fora"], jogo.get("odds_lista", [])
        )

        if odd_casa:
            prob_implicita = 1.0 / odd_casa
            if prob_real > prob_implicita:
                kelly = robo.criterio_kelly(prob_real, odd_casa)
                if kelly > 0:
                    apostas_valor.append({
                        "jogo": f"{jogo['time_casa']} vs {jogo['time_fora']}",
                        "odd": odd_casa,
                        "prob": prob_real,
                        "kelly": kelly,
                    })
                    print(
                        f"💰 {jogo['time_casa']} vs {jogo['time_fora']} | "
                        f"Odd {odd_casa:.2f} | Prob {prob_real*100:.1f}% | Kelly {kelly*100:.2f}%"
                    )
            else:
                print(
                    f"   · {jogo['time_casa']} vs {jogo['time_fora']} | "
                    f"Odd {odd_casa:.2f} | Prob {prob_real*100:.1f}% (sem valor)"
                )
        else:
            print(f"   · {jogo['time_casa']} vs {jogo['time_fora']} | sem odd Over 1.5")

    if len(apostas_valor) >= 3:
        apostas_valor.sort(key=lambda x: x["kelly"], reverse=True)
        bilhete = apostas_valor[:3]
        odd_final = 1.0
        for aposta in bilhete:
            odd_final *= aposta["odd"]
        kelly_combinado = sum(b["kelly"] for b in bilhete) / 3
        valor_aposta = BANCA_INICIAL * kelly_combinado

        print("\n" + "=" * 60)
        print("🚨 ALERTA DE APOSTA DE VALOR - OVER 1.5 GOLS 🚨")
        print("=" * 60)
        for i, aposta in enumerate(bilhete, 1):
            print(
                f"{i}. {aposta['jogo']} | Odd: {aposta['odd']:.2f} | "
                f"Prob: {aposta['prob']*100:.1f}% | Kelly: {aposta['kelly']*100:.2f}%"
            )
        print("-" * 60)
        print(f"💵 Odd Final: {odd_final:.2f} | 📌 APOSTAR: R$ {valor_aposta:.2f}")
        print("=" * 60)
    else:
        print(f"\n❌ Não há 3 jogos com valor hoje (analisados: {len(jogos_do_dia)}).")


if __name__ == "__main__":
    main()
