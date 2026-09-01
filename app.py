from flask import Flask, render_template
from src.api_client import buscar_jogos_e_estatisticas
from src.bot import selecionar_apostas
from src.config import BANCA_INICIAL, MAX_JOGOS_ENVIO

app = Flask(__name__)

@app.route('/')
def home():
    jogos_do_dia = buscar_jogos_e_estatisticas()
    apostas_valor = selecionar_apostas(jogos_do_dia)

    bilhete = []
    tem_aposta = False

    if apostas_valor:
        tem_aposta = True
        bilhete = apostas_valor[:MAX_JOGOS_ENVIO]
        odd_final = 1.0
        for aposta in bilhete: odd_final *= aposta['odd']
        valor_aposta = sum(BANCA_INICIAL * b['kelly'] for b in bilhete)
    else:
        odd_final = 0
        valor_aposta = 0

    return render_template('index.html', bilhete=bilhete, tem_aposta=tem_aposta, 
                           odd_final=odd_final, valor_aposta=valor_aposta, banca=BANCA_INICIAL)

if __name__ == '__main__':
    app.run(debug=True)
