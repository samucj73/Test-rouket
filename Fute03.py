import streamlit as st
import requests
from datetime import datetime, timedelta

# =============================
# Configurações
# =============================
LEAGUES = {
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2"
}

BASE_URL_ESPN = "http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

# =============================
# Função para puxar jogos de uma data específica
# =============================
def obter_jogos_espn(league_code, data_YYYYMMDD):
    try:
        url = BASE_URL_ESPN.format(league=league_code)
        r = requests.get(url, params={"dates": data_YYYYMMDD}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            events = data.get("events", [])
            return events
    except Exception as e:
        st.error(f"Erro ao obter jogos: {e}")
    return []

# =============================
# Streamlit interface
# =============================
st.set_page_config(page_title="📊 Jogos da Temporada Passada - API ESPN", layout="wide")
st.title("📊 Consulta de Jogos da Temporada Passada - API ESPN")

liga_nome = st.selectbox("🏆 Escolha a Liga:", list(LEAGUES.keys()))
liga_code = LEAGUES[liga_nome]

ano_temporada = st.selectbox("📅 Escolha o ano da temporada:", list(range(2015, datetime.now().year+1)), index=7)

if st.button("🔍 Buscar jogos da temporada selecionada"):
    with st.spinner("Buscando jogos..."):
        # Para pegar uma data qualquer dentro da temporada escolhida, usamos 1º de janeiro do ano selecionado
        data_str = f"{ano_temporada}0101"
        jogos = obter_jogos_espn(liga_code, data_str)
        if not jogos:
            st.info("Nenhum jogo encontrado para essa liga e temporada.")
        else:
            st.success(f"{len(jogos)} jogos encontrados na {liga_nome} para o ano {ano_temporada}")
            for j in jogos:
                home = j["competitions"][0]["competitors"][0]["team"]["displayName"]
                away = j["competitions"][0]["competitors"][1]["team"]["displayName"]
                status = j["status"]["type"]["description"]
                placar_home = j["competitions"][0]["competitors"][0].get("score", 0)
                placar_away = j["competitions"][0]["competitors"][1].get("score", 0)
                st.write(f"🏟️ {home} vs {away} | ⚽ {placar_home} x {placar_away} | 🕒 {status}")
