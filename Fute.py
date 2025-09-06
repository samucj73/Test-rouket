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

st.set_page_config(page_title="Jogos e Tendência de Gols", layout="wide")
st.title("⚽ Jogos e Tendência de Gols - API Football")

# ==========================
# Função para buscar ligas
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas = [{"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]} for l in data]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

# ==========================
# ==========================
# Função para calcular média de gols apenas com jogos finalizados
# ==========================
def media_gols_time(team_id):
    url = f"{BASE_URL}/fixtures?team={team_id}&last=10"  # pega mais jogos para aumentar chance de histórico
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return 0, 0

    jogos = response.json()["response"]
    if not jogos:
        return 0, 0

    gols_marcados = []
    gols_sofridos = []

    for j in jogos:
        # Considera apenas jogos finalizados com gols válidos
        if j["status"]["short"] != "FT":
            continue

        if j["teams"]["home"]["id"] == team_id:
            if j["goals"]["home"] is not None and j["goals"]["away"] is not None:
                gols_marcados.append(j["goals"]["home"])
                gols_sofridos.append(j["goals"]["away"])
        else:
            if j["goals"]["home"] is not None and j["goals"]["away"] is not None:
                gols_marcados.append(j["goals"]["away"])
                gols_sofridos.append(j["goals"]["home"])

    if not gols_marcados:
        return 0, 0

    media_marcados = sum(gols_marcados) / len(gols_marcados)
    media_sofridos = sum(gols_sofridos) / len(gols_sofridos)
    return media_marcados, media_sofridos

# ==========================
# Função visual para exibir cada jogo
# ==========================
def exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia):
    # Definir cor e ícone
    if "Mais 2.5" in tendencia:
        cor = "red"
        icone = "🔥"
    elif "Menos 1.5" in tendencia:
        cor = "blue"
        icone = "❄️"
    else:
        cor = "orange"
        icone = "⚖️"

    col1, col2, col3 = st.columns([3,1,3])
    with col1:
        st.image(teams["home"]["logo"], width=50)
        st.markdown(f"### {teams['home']['name']}")
        st.caption(f"⚽ Média: {media_casa[0]:.2f} | 🛡️ Sofridos: {media_casa[1]:.2f}")

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:{cor}; font-size:18px;'>"
            f"<b>{icone} {tendencia}</b><br>Estimativa: {estimativa:.2f}</div>",
            unsafe_allow_html=True
        )
        st.caption(f"📍 {fixture['venue']['name'] if fixture['venue'] else 'Desconhecido'}\n{fixture['date'][:16].replace('T',' ')}")
        st.caption(f"🏟️ Liga: {league['name']}\nStatus: {fixture['status']['long']}")

    with col3:
        st.image(teams["away"]["logo"], width=50)
        st.markdown(f"### {teams['away']['name']}")
        st.caption(f"⚽ Média: {media_fora[0]:.2f} | 🛡️ Sofridos: {media_fora[1]:.2f}")

    st.divider()

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if ligas:
    df_ligas = pd.DataFrame(ligas)
    liga_escolhida = st.selectbox(
        "Escolha uma liga:",
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
                    for j in data_filtrada:
                        fixture = j["fixture"]
                        league = j["league"]
                        teams = j["teams"]

                        # Calcular médias
                        media_casa = media_gols_time(teams["home"]["id"])
                        media_fora = media_gols_time(teams["away"]["id"])

                        estimativa = media_casa[0] + media_fora[0]
                        if estimativa >= 2.5:
                            tendencia = "Mais 2.5"
                        elif estimativa <= 1.5:
                            tendencia = "Menos 1.5"
                        else:
                            tendencia = "Equilibrado"

                        exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia)
                else:
                    st.warning("⚠️ Não há jogos dessa liga na data selecionada.")
            else:
                st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
