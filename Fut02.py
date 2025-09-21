import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os

# =============================
# Configurações Football-Data.org
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL = "https://api.football-data.org/v4"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo 2
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Persistência alertas
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

# =============================
# Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg}, timeout=10)
    except:
        st.warning("Falha ao enviar mensagem para Telegram")

def verificar_enviar_alerta(fixture_id, home, away, data_jogo, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    precisa_enviar = False
    if fixture_id not in alertas or alertas[fixture_id]["tendencia"] != tendencia:
        precisa_enviar = True
    if precisa_enviar:
        data_format = data_jogo.strftime("%d/%m/%Y %H:%M")
        msg = (
            f"⚽ {home} vs {away}\n"
            f"📅 {data_format} (BRT)\n"
            f"Tendência: {tendencia} | Estimativa: {estimativa:.2f} | Confiança: {confianca:.0f}%"
        )
        enviar_telegram(msg, TELEGRAM_CHAT_ID)
        alertas[fixture_id] = {"tendencia": tendencia}
        salvar_alertas(alertas)

# =============================
# Função tendência de gols
# =============================
def calcular_tendencia(media_casa, media_fora):
    estimativa = (media_casa + media_fora) / 2
    if estimativa >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa - 2.5) * 15)
    elif estimativa >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa - 1.5) * 20)
    else:
        tendencia = "Menos 1.5"
        confianca = min(95, 55 + (1.5 - estimativa) * 20)
    return estimativa, confianca, tendencia

# =============================
# Funções API Football-Data
# =============================
def obter_ligas():
    return {
        "FIFA World Cup": "WC",
        "UEFA Champions League": "CL",
        "Bundesliga": "BL1",
        "Eredivisie": "DED",
        "Brasileirão Série A": "BSA",
        "La Liga": "PD",
        "Ligue 1": "FL1",
        "Championship": "ELC",
        "Primeira Liga": "PPL",
        "European Championship": "EC",
        "Serie A": "SA",
        "Premier League": "PL"
    }

def obter_classificacao(liga_id):
    try:
        url = f"{BASE_URL}/competitions/{liga_id}/standings"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        standings = {}
        if "standings" in data and len(data["standings"]) > 0:
            table = data["standings"][0].get("table", [])
            for t in table:
                name = t['team']['name']
                gols_marcados = t.get('goalsFor', 1)
                gols_sofridos = t.get('goalsAgainst', 1)
                standings[name] = {"scored": gols_marcados, "against": gols_sofridos}
        return standings
    except Exception as e:
        st.warning(f"Erro ao obter classificação da liga {liga_id}: {e}")
        return {}

def obter_jogos_dia(liga_id, data):
    try:
        url = f"{BASE_URL}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        jogos = resp.json().get("matches", [])
        return jogos
    except Exception as e:
        st.warning(f"Erro ao obter jogos da liga {liga_id}: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia e envia alertas de tendência de gols.")

data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_iso = data_selecionada.strftime("%Y-%m-%d")

ligas = obter_ligas()
liga_escolhida = st.selectbox("🏆 Liga:", list(ligas.keys()))
liga_id = ligas.get(liga_escolhida)

# Checkbox para buscar todos os jogos do dia
buscar_todos = st.checkbox("📌 Buscar todos os jogos do dia (todas as ligas)")

if st.button("🔍 Buscar jogos"):
    classificacao = {}
    jogos = []
    
    if buscar_todos:
        for lid in ligas.values():
            classificacao.update(obter_classificacao(lid))
            jogos += obter_jogos_dia(lid, data_iso)
    else:
        if not liga_id:
            st.error("Selecione uma liga válida!")
        else:
            classificacao = obter_classificacao(liga_id)
            jogos = obter_jogos_dia(liga_id, data_iso)

    melhores_15, melhores_25 = [], []

    for match in jogos:
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        fixture_id = str(match["id"])
        data_jogo = datetime.fromisoformat(match["utcDate"].replace("Z","+00:00")) - timedelta(hours=3)

        media_casa = classificacao.get(home, {}).get("scored", 1)
        media_fora = classificacao.get(away, {}).get("against", 1)

        estimativa, confianca, tendencia = calcular_tendencia(media_casa, media_fora)
        verificar_enviar_alerta(fixture_id, home, away, data_jogo, tendencia, estimativa, confianca)

        if tendencia == "Mais 1.5":
            melhores_15.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca})
        elif tendencia == "Mais 2.5":
            melhores_25.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca})

    # Top 3
    melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

    msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
    if melhores_15:
        msg_alt += "🔥 Top 3 +1.5 Gols\n"
        for j in melhores_15:
            msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']:.0f}%\n"
        msg_alt += "\n"

    if melhores_25:
        msg_alt += "⚡ Top 3 +2.5 Gols\n"
        for j in melhores_25:
            msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']:.0f}%\n"
        msg_alt += "\n"

    if melhores_15 or melhores_25:
        enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
        st.success("🚀 Top jogos enviados para canal alternativo 2!")
    else:
        st.info("Nenhum jogo com tendência clara +1.5 ou +2.5 encontrado.")
