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
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo 2
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Funções de persistência
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
# Funções auxiliares
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    data_iso = fixture["fixture"]["date"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas()
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
        salvar_alertas(alertas)

# =============================
# Cálculo H2H ponderada
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

    total_pontos = 0
    total_peso = 0
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
# Função de tendência ajustada
# =============================
def calcular_tendencia_confianca_ajustada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    media_time_casa = media_casa.get("media_gols_marcados", 0) + media_fora.get("media_gols_sofridos", 0)
    media_time_fora = media_fora.get("media_gols_marcados", 0) + media_casa.get("media_gols_sofridos", 0)
    
    estimativa_base = (media_time_casa + media_time_fora) / 2
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * media_h2h.get("media_gols", 0)

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
# Função para obter odds reais
# =============================
def obter_odds(fixture_id):
    url = f"{BASE_URL}/odds?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code != 200:
        return {"1.5": None, "2.5": None}

    response_json = response.json().get("response", [])
    odds_15 = None
    odds_25 = None

    if not response_json:
        return {"1.5": None, "2.5": None}

    # Considera apenas a primeira casa de apostas (ou ajustar conforme necessidade)
    bookmakers = response_json[0].get("bookmakers", [])
    if not bookmakers:
        return {"1.5": None, "2.5": None}

    markets = bookmakers[0].get("markets", [])
    for bet in markets:
        # Verifica se a chave 'label' existe antes de acessar
        if "label" not in bet or not bet["label"]:
            continue

        if bet["label"].lower() == "goals over/under":
            for outcome in bet.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price")
                if name == "Over 1.5":
                    odds_15 = price
                elif name == "Over 2.5":
                    odds_25 = price

    return {"1.5": odds_15, "2.5": odds_25}

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")
st.markdown("Monitora jogos do dia nas principais ligas e envia alertas de tendência de gols.")

temporada = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

ligas_principais = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Brasileirão Série A": 71,
    "UEFA Champions League": 2,
    "Copa Libertadores": 13
}

if st.button("🔍 Buscar jogos do dia"):
    url = f"{BASE_URL}/fixtures?date={hoje}"
    response = requests.get(url, headers=HEADERS)
    jogos = response.json().get("response", [])

    st.subheader("📝 Jogos retornados pela API")
    st.json(response.json())

    #melhores_15 = []
    #melhores_25 = []
    melhores_15 = []
    melhores_25 = []

    for match in jogos:
        league_id = match.get("league", {}).get("id")
        if league_id not in ligas_principais.values():
            continue

        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        home_id = match["teams"]["home"]["id"]
        away_id = match["teams"]["away"]["id"]
        media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada, max_jogos=5)
        
        # Exemplo: médias fictícias (substituir por cálculo real de médias do time)
        media_casa = {"media_gols_marcados": 1.2, "media_gols_sofridos": 1.1}
        media_fora = {"media_gols_marcados": 1.1, "media_gols_sofridos": 1.3}

        estimativa, confianca, tendencia = calcular_tendencia_confianca_ajustada(media_h2h, media_casa, media_fora)

        # Hora e competição
        data_iso = match["fixture"]["date"]
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        hora_formatada = data_jogo.strftime("%H:%M")
        competicao = match.get("league", {}).get("name", "Desconhecido")

        # Obter odds reais
        odds = obter_odds(match["fixture"]["id"])

        with st.container():
            st.subheader(f"🏟️ {home} vs {away}")
            st.caption(f"Liga: {competicao} | Temporada: {temporada}")
            st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
            st.write(f"🔥 Tendência: **{tendencia}**")
            st.write(f"✅ Confiança: **{confianca:.0f}%**")
            st.write(f"💰 Odds Over 1.5: {odds['1.5']} | Over 2.5: {odds['2.5']}")

        verificar_enviar_alerta(match, tendencia, confianca, estimativa)

        # Adicionar ao top 3 com odds reais
        if tendencia == "Mais 1.5":
            melhores_15.append({
                "home": home,
                "away": away,
                "estimativa": estimativa,
                "confianca": confianca,
                "hora": hora_formatada,
                "competicao": competicao,
                "odd_15": odds["1.5"]
            })
        elif tendencia == "Mais 2.5":
            melhores_25.append({
                "home": home,
                "away": away,
                "estimativa": estimativa,
                "confianca": confianca,
                "hora": hora_formatada,
                "competicao": competicao,
                "odd_25": odds["2.5"]
            })

    # Ordenar e pegar top 3
    # Ordenar e pegar top 3
melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

if melhores_15 or melhores_25:
    msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"

    if melhores_15:
        odd_combinada_15 = 1
        msg_alt += "🔥 Top 3 Jogos para +1.5 Gols\n"
        for j in melhores_15:
            odd_combinada_15 *= float(j.get("odds_15", 1))
            msg_alt += (
                f"🏆 {j['competicao']}\n"
                f"🕒 {j['hora']} BRT\n"
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"📊 Estimativa: {j['estimativa']:.2f} gols | ✅ Confiança: {j['confianca']:.0f}%\n"
                f"💰 Odd: {j.get('odds_15', 'N/A')}\n\n"
            )
        msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_15:.2f}\n\n"

    if melhores_25:
        odd_combinada_25 = 1
        msg_alt += "⚡ Top 3 Jogos para +2.5 Gols\n"
        for j in melhores_25:
            odd_combinada_25 *= float(j.get("odds_25", 1))
            msg_alt += (
                f"🏆 {j['competicao']}\n"
                f"🕒 {j['hora']} BRT\n"
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"📊 Estimativa: {j['estimativa']:.2f} gols | ✅ Confiança: {j['confianca']:.0f}%\n"
                f"💰 Odd: {j.get('odds_25', 'N/A')}\n\n"
            )
        msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_25:.2f}\n\n"

    enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
    st.success("🚀 Top jogos enviados para o canal alternativo 2!")
else:
    st.info("Nenhum jogo com tendência clara de +1.5 ou +2.5 gols encontrado.")
    
