import streamlit as st
import requests
from datetime import datetime

# =============================
# Configurações
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"

ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1"
}

# =============================
# Função para puxar jogos da temporada
# =============================
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"Erro ao obter jogos: {e}")
    return []

# =============================
# Streamlit interface
# =============================
st.set_page_config(page_title="📊 Jogos de Temporadas Passadas", layout="wide")
st.title("📊 Consulta de Jogos de Temporadas Passadas (OpenLigaDB)")

temporada = st.selectbox("📅 Escolha a temporada:", ["2022", "2023", "2024", "2025"], index=2)
liga_nome = st.selectbox("🏆 Escolha a Liga:", list(ligas_openliga.keys()))
liga_id = ligas_openliga[liga_nome]

if st.button("🔍 Buscar jogos da temporada"):
    with st.spinner("Buscando jogos..."):
        jogos = obter_jogos_liga_temporada(liga_id, temporada)
        if not jogos:
            st.info("Nenhum jogo encontrado para essa temporada/ligue.")
        else:
            st.success(f"{len(jogos)} jogos encontrados na {liga_nome} ({temporada})")
            for j in jogos[:50]:  # mostrar os primeiros 50 jogos para teste
                home = j["team1"]["teamName"]
                away = j["team2"]["teamName"]
                placar = "-"
                for r in j.get("matchResults", []):
                    if r.get("resultTypeID") == 2:
                        placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                        break
                data = j.get("matchDateTime") or j.get("matchDateTimeUTC") or "Desconhecida"
                st.write(f"🏟️ {home} vs {away} | 📅 {data} | ⚽ Placar: {placar}")
