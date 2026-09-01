from src.api_client import coletar_dados_mercado
from src.bot import selecionar_apostas
from src.config import BANCA_INICIAL, MAX_JOGOS_ENVIO


def main():
    jogos_do_dia, diagnostico = coletar_dados_mercado(com_diagnostico=True)
    apostas_valor = selecionar_apostas(jogos_do_dia)

    print("\n🧮 Iniciando Motor Matemático...\n")
    if apostas_valor:
        bilhete = apostas_valor[:MAX_JOGOS_ENVIO]
        print("\n" + "=" * 60)
        print(f"🚨 {len(bilhete)} SELEÇÃO(ÕES) DE VALOR - OVER 1.5 🚨")
        print("=" * 60)
        for i, aposta in enumerate(bilhete, 1):
            valor_aposta = BANCA_INICIAL * aposta["kelly"]
            print(
                f"{i}. {aposta['jogo']} | Odd: {aposta['odd']:.2f} | "
                f"Prob: {aposta['prob']*100:.1f}% | Edge: {aposta['edge']*100:.1f} p.p. | "
                f"Entrada individual: R$ {valor_aposta:.2f}"
            )
        print("=" * 60)
    else:
        print(f"\nNenhuma aposta de valor (analisados: {len(jogos_do_dia)}).")
        if not jogos_do_dia:
            print(diagnostico.resumo())


if __name__ == "__main__":
    main()
