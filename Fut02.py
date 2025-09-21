import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os

# =============================
# Configurações API-Football
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"

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
# Funções API
# =============================
def obter_ligas():
    url = f"{BASE_URL}/leagues"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ligas = {l['league']['name']: l['league']['id'] for l in data['response']}
        return ligas
    except:
        st.error("Erro ao obter ligas da API-Football")
        return {}

def obter_classificacao(liga_id, temporada):
    url = f"{BASE_URL}/standings?league={liga_id}&season={temporada}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        standings = {}
        for team in data['response'][0]['league']['standings']:
            for t in team:
                name = t['team']['name']
                gols_marcados = t['all']['goals']['for']
                gols_sofridos = t['all']['goals']['against']
                standings[name] = {"scored": gols_marcados, "against": gols_sofridos}
        return standings
    except:
        st.warning("Erro ao obter classificação")
        return {}

def obter_jogos_dia(league_id, data):
    url = f"{BASE_URL}/fixtures?league={league_id}&season={datetime.today().year}&date={data}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get('response', [])
    except:
        st.warning("Erro ao obter jogos")
        return []

def obter_odds(fixture_id):
    url = f"{BASE_URL}/odds?fixture={fixture_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        odds_data = resp.json().get("response", [])
        if not odds_data:
            return {"1.5": None, "2.5": None}
        odds_15, odds_25 = None, None
        bookmakers = odds_data[0].get("bookmakers", [])
        if not bookmakers:
            return {"1.5": None, "2.5": None}
        for market in bookmakers[0].get("markets", []):
            if market.get("label","").lower() == "goals over/under":
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == "Over 1.5":
                        odds_15 = outcome.get("price")
                    elif outcome.get("name") == "Over 2.5":
                        odds_25 = outcome.get("price")
        return {"1.5": odds_15, "2.5": odds_25}
    except:
        return {"1.5": None, "2.5": None}

# =============================
# Streamlit interface
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia e envia alertas de tendência de gols.")

temporada = st.selectbox("📅 Temporada:", [2022,2023,2024,2025], index=1)
data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_iso = data_selecionada.strftime("%Y-%m-%d")

# Seleção de liga
ligas = obter_ligas()
liga_escolhida = st.selectbox("🏆 Liga:", list(ligas.keys()) if ligas else ["Nenhuma"])
liga_id = ligas.get(liga_escolhida)

if st.button("🔍 Buscar jogos"):
    if not liga_id:
        st.error("Selecione uma liga válida!")
    else:
        classificacao = obter_classificacao(liga_id, temporada)
        jogos = obter_jogos_dia(liga_id, data_iso)

        melhores_15, melhores_25 = [], []

        for match in jogos:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            fixture_id = str(match["fixture"]["id"])
            data_jogo = datetime.fromisoformat(match["fixture"]["date"].replace("Z","+00:00")) - timedelta(hours=3)

            media_casa = classificacao.get(home, {}).get("scored", 1)
            media_fora = classificacao.get(away, {}).get("against", 1)

            estimativa, confianca, tendencia = calcular_tendencia(media_casa, media_fora)
            verificar_enviar_alerta(fixture_id, home, away, data_jogo, tendencia, estimativa, confianca)

            odds = obter_odds(fixture_id)

            if tendencia == "Mais 1.5":
                melhores_15.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca, "odd_15": odds["1.5"]})
            elif tendencia == "Mais 2.5":
                melhores_25.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca, "odd_25": odds["2.5"]})

        # Top 3
        melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
        melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

        msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
        if melhores_15:
            odd_combinada_15 = 1
            msg_alt += "🔥 Top 3 +1.5 Gols\n"
            for j in melhores_15:
                odd_combinada_15 *= float(j.get("odd_15") or 1)
                msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']:.0f}% | Odd: {j.get('odd_15','N/A')}\n"
            msg_alt += f"🎯 Odd combinada: {odd_combinada_15:.2f}\n\n"

        if melhores_25:
            odd_combinada_25 = 1
            msg_alt += "⚡ Top 3 +2.5 Gols\n"
            for j in melhores_25:
                odd_combinada_25 *= float(j.get("odd_25") or 1)
                msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']:.0f}% | Odd: {j.get('odd_25','N/A')}\n"
            msg_alt += f"🎯 Odd combinada: {odd_combinada_25:.2f}\n\n"

        if melhores_15 or melhores_25:
            enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
            st.success("🚀 Top jogos enviados para canal alternativo 2!")
        else:
            st.info("Nenhum jogo com tendência clara +1.5 ou +2.5 encontrado.")
