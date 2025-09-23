import streamlit as st
import requests
from datetime import date

# =============================
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # sua chave gratuita
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Funções para API
# =============================
@st.cache_data(ttl=3600)  # cache de 1 hora
def obter_ligas():
    try:
        url = f"{BASE_URL}/all_leagues.php"
        resp = requests.get(url)
        resp.raise_for_status()
        ligas = {
            liga["strLeague"]: liga["idLeague"]
            for liga in resp.json().get("leagues", [])
            if liga["strSport"] == "Soccer"
        }
        return ligas
    except Exception as e:
        st.error(f"Erro ao obter ligas: {e}")
        return {}

@st.cache_data(ttl=300)  # cache de 5 min
def obter_jogos_do_dia(liga_id, data):
    try:
        url = f"{BASE_URL}/eventsday.php?d={data}&l={liga_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        jogos = resp.json().get("events", [])
        return jogos
    except Exception as e:
        st.error(f"Erro ao obter jogos do dia: {e}")
        return []

# =============================
# Streamlit UI
# =============================
st.title("⚽ Jogos de Futebol do Dia - TheSportsDB")

# Escolha da data
data_selecionada = st.date_input("Escolha a data:", value=date.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Carregar ligas
ligas = obter_ligas()
if not ligas:
    st.warning("Nenhuma liga encontrada.")
else:
    liga_nome = st.selectbox("Escolha a liga:", sorted(ligas.keys()))
    liga_id = ligas[liga_nome]

    # Buscar jogos do dia
    jogos = obter_jogos_do_dia(liga_id, data_str)

    if jogos:
        st.subheader(f"Jogos em {liga_nome} no dia {data_str}")
        for j in jogos:
            st.write(f"🏠 {j['strHomeTeam']}  vs  {j['strAwayTeam']} 🏟️ {j.get('strVenue','')}")
    else:
        st.info(f"Não há jogos registrados para {liga_nome} no dia {data_str}.")
