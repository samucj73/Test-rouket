import streamlit as st
from datetime import datetime, timedelta
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
TELEGRAM_CHAT_ID = "-1003073115320"
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
# Função para enviar alerta Telegram
# =============================
def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    # Data e horário do jogo em BRT
    data_iso = fixture["fixture"]["date"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))  # UTC
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 Data do jogo: {data_formatada}\n"
        f"⏰ Horário do jogo (BRT): {hora_formatada}\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )

    requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

# =============================
# Função para verificar e atualizar alertas
# =============================
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
# Função H2H ponderada
# =============================
def media_gols_confrontos_diretos(home_id, away_id, temporada=None, max_jogos=5):
    url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code != 200:
        return {"media_gols": 0, "total_jogos": 0}

    jogos = response.json().get("response", [])
    if temporada:
        jogos = [j for j in jogos if j["league"]["season"] == temporada]
    
    jogos = sorted(jogos, key=lambda x: x["fixture"]["date"], reverse=True)[:max_jogos]
    if not jogos:
        return {"media_gols": 0, "total_jogos": 0}

    total_pontos, total_peso = 0, 0
    for idx, j in enumerate(jogos):
        if j["fixture"]["status"]["short"] != "FT":
            continue
        home_goals = j["score"]["fulltime"]["home"]
        away_goals = j["score"]["fulltime"]["away"]
        gols = home_goals + away_goals
        peso = max_jogos - idx
        total_pontos += gols * peso
        total_peso += peso

    media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
    return {"media_gols": media_ponderada, "total_jogos": len(jogos)}

# =============================
# Função de estimativa refinada
# =============================
def estimativa_total_gols(home_stats, away_stats, media_h2h, peso_h2h=0.3):
    estimativa_casa = (home_stats["media_gols_marcados"] + away_stats["media_gols_sofridos"]) / 2
    estimativa_fora = (away_stats["media_gols_marcados"] + home_stats["media_gols_sofridos"]) / 2
    estimativa_base = (estimativa_casa + estimativa_fora) / 2
    estimativa_final = round((1 - peso_h2h) * estimativa_base + peso_h2h * media_h2h["media_gols"], 2)

    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + estimativa_final * 10)
    elif estimativa_final <= 1.5:
        tendencia = "Menos 1.5"
        confianca = min(95, 60 + (1.5 - estimativa_final) * 15)
    else:
        tendencia = "Equilibrado"
        confianca = 50

    return estimativa_final, confianca, tendencia

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())

# Liga principal
ligas_principais = {
    "Premier League": 39,
    "Premier League 2ª Divisão": 40,
    "La Liga": 140,
    "La Liga 2ª Divisão": 141,
    "Serie A": 135,
    "MLS": 253, 
    "Bundesliga": 78,
    "Bundesliga 2ª Divisão": 79,
    "Ligue 1": 61,
    "Brasileirão Série A": 71,
    "Brasileirão Série B": 72,
    "UEFA Champions League": 2,
    "Copa Libertadores": 13,
    "Copa Sul-Americana": 14,
    "Copa do Brasil": 73
}

if st.button("🔍 Buscar jogos do dia"):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoje}"
    response = requests.get(url, headers=HEADERS)
    jogos = response.json().get("response", [])

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

            # Buscar H2H
            media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada, max_jogos=5)

            # Estatísticas fictícias (pode ser substituído por API de stats)
            home_stats = {"media_gols_marcados": 1.5, "media_gols_sofridos": 1.2}
            away_stats = {"media_gols_marcados": 1.3, "media_gols_sofridos": 1.4}

            # Estimativa refinada
            estimativa, confianca, tendencia = estimativa_total_gols(home_stats, away_stats, media_h2h, peso_h2h=0.3)

            st.subheader(f"🏟️ {home} vs {away}")
            st.caption(f"Liga: {match['league']['name']} | Temporada: {temporada}")
            st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
            st.write(f"🔥 Tendência: **{tendencia}**")
            st.write(f"✅ Confiança: **{confianca:.0f}%**")

            if confianca >= 60 and tendencia != "Equilibrado":
                verificar_e_atualizar_alerta(match, tendencia, confianca, estimativa)
