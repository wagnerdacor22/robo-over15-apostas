import os
from html import escape
from itertools import combinations
from math import prod

import requests

from src.api_client import coletar_dados_mercado
from src.config import (
    ATIVAR_BILHETE_EXTRA,
    BANCA_INICIAL,
    EXTRA_APOSTA_PCT,
    EXTRA_EDGE_MINIMO,
    EXTRA_MIN_JOGOS_AMOSTRA,
    EXTRA_ODD_MAXIMA,
    EXTRA_ODD_MINIMA,
    EXTRA_PROB_MINIMA_COMBINADA,
    EXTRA_PROB_MINIMA_INDIVIDUAL,
    EXTRA_QTD_JOGOS,
    MARGEM_VALOR_MINIMA,
    MAX_JOGOS_ENVIO,
)
from src.motor import MotorPreditivo

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


def selecionar_apostas(jogos_do_dia):
    apostas_valor = []
    for jogo in jogos_do_dia:
        robo = MotorPreditivo(media_gols_liga=jogo.get("media_gols_liga", 2.65))
        xg_casa, xg_fora = robo.calcular_forcas(
            jogo["gc"], jogo["sc"], jogo["gf"], jogo["sf"]
        )
        prob_real = robo.probabilidade_over_15(xg_casa, xg_fora)
        odd_casa = jogo.get("odd_over15")
        if not odd_casa:
            continue

        prob_implicita = 1.0 / odd_casa
        edge = prob_real - prob_implicita
        if edge < MARGEM_VALOR_MINIMA:
            print(
                f"   Sem valor: {jogo['time_casa']} vs {jogo['time_fora']} | "
                f"odd {odd_casa:.2f} | modelo {prob_real*100:.1f}% | edge {edge*100:.1f} p.p."
            )
            continue

        kelly = robo.criterio_kelly(prob_real, odd_casa)
        if kelly <= 0:
            continue
        # Reduz a confianca do modelo aproximando 30% da estimativa da
        # probabilidade implicita do mercado. Nao e calibracao definitiva, mas
        # evita usar a previsao bruta no bilhete extra.
        prob_ajustada = 0.70 * prob_real + 0.30 * prob_implicita
        apostas_valor.append(
            {
                "jogo": f"{jogo['time_casa']} vs {jogo['time_fora']}",
                "odd": odd_casa,
                "prob": prob_real,
                "prob_ajustada": prob_ajustada,
                "edge": edge,
                "kelly": kelly,
                "liga": jogo.get("liga", ""),
                "bookmaker": jogo.get("bookmaker", ""),
                "data": jogo.get("data", ""),
                "xg_total": xg_casa + xg_fora,
                "amostra_casa": int(jogo.get("amostra_casa") or 0),
                "amostra_fora": int(jogo.get("amostra_fora") or 0),
            }
        )

    apostas_valor.sort(key=lambda item: (item["edge"], item["kelly"]), reverse=True)
    return apostas_valor


def montar_bilhete_extra(apostas):
    """Escolhe a multipla mais segura que alcance a faixa de odd desejada."""
    if not ATIVAR_BILHETE_EXTRA:
        return None

    candidatos = [
        aposta
        for aposta in apostas
        if aposta["prob_ajustada"] >= EXTRA_PROB_MINIMA_INDIVIDUAL
        and aposta["edge"] >= EXTRA_EDGE_MINIMO
        and min(aposta["amostra_casa"], aposta["amostra_fora"])
        >= EXTRA_MIN_JOGOS_AMOSTRA
    ]
    if len(candidatos) < EXTRA_QTD_JOGOS:
        return None

    opcoes = []
    for selecoes in combinations(candidatos, EXTRA_QTD_JOGOS):
        odd_final = prod(item["odd"] for item in selecoes)
        prob_combinada = prod(item["prob_ajustada"] for item in selecoes)
        if not (EXTRA_ODD_MINIMA <= odd_final <= EXTRA_ODD_MAXIMA):
            continue
        if prob_combinada < EXTRA_PROB_MINIMA_COMBINADA:
            continue

        ligas_distintas = len({item.get("liga") for item in selecoes})
        opcoes.append(
            {
                "selecoes": list(selecoes),
                "odd_final": odd_final,
                "prob_combinada": prob_combinada,
                # Primeiro privilegia ligas diferentes; depois, maior chance.
                "score": (ligas_distintas, prob_combinada, -odd_final),
            }
        )

    return max(opcoes, key=lambda item: item["score"]) if opcoes else None


def montar_mensagem_apostas(apostas, total_analisado):
    selecionadas = apostas[:MAX_JOGOS_ENVIO]
    qtd = len(selecionadas)
    mensagem = (
        f"✅ <b>{qtd} selecao(oes) de valor - Over 1.5</b>\n"
        f"Analisados com dados completos: {total_analisado}\n\n"
        "🎯 <b>ACAO PRINCIPAL DO ROBO</b>\n"
        f"Faca {qtd} aposta(s) <b>SIMPLES e SEPARADA(S)</b>, uma por jogo, "
        "no mercado <b>Mais de 1.5 gols na partida</b>.\n"
        "❌ <b>Nao junte estas selecoes em uma multipla</b> apenas por aparecerem juntas.\n"
        "Uma multipla so e indicada quando o robo enviar explicitamente "
        "<b>BILHETE EXTRA LIBERADO</b>.\n\n"
    )
    for indice, aposta in enumerate(selecionadas, 1):
        valor = BANCA_INICIAL * aposta["kelly"]
        mensagem += f"⚽ <b>{indice}. {escape(aposta['jogo'])}</b>\n"
        if aposta.get("liga"):
            mensagem += f"🏆 {escape(aposta['liga'])}\n"
        mensagem += (
            "🎯 Mercado: <b>Mais de 1.5 gols na partida</b>\n"
            f"📈 Odd: {aposta['odd']:.2f} | Modelo: {aposta['prob']*100:.1f}%\n"
            f"➕ Vantagem estimada: {aposta['edge']*100:.1f} p.p.\n"
            f"💵 Entrada simples sugerida: R$ {valor:.2f}\n"
        )
        if aposta.get("bookmaker"):
            mensagem += f"🏦 Odd em: {escape(aposta['bookmaker'])}\n"
        mensagem += "\n"
    mensagem += (
        "⚠️ Odds mudam rapidamente. Reconfira antes de apostar. "
        "Estimativa estatistica nao garante resultado."
    )
    return mensagem


def montar_mensagem_bilhete_nao_liberado(apostas):
    """Explica claramente o que fazer quando a multipla extra e recusada."""
    selecionadas = apostas[:MAX_JOGOS_ENVIO]
    linhas = [
        "🛡️ <b>MULTIPLA NAO LIBERADA</b>",
        "",
        "✅ <b>Acao de hoje:</b> mantenha as apostas aprovadas como "
        "<b>SIMPLES e SEPARADAS</b>.",
        "❌ <b>Nao monte um bilhete juntando os jogos abaixo.</b>",
    ]

    for indice, aposta in enumerate(selecionadas, 1):
        valor = BANCA_INICIAL * aposta["kelly"]
        linhas.append(
            f"{indice}) {escape(aposta['jogo'])} — Over 1.5 — R$ {valor:.2f}"
        )

    # Mostra a odd combinada das selecoes exibidas quando ela ajuda a explicar
    # por que nao existe bilhete extra. O filtro oficial continua sendo feito
    # por montar_bilhete_extra(), com todos os criterios de seguranca.
    if len(selecionadas) >= EXTRA_QTD_JOGOS:
        melhor_grupo = selecionadas[:EXTRA_QTD_JOGOS]
        odd_combinada = prod(item["odd"] for item in melhor_grupo)
        linhas.extend(
            [
                "",
                f"ℹ️ Odd combinada destas {EXTRA_QTD_JOGOS} selecoes: "
                f"<b>{odd_combinada:.2f}</b>.",
            ]
        )
        if odd_combinada < EXTRA_ODD_MINIMA:
            linhas.append(
                f"Ela esta abaixo da odd minima de <b>{EXTRA_ODD_MINIMA:.2f}</b> "
                "exigida para o bilhete extra."
            )
        elif odd_combinada > EXTRA_ODD_MAXIMA:
            linhas.append(
                f"Ela esta acima da odd maxima de <b>{EXTRA_ODD_MAXIMA:.2f}</b> "
                "permitida para o bilhete extra."
            )

    linhas.extend(
        [
            "",
            "O bilhete extra so sera enviado quando a combinacao cumprir "
            "simultaneamente probabilidade, vantagem, amostra e faixa de odd.",
        ]
    )
    return "\n".join(linhas)


def montar_mensagem_bilhete_extra(bilhete):
    valor = BANCA_INICIAL * EXTRA_APOSTA_PCT
    retorno_bruto = valor * bilhete["odd_final"]
    mensagem = (
        "🔥 <b>BILHETE EXTRA EQUILIBRADO</b>\n"
        "Somente sinais de maior confianca\n\n"
    )
    for indice, aposta in enumerate(bilhete["selecoes"], 1):
        mensagem += (
            f"⚽ <b>{indice}. {escape(aposta['jogo'])}</b>\n"
            f"📈 Odd: {aposta['odd']:.2f} | "
            f"Prob. ajustada: {aposta['prob_ajustada']*100:.1f}%\n"
            f"📊 Amostra casa/fora: {aposta['amostra_casa']}/{aposta['amostra_fora']} jogos\n\n"
        )

    mensagem += (
        f"🎯 <b>Odd combinada:</b> {bilhete['odd_final']:.2f}\n"
        f"🧮 <b>Probabilidade conjunta estimada:</b> "
        f"{bilhete['prob_combinada']*100:.1f}%\n"
        f"💵 <b>Entrada maxima:</b> R$ {valor:.2f} "
        f"({EXTRA_APOSTA_PCT*100:.1f}% da banca)\n"
        f"💰 <b>Retorno bruto potencial:</b> R$ {retorno_bruto:.2f}\n\n"
        "⚠️ A probabilidade conjunta pressupoe independencia entre jogos e "
        "nao representa garantia de acerto."
    )
    return mensagem


def main():
    try:
        enviar_telegram("🤖 Robô iniciado. Analisando múltiplas ligas internacionais. Aguarde...")

        jogos_do_dia, diagnostico = coletar_dados_mercado(com_diagnostico=True)
        apostas_valor = selecionar_apostas(jogos_do_dia)

        if apostas_valor:
            enviar_telegram(montar_mensagem_apostas(apostas_valor, len(jogos_do_dia)))
            bilhete_extra = montar_bilhete_extra(apostas_valor)
            if bilhete_extra:
                enviar_telegram(montar_mensagem_bilhete_extra(bilhete_extra))
            elif ATIVAR_BILHETE_EXTRA:
                enviar_telegram(montar_mensagem_bilhete_nao_liberado(apostas_valor))
        elif jogos_do_dia:
            enviar_telegram(
                "ℹ️ <b>A coleta funcionou, mas nao houve aposta de valor.</b>\n\n"
                f"Foram analisados {len(jogos_do_dia)} jogo(s) com odds e estatisticas. "
                f"Nenhum superou a probabilidade implicita por pelo menos "
                f"{MARGEM_VALOR_MINIMA*100:.1f} pontos percentuais.\n\n"
                "Isso e diferente de falha na coleta e pode ser um resultado normal."
            )
        else:
            enviar_telegram(
                "❌ <b>Nenhum jogo chegou ao motor matematico.</b>\n\n"
                f"<pre>{escape(diagnostico.resumo())}</pre>\n\n"
                "Confira no GitHub Actions a falha indicada acima."
            )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        enviar_telegram(f"⚠️ <b>O Robô deu um erro e travou:</b>\n\n{str(e)}")


if __name__ == "__main__":
    main()
