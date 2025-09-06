import requests
import pandas as pd
from datetime import datetime

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

def buscar_jogos_por_data(data, competicoes=[]):
    todos_jogos = []
    for comp_id in competicoes:
        url = f"{BASE_URL}/fixtures?league={comp_id}&season={datetime.now().year}&date={data}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            jogos = response.json().get("response", [])
            for j in jogos:
                todos_jogos.append({
                    "time_casa": j["teams"]["home"]["name"],
                    "time_fora": j["teams"]["away"]["name"],
                    "data": j["fixture"]["date"],
                    "league": j["league"]["name"],
                    "fixture_id": j["fixture"]["id"]
                })
        else:
            print("Erro ao buscar jogos:", response.status_code)
    return pd.DataFrame(todos_jogos)

def buscar_odds(fixture_id):
    """Puxa odds de Over/Under 1.5 gols de um jogo específico"""
    url = f"{BASE_URL}/odds?fixture={fixture_id}&market=Over/Under"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None
    
    odds_data = response.json().get("response", [])
    for bookie in odds_data:
        for market in bookie.get("bookmakers", []):
            for bet in market.get("bets", []):
                if bet["name"] == "Over/Under":
                    for value in bet.get("values", []):
                        if value["value"] == "Over 1.5":
                            return value["odd"]
    return None

def calcular_probabilidade(odd):
    """Converte odd em probabilidade implícita"""
    if odd:
        return round(1 / float(odd), 2)
    return None

def filtrar_jogos_mais_1_5(df, limiar_prob=0.5):
    resultados = []
    for _, row in df.iterrows():
        odd = buscar_odds(row["fixture_id"])
        prob = calcular_probabilidade(odd)
        if prob and prob >= limiar_prob:
            row["prob_mais_1_5"] = prob
            resultados.append(row)
    return pd.DataFrame(resultados)

def executar_varredura_diaria(competicoes, limiar_prob=0.5):
    hoje = datetime.now().strftime("%Y-%m-%d")
    df_jogos = buscar_jogos_por_data(hoje, competicoes)
    df_filtrado = filtrar_jogos_mais_1_5(df_jogos, limiar_prob)
    
    if df_filtrado.empty:
        print("Nenhum jogo hoje com probabilidade de +1.5 gols acima do limite.")
    else:
        print("Jogos com probabilidade de +1.5 gols >= {}:".format(limiar_prob*100))
        print(df_filtrado[["time_casa", "time_fora", "league", "prob_mais_1_5"]])
    
    return df_filtrado

# --------------------------
# Uso diário
# --------------------------
competicoes = [39, 61]  # IDs da Premier League e Serie A
df_resultados = executar_varredura_diaria(competicoes, limiar_prob=0.5)
