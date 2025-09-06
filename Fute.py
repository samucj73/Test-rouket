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

st.title("Jogos e Tendência de Gols - API Football")

# ==========================
# Função para buscar ligas
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas = [
            {"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]}
            for l in data
        ]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

# ==========================
# Função para calcular média de gols (marcados e sofridos)
# ==========================
def media_gols_time(team_id):
    url = f"{BASE_URL}/fixtures?team={team_id}&last=5"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        jogos = response.json()["response"]
        if not jogos:
            return 0, 0

        gols_marcados = [
            j["goals"]["home"] if j["teams"]["home"]["id"] == team_id else j["goals"]["away"]
            for j in jogos
        ]
        gols_sofridos = [
            j["goals"]["away"] if j["teams"]["home"]["id"] == team_id else j["goals"]["home"]
            for j in jogos
        ]

        media_marcados = sum(gols_marcados) / len(gols_marcados)
        media_sofridos = sum(gols_sofridos) / len(gols_sofridos)
        return media_marcados, media_sofridos
    else:
        return 0, 0

# ==========================
# Buscar ligas e jogos
# ==========================
ligas = get_ligas()

if ligas:
    df_ligas = pd.DataFrame(ligas)
    st.write(f"✅ Total de ligas disponíveis: {len(df_ligas)}")
    st.dataframe(df_ligas[["id", "nome", "pais"]])

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
                data_filtrada = [j for j in data if j["league"]["id"] == int(liga_id)]

                if data_filtrada:
                    lista = []
                    for j in data_filtrada:
                        fixture = j["fixture"]
                        league = j["league"]
                        teams = j["teams"]

                        # Médias de gols (casa e fora)
                        media_casa_marc, media_casa_sofr = media_gols_time(teams["home"]["id"])
                        media_fora_marc, media_fora_sofr = media_gols_time(teams["away"]["id"])

                        # Estimativa baseada em ataque + defesa
                        estimativa = (
                            (media_casa_marc + media_fora_sofr) / 2
                            + (media_fora_marc + media_casa_sofr) / 2
                        )

                        # Classificação
                        if estimativa >= 2.5:
                            tendencia = "🔥 Mais 2.5"
                        elif estimativa <= 1.5:
                            tendencia = "❄️ Menos 1.5"
                        else:
                            tendencia = "⚖️ Equilibrado"

                        lista.append({
                            "Data/Hora": fixture["date"],
                            "Liga": league["name"],
                            "Time Casa": teams["home"]["name"],
                            "Time Fora": teams["away"]["name"],
                            "Casa (M/S)": f"{round(media_casa_marc,2)}/{round(media_casa_sofr,2)}",
                            "Fora (M/S)": f"{round(media_fora_marc,2)}/{round(media_fora_sofr,2)}",
                            "Estimativa Gols": round(estimativa, 2),
                            "Tendência": tendencia,
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
