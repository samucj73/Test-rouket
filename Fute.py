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
                    # Placeholder para probabilidade de +1.5 gols
                    "prob_mais_1_5": None
                })
        else:
            print("Erro ao buscar jogos:", response.status_code)
    return pd.DataFrame(todos_jogos)

# Exemplo de uso
competicoes = [39, 61]  # IDs da Premier League e Serie A
hoje = datetime.now().strftime("%Y-%m-%d")
df_jogos = buscar_jogos_por_data(hoje, competicoes)
print(df_jogos)
