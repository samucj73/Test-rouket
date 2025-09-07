import streamlit as st
import requests
from datetime import datetime
import json
import os

# ==================================
# Configurações
# ==================================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
HEADERS = {"x-apisports-key": API_KEY}

# Telegram
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ALERTAS_PATH = "alertas.json"

# Principais ligas (Europa + Brasil A e B)
LIGAS_PRINCIPAIS = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A (Itália)",
    78: "Bundesliga",
    61: "Ligue 1",
    71: "Brasileirão Série A",
    72: "Brasileirão Série B"
}

# ==================================
# Função para calcular média de gols da temporada
# ==================================
def calcular_media_gols(liga_id, temporada=2023):
    url = f"{BASE_URL}/fixtures?league={liga_id}&season={temporada}&status=FT"
    resp = requests.get(url, headers=HEADERS).json()
    jogos = resp.get("response", [])

    if not jogos:
        return 0.0

    total_gols = sum(
        (j["goals"]["home"] or 0) + (j["goals"]["away"] or 0)
        for j in jogos
    )
    return total_gols / len(jogos)

# ==================================
# Funções de alerta Telegram
# ==================================
def enviar_alerta_telegram(home, away, liga, tendencia, media_gols, status):
    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"Liga: {liga}\n"
        f"📊 Média de gols (2023): {media_gols:.2f}\n"
        f"Tendência: {tendencia}\n"
        f"Status: {status}"
    )
    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

def verificar_enviar_alerta(jogo_id, home, away, liga, tendencia, media_gols, status):
    alertas = carregar_alertas()
    precisa_enviar = False

    if jogo_id not in alertas:
        precisa_enviar = True
    else:
        if alertas[jogo_id]["tendencia"] != tendencia:
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(home, away, liga, tendencia, media_gols, status)
        alertas[jogo_id] = {"tendencia": tendencia}
        salvar_alertas(alertas)

# ==================================
# Interface
# ==================================
st.title("⚽ Scanner de Jogos - Alertas de Gols")

# Seletor de data
data_escolhida = st.date_input(
    "📅 Escolha a data dos jogos",
    datetime.today()
).strftime("%Y-%m-%d")

st.write(f"🔍 Buscando jogos em **{data_escolhida}**...")

# ==================================
# Buscar jogos da data escolhida
# ==================================
url = f"{BASE_URL}/fixtures?date={data_escolhida}"
response = requests.get(url, headers=HEADERS)
dados = response.json()

jogos = dados.get("response", [])

# Filtrar pelas ligas principais
jogos_filtrados = [
    j for j in jogos if j["league"]["id"] in LIGAS_PRINCIPAIS
]

if not jogos_filtrados:
    st.warning("⚠️ Nenhum jogo encontrado para essa data nas ligas principais.")
else:
    st.success(f"✅ {len(jogos_filtrados)} jogos encontrados!")

    for jogo in jogos_filtrados:
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        status = jogo["fixture"]["status"]["long"]
        liga_id = jogo["league"]["id"]
        liga_nome = LIGAS_PRINCIPAIS[liga_id]

        # Calcular média da temporada 2023
        media_gols = calcular_media_gols(liga_id, 2023)

        # Determinar tendência
        if media_gols >= 2.5:
            tendencia = "Mais 2.5 gols 🔥"
        elif media_gols <= 1.5:
            tendencia = "Menos 1.5 gols ❄️"
        else:
            tendencia = "Equilibrado ⚖️"

        st.markdown(
            f"""
            🏟️ **{home} vs {away}**  
            📍 Liga: {liga_nome}  
            📊 Média de gols (2023): **{media_gols:.2f}**  
            📌 Status: {status}  
            ⚡ Tendência: **{tendencia}**
            """
        )

        # Enviar alerta apenas se for Mais 2.5 ou Menos 1.5
        if "Mais 2.5" in tendencia or "Menos 1.5" in tendencia:
            verificar_enviar_alerta(str(jogo["fixture"]["id"]), home, away, liga_nome, tendencia, media_gols, status)
