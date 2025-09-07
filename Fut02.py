import streamlit as st
import requests
import pandas as pd
import os
import json
from datetime import datetime

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ==========================
# Configurações Telegram
# ==========================
BASE_URL_TG = "https://api.telegram.org/botSEU_TOKEN/sendMessage"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
ALERTAS_PATH = "alertas_andamento.json"

st.set_page_config(page_title="Jogos e Tendência de Gols", layout="wide")
st.title("⚽ Alertas de Gols - Europa & Brasil 2023")

# ==========================
# Função para buscar ligas principais
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas_desejadas = [
            "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
            "Brasileirão Série A", "Brasileirão Série B"
        ]
        ligas = [
            {
                "id": l["league"]["id"],
                "nome": l["league"]["name"],
                "pais": l["country"]["name"]
            }
            for l in data if l["league"]["name"] in ligas_desejadas
        ]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

# ==========================
# Função para buscar estatísticas dos times na temporada 2023
# ==========================
@st.cache_data
def buscar_estatisticas_liga(liga_id, temporada=2023):
    url_fixtures = f"{BASE_URL}/fixtures?league={liga_id}&season={temporada}"
    response = requests.get(url_fixtures, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code} ao buscar jogos da liga: {response.text}")
        return {}

    jogos = response.json()["response"]
    if not jogos:
        st.warning(f"🔎 API retornou 0 jogos da liga {liga_id} na temporada {temporada}")
        return {}

    times_stats = {}
    for j in jogos:
        fixture = j["fixture"]
        status = fixture["status"]["short"]
        if status != "FT":
            continue  # Apenas jogos finalizados

        home = j["teams"]["home"]
        away = j["teams"]["away"]
        home_goals = j["score"]["fulltime"]["home"]
        away_goals = j["score"]["fulltime"]["away"]

        for t in [home, away]:
            if t["id"] not in times_stats:
                times_stats[t["id"]] = {
                    "nome": t["name"],
                    "logo": t["logo"],
                    "jogos_disputados": 0,
                    "gols_marcados": 0,
                    "gols_sofridos": 0
                }

        times_stats[home["id"]]["jogos_disputados"] += 1
        times_stats[away["id"]]["jogos_disputados"] += 1
        times_stats[home["id"]]["gols_marcados"] += home_goals
        times_stats[home["id"]]["gols_sofridos"] += away_goals
        times_stats[away["id"]]["gols_marcados"] += away_goals
        times_stats[away["id"]]["gols_sofridos"] += home_goals

    # Calcular médias
    for t_id, t_stats in times_stats.items():
        jogos = t_stats["jogos_disputados"]
        t_stats["media_gols_marcados"] = round(t_stats["gols_marcados"] / jogos, 2) if jogos else 0
        t_stats["media_gols_sofridos"] = round(t_stats["gols_sofridos"] / jogos, 2) if jogos else 0

    return times_stats

# ==========================
# Função para enviar alerta no Telegram
# ==========================
def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    msg = (
        f"⚽ Alerta de Gols!\n"
        f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {fixture['status']['long']}\n"
        f"Placar atual: {fixture.get('goals', {}).get('home',0)} x {fixture.get('goals', {}).get('away',0)}"
    )
    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

# ==========================
# Função para verificar se o alerta deve ser enviado
# ==========================
def carregar_alertas_andamento():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas_andamento(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

def verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas_andamento()
    fixture_id = str(fixture["id"])
    home_goals = fixture.get("goals", {}).get("home", 0)
    away_goals = fixture.get("goals", {}).get("away", 0)

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if ultimo["home_goals"] != home_goals or ultimo["away_goals"] != away_goals or ultimo["tendencia"] != tendencia:
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia
        }
        salvar_alertas_andamento(alertas)

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if ligas:
    df_ligas = pd.DataFrame(ligas)
    liga_escolhida = st.selectbox("Escolha uma liga:", options=df_ligas["nome"].unique())
    liga_id = df_ligas[df_ligas["nome"] == liga_escolhida]["id"].values[0]

    if st.button("Buscar Jogos de Hoje"):
        data_hoje = datetime.today().strftime("%Y-%m-%d")
        st.info("⏳ Buscando jogos do dia e calculando médias da temporada 2023...")
        times_stats = buscar_estatisticas_liga(liga_id, temporada=2023)

        url = f"{BASE_URL}/fixtures?date={data_hoje}&league={liga_id}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            jogos = response.json()["response"]
            if jogos:
                for j in jogos:
                    fixture = j["fixture"]
                    teams = j["teams"]

                    media_casa = times_stats.get(teams["home"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})
                    media_fora = times_stats.get(teams["away"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})

                    estimativa = media_casa["media_gols_marcados"] + media_fora["media_gols_marcados"]
                    confianca = min(95, 50 + abs(estimativa - 1.75) * 30)
                    if estimativa >= 2.5:
                        tendencia = "Mais 2.5"
                    elif estimativa <= 1.5:
                        tendencia = "Menos 1.5"
                    else:
                        tendencia = "Equilibrado"

                    # Envia alerta automático
                    verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa)

                    # Exibir no Streamlit
                    st.markdown(f"**{teams['home']['name']} vs {teams['away']['name']}**")
                    st.markdown(f"Tendência: {tendencia} | Estimativa: {estimativa:.2f} | Confiança: {confianca:.0f}%")
                    st.markdown(f"Status: {fixture['status']['long']}")
                    st.markdown(f"Placar atual: {fixture.get('goals', {}).get('home',0)} x {fixture.get('goals', {}).get('away',0)}")
                    st.divider()
            else:
                st.warning("⚠️ Nenhum jogo encontrado para hoje.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
