# Futebol_Alertas_AllLigas.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações TheSportsDB
# =============================
API_KEY = "123"  # sua chave gratuita
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Funções auxiliares
# =============================

def listar_ligas():
    """Obtém todas as ligas de futebol disponíveis na API."""
    url = f"{BASE_URL}/all_leagues.php"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
        return ligas
    except Exception as e:
        st.error(f"Erro ao buscar ligas: {e}")
        return []

def listar_jogos(liga_nome, data):
    """Busca jogos de uma liga pelo nome e data."""
    url = f"{BASE_URL}/eventsday.php?d={data}&l={liga_nome}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        return data.get("events")
    except Exception as e:
        st.error(f"Erro ao buscar jogos: {e}")
        return None

# =============================
# Streamlit App
# =============================

st.set_page_config(page_title="⚽ Alertas Futebol", layout="wide")
st.title("⚽ Alertas Automáticos de Jogos")

# Data escolhida
hoje = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = hoje.strftime("%Y-%m-%d")

# Buscar todas as ligas
ligas = listar_ligas()
liga_nomes = [l["strLeague"] for l in ligas]

# Escolher a liga
liga_escolhida = st.selectbox("🏆 Escolha a liga:", liga_nomes)

# Botão buscar
if st.button("🔎 Buscar Jogos"):
    jogos = listar_jogos(liga_escolhida, data_str)

    if not jogos:
        st.warning(f"❌ Não há jogos registrados para {liga_escolhida} em {data_str}.")
    else:
        st.success(f"🔎 Foram encontrados {len(jogos)} jogos:")
        for e in jogos:
            home = e.get("strHomeTeam", "TBD")
            away = e.get("strAwayTeam", "TBD")
            hora = e.get("strTime", "00:00")
            st.write(f"**{home} 🆚 {away}** ⏰ {hora}")
