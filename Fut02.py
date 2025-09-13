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
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ALERTAS_PATH = "alertas.json"

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

# =============================
# NOVO: cálculo com base nos confrontos diretos (H2H)
# =============================
def media_gols_confrontos_diretos(home_id, away_id, temporada=None):
    """Busca média de gols nos confrontos diretos entre os dois times"""
    url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return {"media_gols": 0, "total_jogos": 0}

    jogos = response.json().get("response", [])
    gols_totais, jogos_disputados = 0, 0

    for j in jogos:
        if j["fixture"]["status"]["short"] != "FT":
            continue
        # mantém compatibilidade com temporada
        if temporada and j["league"]["season"] != temporada:
            continue

        home_goals = j["score"]["fulltime"]["home"]
        away_goals = j["score"]["fulltime"]["away"]
        gols_totais += home_goals + away_goals
        jogos_disputados += 1

    if jogos_disputados == 0:
        return {"media_gols": 0, "total_jogos": 0}

    return {
        "media_gols": round(gols_totais / jogos_disputados, 2),
        "total_jogos": jogos_disputados
    }

def calcular_tendencia_confianca(media_h2h):
    """Calcula tendência só com base no H2H"""
    estimativa = media_h2h["media_gols"]

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
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")

st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

# Escolher temporada
temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)

# Escolher data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())

# Botão para buscar jogos
if st.button("🔍 Buscar jogos do dia"):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoje}"
    response = requests.get(url, headers=HEADERS)
    
    # DEBUG: Mostrar JSON completo da API
    st.subheader("📝 Todos os jogos retornados pela API (para conferência)")
    st.json(response.json())
    
    jogos = response.json().get("response", [])

    ligas_principais = {
        "Premier League": 39,
        "La Liga": 140,
        "Serie A": 135,
        "Bundesliga": 78,
        "Ligue 1": 61,
        "Brasileirão Série A": 71,
        "Brasileirão Série B": 72
    }

    if not jogos:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
    else:
        st.success(f"✅ Total de jogos encontrados: {len(jogos)}")
        for match in jogos:
            league_id = match.get("league", {}).get("id")
            if league_id not in ligas_principais.values():
                continue

            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            home_id = match["teams"]["home"]["id"]
            away_id = match["teams"]["away"]["id"]

            # usa somente H2H
            media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada)
            estimativa, confianca, tendencia = calcular_tendencia_confianca(media_h2h)

            with st.container():
                st.subheader(f"🏟️ {home} vs {away}")
                st.caption(f"Liga: {match['league']['name']} | Temporada: {temporada}")
                st.write(f"📊 Estimativa de gols (H2H): **{estimativa:.2f}**")
                st.write(f"🔥 Tendência: **{tendencia}**")
                st.write(f"✅ Confiança: **{confianca:.0f}%**")

            if confianca >= 60 and tendencia != "Equilibrado":
                verificar_e_atualizar_alerta(match, tendencia, confianca, estimativa)
