import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json

# =============================
# Configurações API
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
HEADERS_FIXTURES = {"x-apisports-key": API_KEY}
BASE_URL_FIXTURES = "https://v3.football.api-sports.io"
BASE_URL_STANDINGS = "https://api.football-standings.com"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo 2
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Funções persistência
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
# Funções Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})

def enviar_alerta_telegram(home, away, data_jogo, tendencia, estimativa, confianca):
    data_formatada = data_jogo.strftime("%d/%m/%Y")
    hora_formatada = data_jogo.strftime("%H:%M")
    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture_id, home, away, data_jogo, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    precisa_enviar = False
    if fixture_id not in alertas or alertas[fixture_id]["tendencia"] != tendencia:
        precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(home, away, data_jogo, tendencia, estimativa, confianca)
        alertas[fixture_id] = {"tendencia": tendencia}
        salvar_alertas(alertas)

# =============================
# Função tendência de gols
# =============================
def calcular_tendencia_confianca(media_casa, media_fora):
    estimativa_final = (media_casa + media_fora) / 2
    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5) * 15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5) * 20)
    else:
        tendencia = "Menos 1.5"
        confianca = min(95, 55 + (1.5 - estimativa_final) * 20)
    return estimativa_final, confianca, tendencia

# =============================
# Funções API Football Standings
# =============================
def obter_ligas():
    url = f"{BASE_URL_STANDINGS}/leagues"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    return resp.json().get("leagues", [])

def obter_classificacao_liga(league_id):
    url = f"{BASE_URL_STANDINGS}/leagues/{league_id}/standings"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    return resp.json().get("standings", [])

# =============================
# Funções API Fixtures
# =============================
def obter_jogos_dia(league_ids, data):
    jogos_dia = []
    for liga_id in league_ids:
        url = f"{BASE_URL_FIXTURES}/fixtures?date={data}&league={liga_id}"
        resp = requests.get(url, headers=HEADERS_FIXTURES)
        if resp.status_code != 200:
            continue
        jogos = resp.json().get("response", [])
        jogos_dia.extend(jogos)
    return jogos_dia

def obter_odds(fixture_id):
    url = f"{BASE_URL_FIXTURES}/odds?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS_FIXTURES)
    if resp.status_code != 200:
        return {"1.5": None, "2.5": None}

    response_json = resp.json().get("response", [])
    if not response_json:
        return {"1.5": None, "2.5": None}

    odds_15, odds_25 = None, None
    bookmakers = response_json[0].get("bookmakers", [])
    if not bookmakers:
        return {"1.5": None, "2.5": None}

    markets = bookmakers[0].get("markets", [])
    for bet in markets:
        if bet.get("label", "").lower() == "goals over/under":
            for outcome in bet.get("outcomes", []):
                if outcome.get("name") == "Over 1.5":
                    odds_15 = outcome.get("price")
                elif outcome.get("name") == "Over 2.5":
                    odds_25 = outcome.get("price")
    return {"1.5": odds_15, "2.5": odds_25}

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

# Temporada
temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)

# Seleção de liga
ligas = obter_ligas()
ligas_dict = {liga["name"]: liga["id"] for liga in ligas}
liga_escolhida = st.selectbox("🏆 Escolha a liga:", list(ligas_dict.keys()))
liga_id = ligas_dict[liga_escolhida]

# Data
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
data_iso = data_selecionada.strftime("%Y-%m-%d")

if st.button("🔍 Buscar jogos do dia"):
    st.info(f"Buscando jogos do dia para a liga {liga_escolhida}...")

    # Obter classificação da liga
    classificacao = obter_classificacao_liga(liga_id)
    classificacao_dict = {time["team"]: time for time in classificacao}

    # Obter jogos reais do dia
    jogos_dia = obter_jogos_dia([liga_id], data_iso)

    melhores_15 = []
    melhores_25 = []

    for match in jogos_dia:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        fixture_id = str(match["fixture"]["id"])
        data_jogo = datetime.fromisoformat(match["fixture"]["date"].replace("Z", "+00:00")) - timedelta(hours=3)

        # Obter médias reais da classificação
        media_casa = classificacao_dict.get(home, {}).get("goals_scored", 1.0)
        media_fora = classificacao_dict.get(away, {}).get("goals_against", 1.0)

        estimativa, confianca, tendencia = calcular_tendencia_confianca(media_casa, media_fora)
        verificar_enviar_alerta(fixture_id, home, away, data_jogo, tendencia, estimativa, confianca)

        # Obter odds reais
        odds = obter_odds(fixture_id)

        # Top 3
        if tendencia == "Mais 1.5":
            melhores_15.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca, "odd_15": odds["1.5"]})
        elif tendencia == "Mais 2.5":
            melhores_25.append({"home": home, "away": away, "estimativa": estimativa, "confianca": confianca, "odd_25": odds["2.5"]})

    # Ordenar Top 3
    melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

    msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
    if melhores_15:
        odd_combinada_15 = 1
        msg_alt += "🔥 Top 3 Jogos para +1.5 Gols\n"
        for j in melhores_15:
            odd_combinada_15 *= float(j.get("odd_15") or 1)
            msg_alt += (
                f"🏟️ {j['home']} vs {j['away']} | "
                f"Estimativa: {j['estimativa']:.2f} | "
                f"Confiança: {j['confianca']:.0f}% | "
                f"Odd: {j.get('odd_15','N/A')}\n"
            )
        msg_alt += f"🎯 Odd combinada: {odd_combinada_15:.2f}\n\n"

    if melhores_25:
        odd_combinada_25 = 1
        msg_alt += "⚡ Top 3 Jogos para +2.5 Gols\n"
        for j in melhores_25:
            odd_combinada_25 *= float(j.get("odd_25") or 1)
            msg_alt += (
                f"🏟️ {j['home']} vs {j['away']} | "
                f"Estimativa: {j['estimativa']:.2f} | "
                f"Confiança: {j['confianca']:.0f}% | "
                f"Odd: {j.get('odd_25','N/A')}\n"
            )
        msg_alt += f"🎯 Odd combinada: {odd_combinada_25:.2f}\n\n"

    if melhores_15 or melhores_25:
        enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
        st.success("🚀 Top jogos enviados para o canal alternativo 2!")
    else:
        st.info("Nenhum jogo com tendência clara de +1.5 ou +2.5 gols encontrado.")



    
