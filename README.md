🤖 Robô de Apostas Esportivas - Over 1.5 Gols (Poisson + Kelly)
Este projeto é um robô analítico que utiliza modelagem matemática avançada para identificar Apostas de Valor (Value Bets) no mercado de Over 1.5 Gols (Mais de 1.5 Gols) em partidas de futebol.

🧠 Como funciona?
Coleta de Dados: Busca jogos do dia e estatísticas de equipes via API-Football.
Modelagem Preditiva: Utiliza a Distribuição de Poisson para calcular a probabilidade real de uma partida terminar com 2 ou mais gols, baseando-se na Força de Ataque e Defesa dos times.
Identificação de Valor: Compara a probabilidade real com as Odds oferecidas pelas casas de apostas (via The Odds API).
Gestão de Banca: Aplica o Critério de Kelly fracionado para determinar o valor exato da aposta, visando crescimento sustentável a longo prazo.
⚙️ Configuração
Clone o repositório.
Crie um ambiente virtual: python -m venv venv
Ative o ambiente e instale as dependências: pip install -r requirements.txt
Renomeie o arquivo .env.example para .env e insira suas chaves de API.
Execute o robô: python src/main.py
⚠️ Aviso Legal
Apostas esportivas envolvem risco financeiro. Este software é uma ferramenta analítica para fins educacionais e não garante lucros. Jogue com responsabilidade.

