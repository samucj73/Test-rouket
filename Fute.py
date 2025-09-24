import requests
import streamlit as st
from datetime import datetime

# =============================
# Configurações APIs
# =============================
API_KEY_FD = "SUA_CHAVE_FOOTBALLDATA"
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

API_KEY_TSD = "123"  # TheSportsDB (free demo key)
BASE_URL_TSD = "https://www.thesportsdb.com/api/v1/json"

# =============================
# Funções para buscar jogos
# =============================

def jogos_brasileirao(data):
    """Puxa jogos do Brasileirão Série A pela Football-Data.org"""
    url = f"{BASE_URL_FD}/competitions/2013/matches?dateFrom={data}&dateTo={data}"
    resp = requests.get(url, headers=HEADERS_FD).json()
    jogos = []
    for m in resp.get("matches", []):
        jogos.append({
            "liga": "Brasileirão Série A",
            "home": m["homeTeam"]["name"],
            "away": m["awayTeam"]["name"],
            "date": m["utcDate"][:10]
        })
    return jogos

def jogos_internacionais(data, liga_id):
    """Puxa jogos de outras ligas pelo TheSportsDB"""
    url = f"{BASE_URL_TSD}/{API_KEY_TSD}/eventsday.php?d={data}&id={liga_id}"
    resp = requests.get(url).json()
    jogos = []
    for e in resp.get("events", []):
        jogos.append({
            "liga": e.get("strLeague"),
            "home": e.get("strHomeTeam"),
            "away": e.get("strAwayTeam"),
            "date": e.get("dateEvent")
        })
    return jogos

# =============================
# Streamlit App
# =============================
st.title("📊 Agenda de Jogos - Multi API")

data_escolhida = st.date_input("Escolha a data:", datetime.today()).strftime("%Y-%m-%d")
liga_escolhida = st.selectbox("Escolha a Liga:", ["Brasileirão Série A", "Premier League", "La Liga", "Serie A"])

if st.button("Buscar jogos"):
    if liga_escolhida == "Brasileirão Série A":
        jogos = jogos_brasileirao(data_escolhida)
    else:
        # Exemplo: Premier League (ID 4328), La Liga (ID 4335), Serie A (ID 4332)
        ligas_ids = {"Premier League": 4328, "La Liga": 4335, "Serie A": 4332}
        liga_id = ligas_ids.get(liga_escolhida)
        jogos = jogos_internacionais(data_escolhida, liga_id)
    
    st.subheader(f"Jogos em {liga_escolhida} ({data_escolhida}):")
    for j in jogos:
        st.write(f"⚽ {j['home']} x {j['away']}  ({j['date']})")
