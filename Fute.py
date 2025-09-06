import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.title("Jogos por Liga - API Football")

# ==========================
# Buscar todas as ligas
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas = [
            {
                "id": l["league"]["id"],
                "nome": l["league"]["name"],
                "pais": l["country"]["name"],
            }
            for l in data
        ]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

ligas = get_ligas()

if ligas:
    df_ligas = pd.DataFrame(ligas)
    st.write(f"✅ Total de ligas disponíveis: {len(df_ligas)}")
    st.dataframe(df_ligas[["id", "nome", "pais"]])

    # ==========================
    # Seleção de liga e data
    # ==========================
    liga_escolhida = st.selectbox(
        "Escolha uma liga pelo nome:",
        options=df_ligas["nome"].unique()
    )

    liga_id = df_ligas[df_ligas["nome"] == liga_escolhida]["id"].values[0]

    data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("Buscar Jogos"):
        url = f"{BASE_URL}/fixtures?date={data_formatada}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()["response"]

            if data:
                # Filtrar só os jogos da liga escolhida
                data_filtrada = [j for j in data if j["league"]["id"] == int(liga_id)]

                if data_filtrada:
                    lista = []
                    for j in data_filtrada:
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

                    df_jogos = pd.DataFrame(lista)
                    st.dataframe(df_jogos)
                else:
                    st.warning("⚠️ Não há jogos dessa liga na data selecionada.")
            else:
                st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
