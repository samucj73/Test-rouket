import streamlit as st
from datetime import datetime
import requests
import os
import json

# =============================
# Configurações API
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ALERTAS_PATH = "alertas.json"

# =============================
# Configurações do filtro de alertas
# =============================
CONF_MINIMA = 60
TENDENCIAS_ALERTA = ["Mais 2.5", "Menos 1.5"]

# =============================
# Funções de persistência
# =============================
def carregar_alertas_andamento():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas_andamento(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

# =============================
# Funções auxiliares
# =============================
def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas_andamento()
    fixture_id = str(fixture["fixture"]["id"])

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (
            ultimo["home_goals"] != home_goals
            or ultimo["away_goals"] != away_goals
            or ultimo["tendencia"] != tendencia
        ):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia,
        }
        salvar_alertas_andamento(alertas)

def verificar_e_enviar_alerta_filtrado(fixture, estimativa, confianca, tendencia):
    if confianca < CONF_MINIMA or tendencia not in TENDENCIAS_ALERTA:
        return
    verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa)

def media_gols_time(team_id, league_id, season):
    """Busca média de gols marcados/sofridos de um time em uma liga/temporada"""
    url = f"{BASE_URL}/fixtures?league={league_id}&season={season}&team={team_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return {"media_gols_marcados": 0, "media_gols_sofridos": 0}

    jogos = response.json().get("response", [])
    gols_marcados, gols_sofridos, jogos_disputados = 0, 0, 0

    for j in jogos:
        if j["fixture"]["status"]["short"] != "FT":
            continue
        home = j["teams"]["home"]["id"]
        away = j["teams"]["away"]["id"]
        home_goals = j["score"]["fulltime"]["home"]
        away_goals = j["score"]["fulltime"]["away"]

        if team_id == home:
            gols_marcados += home_goals
            gols_sofridos += away_goals
        elif team_id == away:
            gols_marcados += away_goals
            gols_sofridos += home_goals
        jogos_disputados += 1

    if jogos_disputados == 0:
        return {"media_gols_marcados": 0, "media_gols_sofridos": 0}

    return {
        "media_gols_marcados": round(gols_marcados / jogos_disputados, 2),
        "media_gols_sofridos": round(gols_sofridos / jogos_disputados, 2),
    }

def calcular_tendencia_confianca(media_casa, media_fora):
    estimativa = media_casa["media_gols_marcados"] + media_fora["media_gols_marcados"]
    if estimativa >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(90, 50 + estimativa * 10)
    elif estimativa <= 1.5:
        tendencia = "Menos 1.5"
        confianca = min(90, 50 + (1.5 - estimativa) * 20)
    else:
        tendencia = "Equilibrado"
        confianca = 50
    return estimativa, confianca, tendencia

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

# Seleção da temporada
temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)

# Seleção da data
data_selecionada = st.date_input("📆 Escolha a data:", value=datetime.today())
data_formatada = data_selecionada.strftime("%Y-%m-%d")

# Botão para buscar jogos
if st.button("🔍 Buscar jogos do dia"):
    url = f"{BASE_URL}/fixtures?date={data_formatada}"
    response = requests.get(url, headers=HEADERS)
    jogos = response.json().get("response", [])

    ligas_principais = {
        "Premier League": 39,
        "La Liga": 140,
        "Serie A": 135,
        "Bundesliga": 78,
        "Ligue 1": 61,
        "Brasileirão Série A": 71,
        "Brasileirão Série B": 74,
    }

    if not jogos:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
    else:
        for match in jogos:
            league_id = match.get("league", {}).get("id")
            if league_id not in ligas_principais.values():
                continue

            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            home_id = match["teams"]["home"]["id"]
            away_id = match["teams"]["away"]["id"]

            media_casa = media_gols_time(home_id, league_id, temporada)
            media_fora = media_gols_time(away_id, league_id, temporada)

            estimativa, confianca, tendencia = calcular_tendencia_confianca(media_casa, media_fora)

            with st.container():
                st.subheader(f"🏟️ {home} vs {away}")
                st.caption(f"Liga: {match['league']['name']} | Temporada: {temporada}")
                st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
                st.write(f"🔥 Tendência: **{tendencia}**")
                st.write(f"✅ Confiança: **{confianca:.0f}%**")
                home_goals = match.get("goals", {}).get("home", 0) or 0
                away_goals = match.get("goals", {}).get("away", 0) or 0
                st.write(f"⚽ Placar Atual: {home} {home_goals} x {away_goals} {away}")

            # Verifica e envia alerta filtrado
            verificar_e_enviar_alerta_filtrado(match, estimativa, confianca, tendencia)

# Mostrar todos os jogos retornados pela API (para conferência)
st.subheader("🔎 Todos os jogos do dia (para conferência)")
if jogos:
    for match in jogos:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        liga = match["league"]["name"]
        data_jogo = match["fixture"]["date"][:16].replace("T", " ")
        status = match["fixture"]["status"]["long"]

        st.write(f"🏟️ {home} vs {away} | Liga: {liga} | Data: {data_jogo} | Status: {status}")
else:
    st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
