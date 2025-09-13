import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import os

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ==========================
# Configurações Telegram
# ==========================
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ALERTAS_PATH = "alertas_telegram.json"

# ==========================
# Funções Telegram
# ==========================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

def enviar_alerta_telegram(fixture, league, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    liga = league["name"]

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"🏆 Liga: {liga}\n"
        f"🔥 Tendência: Mais 2.5\n"
        f"📊 Estimativa de gols: {estimativa:.2f}"
    )
    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def verificar_enviar_alerta(fixture_id, fixture, league, estimativa):
    alertas = carregar_alertas()
    precisa_enviar = False

    if fixture_id not in alertas:
        precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, league, estimativa)
        alertas[fixture_id] = {"enviado": True}
        salvar_alertas(alertas)

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
# Função para buscar jogos finalizados da liga e calcular estatísticas
# ==========================
@st.cache_data
def buscar_estatisticas_liga(liga_id, temporada):
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
        home_goals = j["score"]["fulltime"]["home"] or 0
        away_goals = j["score"]["fulltime"]["away"] or 0

        for t in [home, away]:
            if t["id"] not in times_stats:
                times_stats[t["id"]] = {
                    "nome": t["name"],
                    "logo": t["logo"],
                    "jogos_disputados": 0,
                    "vitorias": 0,
                    "empates": 0,
                    "derrotas": 0,
                    "gols_marcados": 0,
                    "gols_sofridos": 0
                }

        times_stats[home["id"]]["jogos_disputados"] += 1
        times_stats[away["id"]]["jogos_disputados"] += 1
        times_stats[home["id"]]["gols_marcados"] += home_goals
        times_stats[home["id"]]["gols_sofridos"] += away_goals
        times_stats[away["id"]]["gols_marcados"] += away_goals
        times_stats[away["id"]]["gols_sofridos"] += home_goals

        if home_goals > away_goals:
            times_stats[home["id"]]["vitorias"] += 1
            times_stats[away["id"]]["derrotas"] += 1
        elif home_goals < away_goals:
            times_stats[away["id"]]["vitorias"] += 1
            times_stats[home["id"]]["derrotas"] += 1
        else:
            times_stats[home["id"]]["empates"] += 1
            times_stats[away["id"]]["empates"] += 1

    for t_id, t_stats in times_stats.items():
        jogos = t_stats["jogos_disputados"]
        t_stats["media_gols_marcados"] = round(t_stats["gols_marcados"] / jogos, 2) if jogos else 0
        t_stats["media_gols_sofridos"] = round(t_stats["gols_sofridos"] / jogos, 2) if jogos else 0

    return times_stats

# ==========================
# Função para calcular tendência de gols
# ==========================
def calcular_tendencia(times_stats, home_id, away_id):
    media_casa = times_stats.get(home_id, {"media_gols_marcados":0,"media_gols_sofridos":0})
    media_fora = times_stats.get(away_id, {"media_gols_marcados":0,"media_gols_sofridos":0})

    estimativa = media_casa["media_gols_marcados"] + media_fora["media_gols_marcados"]

    if estimativa >= 2.5:
        tendencia = "Mais 2.5"
    elif estimativa <= 1.5:
        tendencia = "Menos 1.5"
    else:
        tendencia = "Equilibrado"

    return estimativa, tendencia, media_casa, media_fora

# ==========================
# Função visual para exibir cada jogo
# ==========================
def exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia):
    if "Mais 2.5" in tendencia:
        cor = "red"
        icone = "🔥"
    elif "Menos 1.5" in tendencia:
        cor = "blue"
        icone = "❄️"
    else:
        cor = "orange"
        icone = "⚖️"

    home_goals = fixture.get("goals", {}).get("home") or 0
    away_goals = fixture.get("goals", {}).get("away") or 0
    elapsed = fixture.get("status", {}).get("elapsed", 0)

    col1, col2, col3 = st.columns([3,1,3])
    with col1:
        st.image(teams["home"]["logo"], width=50)
        st.markdown(f"### {teams['home']['name']}")
        st.caption(f"⚽ Média: {media_casa['media_gols_marcados']:.2f} | 🛡️ Sofridos: {media_casa['media_gols_sofridos']:.2f}")

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:{cor}; font-size:18px;'>"
            f"<b>{icone} {tendencia}</b><br>Estimativa: {estimativa:.2f}<br>"
            f"⚽ Placar Atual: {elapsed}’ - {teams['home']['name']} {home_goals} x {away_goals} {teams['away']['name']}</div>",
            unsafe_allow_html=True
        )
        st.caption(f"📍 {fixture['venue']['name'] if fixture['venue'] else 'Desconhecido'}<br>🏟️ Liga: {league['name']}<br>Status: {fixture['status']['long']}")

    with col3:
        st.image(teams["away"]["logo"], width=50)
        st.markdown(f"### {teams['away']['name']}")
        st.caption(f"⚽ Média: {media_fora['media_gols_marcados']:.2f} | 🛡️ Sofridos: {media_fora['media_gols_sofridos']:.2f}")

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

    temporada = st.number_input("Escolha o ano da temporada para estatísticas", 
                                min_value=2000, 
                                max_value=datetime.today().year, 
                                value=datetime.today().year, 
                                step=1)

    data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("Buscar Jogos"):
        st.info("⏳ Buscando jogos finalizados da liga e calculando estatísticas...")
        times_stats = buscar_estatisticas_liga(liga_id, temporada)

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

                        estimativa, tendencia, media_casa, media_fora = calcular_tendencia(times_stats, teams["home"]["id"], teams["away"]["id"])
                        
                        # Exibir card
                        exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia)

                        # Enviar alerta apenas se "Mais 2.5"
                        if tendencia == "Mais 2.5":
                            verificar_enviar_alerta(str(fixture["id"]), fixture, league, estimativa)
                else:
                    st.warning("⚠️ Não há jogos dessa liga na data selecionada.")
            else:
                st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
