import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.title("Jogos por Campeonato - API Football")

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# Lista de campeonatos mais usados (ID: Nome)
ligas = {
    71: "Brasileirão Série A",
    2: "Champions League",
    39: "Premier League",
    61: "Ligue 1",
    78: "Bundesliga",
    140: "La Liga",
    135: "Serie A (Itália)"
}

# Seleção do campeonato
liga_id = st.selectbox("Escolha o campeonato:", options=list(ligas.keys()), format_func=lambda x: ligas[x])

# Seleção da data
data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
data_formatada = data_selecionada.strftime("%Y-%m-%d")

if st.button("Buscar Jogos"):
    url = f"{BASE_URL}/fixtures?league={liga_id}&season=2025&date={data_formatada}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        jogos = data.get("response", [])

        if jogos:
            lista = []
            for j in jogos:
                fixture = j["fixture"]
                league = j["league"]
                teams = j["teams"]
                goals = j["goals"]

                lista.append({
                    "Data/Hora": fixture["date"],
                    "Liga": league["name"],
                    "Time Casa": teams["home"]["name"],
                    "Time Fora": teams["away"]["name"],
                    "Gols Casa": goals["home"],
                    "Gols Fora": goals["away"],
                    "Status": fixture["status"]["long"]
                })

            df = pd.DataFrame(lista)
            st.dataframe(df)
        else:
            st.info("Nenhum jogo encontrado para esse campeonato nessa data.")
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
