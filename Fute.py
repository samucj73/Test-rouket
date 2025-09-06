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
# Função para buscar ligas principais
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    ligas_principais = []
    if response.status_code == 200:
        data = response.json()["response"]
        ligas_desejadas = ["Copa Libertadores", "Copa Sul-Americana", "MLS", "Liga MX", "Copa do Nordeste"]
        for l in data:
            if l["league"]["name"] in ligas_desejadas:
                ligas_principais.append({
                    "id": l["league"]["id"],
                    "nome": l["league"]["name"],
                    "pais": l["country"]["name"]
                })
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
    return ligas_principais

# ==========================
# Função para buscar média de gols de um time
# ==========================
def media_gols_time(team_id, league_id):
    url = f"{BASE_URL}/fixtures?team={team_id}&league={league_id}&season=2025&status=FT&last=5"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        jogos = response.json()["response"]
        if not jogos:
            return 0, 0
        gols_marcados = [j["goals"]["home"] if j["teams"]["home"]["id"] == team_id else j["goals"]["away"] for j in jogos]
        gols_sofridos = [j["goals"]["away"] if j["teams"]["home"]["id"] == team_id else j["goals"]["home"] for j in jogos]
        return sum(gols_marcados)/len(gols_marcados), sum(gols_sofridos)/len(gols_sofridos)
    return 0, 0

# ==========================
# Função para calcular confiança
# ==========================
def calcular_confianca(media_casa, media_fora):
    estimativa = (media_casa[0] + media_fora[1] + media_fora[0] + media_casa[1]) / 2
    if estimativa >= 2.5:
        conf = min(95, 50 + (estimativa - 2.5) * 20)
        tendencia = "Mais 2.5 gols 🔥"
    elif estimativa <= 1.5:
        conf = min(95, 50 + (1.5 - estimativa) * 20)
        tendencia = "Menos 1.5 gols ❄️"
    else:
        conf = 50
        tendencia = "Equilibrado ⚖️"
    return estimativa, conf, tendencia

# ==========================
# Função visual para exibir cada jogo
# ==========================
def exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca):
    if "Mais 2.5" in tendencia:
        cor_fundo = "#ffcccc"
        cor_texto = "red"
    elif "Menos 1.5" in tendencia:
        cor_fundo = "#cce5ff"
        cor_texto = "blue"
    else:
        cor_fundo = "#fff2cc"
        cor_texto = "orange"

    st.markdown(
        f"""
        <div style='
            background-color: {cor_fundo};
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        '>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div style='text-align:center; width:30%;'>
                    <img src="{teams['home']['logo']}" width="50"><br>
                    <b>{teams['home']['name']}</b><br>
                    ⚽ Média: {media_casa[0]:.2f} | 🛡️ Sofridos: {media_casa[1]:.2f}
                </div>

                <div style='text-align:center; width:40%; color:{cor_texto};'>
                    <b>{tendencia}</b><br>
                    Estimativa: {estimativa:.2f}<br>
                    Confiança: {confianca:.0f}%<br>
                    📍 {fixture['venue']['name'] if fixture['venue'] else 'Desconhecido'}<br>
                    🏟️ Liga: {league['name']}<br>
                    Status: {fixture['status']['long']}
                </div>

                <div style='text-align:center; width:30%;'>
                    <img src="{teams['away']['logo']}" width="50"><br>
                    <b>{teams['away']['name']}</b><br>
                    ⚽ Média: {media_fora[0]:.2f} | 🛡️ Sofridos: {media_fora[1]:.2f}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True
    )

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if not ligas:
    st.warning("⚠️ Não foi possível carregar as ligas principais.")
else:
    df_ligas = pd.DataFrame(ligas)
    liga_escolhida = st.selectbox(
        "Escolha uma liga:",
        options=df_ligas["nome"].unique()
    )
    liga_id = int(df_ligas[df_ligas["nome"] == liga_escolhida]["id"].values[0])
    data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    # Busca jogos sem precisar do botão
    url = f"{BASE_URL}/fixtures?date={data_formatada}&league={liga_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        if not data:
            st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.info(f"⏳ {len(data)} jogos encontrados, calculando estatísticas...")
            for j in data:
                fixture = j["fixture"]
                league = j["league"]
                teams = j["teams"]

                # Busca médias usando jogos finalizados da liga
                media_casa = media_gols_time(teams["home"]["id"], league["id"])
                media_fora = media_gols_time(teams["away"]["id"], league["id"])

                estimativa, confianca, tendencia = calcular_confianca(media_casa, media_fora)
                exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca)
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
