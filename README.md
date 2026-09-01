# Robo Over 1.5 — versao corrigida

O robo cruza estatisticas de futebol com odds de Over 1.5 e envia ao Telegram
somente as selecoes cuja probabilidade estimada supera a probabilidade implicita
da odd por uma margem minima configuravel.

## O que foi corrigido

- A API-Football agora e consultada uma vez por liga e periodo, usando `from` e
  `to`. A versao antiga podia gastar ate 147 chamadas so procurando fixtures.
- Respostas HTTP, o campo `errors` e as cotas restantes das APIs sao exibidos no
  log e no diagnostico enviado ao Telegram. Uma chave invalida ou cota esgotada
  nao aparece mais apenas como "0 jogos".
- O intervalo padrao de 6,2 segundos respeita o limite do plano gratuito da
  API-Football (10 chamadas por minuto).
- A data usa `America/Sao_Paulo`; a mensagem nao mistura mais o dia do Brasil com
  a data UTC.
- O matching de clubes nao remove palavras importantes como `City`, `United`,
  `Real` e `Atletico`.
- O motor agora usa medias do mandante em casa e do visitante fora. A formula
  antiga dividia as medias de cada time pela media total da liga e deprimia a
  probabilidade de Over 1.5.
- Se existir apenas uma ou duas selecoes validas, elas tambem sao enviadas. Nao e
  mais obrigatorio encontrar tres para mostrar alguma coisa.
- Envia um segundo "Bilhete Extra Equilibrado" com duas selecoes somente quando
  ambas passam por filtros mais fortes de probabilidade, vantagem e tamanho de
  amostra. Se nao houver combinacao segura dentro dos criterios, nenhuma
  multipla e forcada.
- As entradas sao tratadas individualmente. O Kelly de partidas isoladas nao e
  aplicado incorretamente a uma multipla.
- `Football-Data.org` pode ser configurada como fonte alternativa de
  estatisticas.

## Configuracao no GitHub

Em **Settings > Secrets and variables > Actions**, crie estes secrets com os
nomes exatamente iguais:

1. `API_FOOTBALL_KEY`
2. `ODDS_API_KEY`
3. `TELEGRAM_TOKEN`
4. `TELEGRAM_CHAT_ID`
5. `BANCA_INICIAL`
6. `FOOTBALL_DATA_KEY` (opcional, mas recomendado)

Depois abra **Actions > Robo Apostas Over 1.5 > Run workflow** para fazer um
teste manual. A execucao agendada ocorre todos os dias as 11h no horario de
Brasilia.

## Execucao local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.bot
```

Preencha o `.env` antes de executar. O arquivo `.env` esta ignorado pelo Git e
nao deve ser enviado ao repositorio.

## Variaveis uteis

| Variavel | Padrao | Funcao |
| --- | ---: | --- |
| `DIAS_ANALISE` | `1` | `1` analisa apenas o dia atual no Brasil |
| `MAX_JOGOS_POR_LIGA` | `8` | Limita consumo de estatisticas por liga |
| `MAX_JOGOS_ENVIO` | `3` | Maximo de selecoes enviadas |
| `MARGEM_VALOR_MINIMA` | `0.03` | Exige 3 pontos percentuais de vantagem |
| `ATIVAR_BILHETE_EXTRA` | `true` | Ativa a tentativa do segundo bilhete |
| `EXTRA_PROB_MINIMA_INDIVIDUAL` | `0.78` | Exige 78% ajustados em cada jogo extra |
| `EXTRA_EDGE_MINIMO` | `0.04` | Exige 4 p.p. de vantagem em cada selecao |
| `EXTRA_ODD_MINIMA` | `1.75` | Odd combinada minima do extra |
| `EXTRA_ODD_MAXIMA` | `2.60` | Impede multiplas excessivamente arriscadas |
| `EXTRA_PROB_MINIMA_COMBINADA` | `0.55` | Chance conjunta estimada minima de 55% |
| `EXTRA_MIN_JOGOS_AMOSTRA` | `4` | Amostra minima casa/fora por time |
| `EXTRA_APOSTA_PCT` | `0.005` | Limite de 0,5% da banca no bilhete extra |
| `API_FOOTBALL_INTERVALO_SEGUNDOS` | `6.2` | Intervalo entre chamadas da API-Football |
| `ODDS_REGIONS` | `eu` | Regiao de bookmakers consultada |

Para olhar hoje e amanha, use `DIAS_ANALISE=2`. Se o seu plano da API-Football
for pago, o intervalo pode ser reduzido de acordo com o limite contratado.

## Como interpretar a mensagem

- **Nenhum jogo chegou ao motor matematico:** houve problema ou ausencia de
  dados na coleta. A propria mensagem passa a mostrar chave ausente, HTTP 401,
  HTTP 429, cota esgotada, liga sem odds ou outra causa detectada.
- **A coleta funcionou, mas nao houve aposta de valor:** os jogos foram
  analisados corretamente, mas nenhum atingiu a margem minima. Isso e normal e
  nao deve ser contornado afrouxando filtros apenas para forcar uma aposta.
- **Selecao de valor:** e uma estimativa do modelo, nao uma garantia de acerto.
  Reconfira horario e odd antes de qualquer entrada.
- **Bilhete extra nao liberado:** os sinais do dia nao atingiram todos os filtros
  reforcados. Esse bloqueio e intencional.
- **Bilhete Extra Equilibrado:** multipla de duas selecoes com odd final entre
  1.75 e 2.60. A probabilidade conjunta e aproximada e pressupoe independencia
  entre as partidas.

## Aviso

Apostas esportivas envolvem risco financeiro. O modelo ainda precisa de
backtest fora da amostra e calibracao por liga antes de ser tratado como base
para dinheiro real. Resultados passados e probabilidades estimadas nao garantem
lucro.
