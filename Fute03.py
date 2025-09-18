import streamlit as st
import requests

# =============================
# Configurações
# =============================
LEAGUES = {
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1"
}

BASE_URL_ESPN = "http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

# =============================
# Função para puxar jogos
# =============================
def obter_jogos_espn(league_code):
    try:
        url = BASE_URL_ESPN.format(league=league_code)
        r = requests.get(url, timeout=15)
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
st.set_page_config(page_title="📊 Jogos ESPN", layout="wide")
st.title("📊 Consulta de Jogos da Temporada - API ESPN (Édson)")

liga_nome = st.selectbox("🏆 Escolha a Liga:", list(LEAGUES.keys()))
liga_code = LEAGUES[liga_nome]

if st.button("🔍 Buscar jogos da temporada"):
    with st.spinner("Buscando jogos..."):
        jogos = obter_jogos_espn(liga_code)
        if not jogos:
            st.info("Nenhum jogo encontrado para essa liga.")
        else:
            st.success(f"{len(jogos)} jogos encontrados na {liga_nome}")
            for j in jogos:
                home = j["competitions"][0]["competitors"][0]["team"]["displayName"]
                away = j["competitions"][0]["competitors"][1]["team"]["displayName"]
                status = j["status"]["type"]["description"]
                placar_home = j["competitions"][0]["competitors"][0].get("score", 0)
                placar_away = j["competitions"][0]["competitors"][1].get("score", 0)
                st.write(f"🏟️ {home} vs {away} | ⚽ {placar_home} x {placar_away} | 🕒 {status}")
