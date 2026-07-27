from flask import Flask, render_template
from src.motor import MotorPreditivo
from src.api_client import buscar_jogos_e_estatisticas, buscar_odds_over15
from src.config import BANCA_INICIAL

app = Flask(__name__)

@app.route('/')
def home():
    robo = MotorPreditivo(media_gols_liga=2.65)
    jogos_do_dia = buscar_jogos_e_estatisticas()
    apostas_valor = []
    
    for jogo in jogos_do_dia:
        xg_casa, xg_fora = robo.calcular_forcas(jogo["gc"], jogo["sc"], jogo["gf"], jogo["sf"])
        prob_real = robo.probabilidade_over_15(xg_casa, xg_fora)
        odd_casa = buscar_odds_over15(jogo["time_casa"], jogo["time_fora"])
        
        if odd_casa:
            prob_implicita = 1 / odd_casa
            if prob_real > prob_implicita:
                kelly = robo.criterio_kelly(prob_real, odd_casa)
                if kelly > 0:
                    apostas_valor.append({
                        "jogo": f"{jogo['time_casa']} vs {jogo['time_fora']}",
                        "odd": odd_casa,
                        "prob": prob_real,
                        "kelly": kelly
                    })

    bilhete = []
    tem_aposta = False

    if len(apostas_valor) >= 3:
        tem_aposta = True
        apostas_valor.sort(key=lambda x: x['kelly'], reverse=True)
        bilhete = apostas_valor[:3]
        odd_final = 1.0
        for aposta in bilhete: odd_final *= aposta['odd']
        kelly_combinado = sum(b['kelly'] for b in bilhete) / 3
        valor_aposta = BANCA_INICIAL * kelly_combinado
    else:
        odd_final = 0
        valor_aposta = 0

    return render_template('index.html', bilhete=bilhete, tem_aposta=tem_aposta, 
                           odd_final=odd_final, valor_aposta=valor_aposta, banca=BANCA_INICIAL)

if __name__ == '__main__':
    app.run(debug=True)
