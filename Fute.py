# Futebol_Alertas_Integrado.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY_FD = "SUA_CHAVE_FOOTBALLDATA"  # coloque sua chave válida
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configurações TheSportsDB
# =============================
API_KEY_TSD = "123"  # chave gratuita TheSportsDB
BASE_URL_TSD = f"https://www.thesportsdb.com/api/v1/json/{API_KEY_TSD}"

# =============================
# Ligas importantes (Football-Data.org)
# =============================
liga_dict_fd = {
    "Premier League (Inglaterra)": 2021,
    "Championship (Inglaterra)": 2016,
    "Bundesliga (Alemanha)": 2002,
    "La Liga (Espanha)": 2014,
    "Serie A (Itália)": 2019,
    "Ligue 1 (França)": 2015,
    "Primeira Liga (Portugal)": 2017,
    "Campeonato Brasileiro Série A": 2013,
    "Campeonato Brasileiro Série B": 2014,
    "UEFA Champions League": 2001,
    "UEFA Europa League": 2003,
    "Copa Libertadores": 2152,
    "Copa Sudamericana": 2154,
}

# =============================
# Funções auxiliares Football-Data.org
# =============================
def buscar_jogos_fd(liga_id, data_evento):
    url = f"{BASE_URL_FD}/matches"
    params = {"dateFrom": data_evento, "dateTo": data_evento, "competitions": liga_id}
    try:
        r = requests.get(url, headers=HEADERS_FD, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("matches", [])
    except Exception as e:
        st.error(f"Erro ao buscar jogos no Football-Data: {e}")
        return []

# =============================
# Funções auxiliares TheSportsDB
# =============================
def listar_ligas_tsd():
    url = f"{BASE_URL_TSD}/all_leagues.php"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
        return ligas
    except Exception as e:
        st.error(f"Erro ao buscar ligas no TheSportsDB: {e}")
        return []

def buscar_jogos_tsd(liga_nome, data_evento):
    url = f"{BASE_URL_TSD}/eventsday.php?d={data_evento}&l={liga_nome}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        return data.get("events")
    except Exception as e:
        st.error(f"Erro ao buscar jogos no TheSportsDB: {e}")
        return None

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="⚽ Alertas Futebol Integrado", layout="wide")
st.title("⚽ Alertas Automáticos de Jogos - Fonte Híbrida")

# Data escolhida
hoje = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = hoje.strftime("%Y-%m-%d")

# Fonte de dados
fonte = st.radio("🌍 Escolha a fonte de dados:", ["Football-Data.org", "TheSportsDB"])

if fonte == "Football-Data.org":
    todas_ligas = st.checkbox("📌 Buscar todas as ligas fixas", value=True)
    if not todas_ligas:
        liga_fd = st.selectbox("🏆 Escolha a liga:", list(liga_dict_fd.keys()))
        ligas_busca = [liga_dict_fd[liga_fd]]
    else:
        ligas_busca = liga_dict_fd.values()

    # Buscar jogos
    todos_jogos = []
    for liga_id in ligas_busca:
        jogos = buscar_jogos_fd(liga_id, data_str)
        todos_jogos.extend(jogos)

    if not todos_jogos:
        st.warning(f"❌ Não há jogos no Football-Data para {data_str}.")
    else:
        st.success(f"🔎 Foram encontrados {len(todos_jogos)} jogos no Football-Data:")
        for j in todos_jogos:
            home = j["homeTeam"]["name"]
            away = j["awayTeam"]["name"]
            hora = j["utcDate"][11:16]
            liga = j["competition"]["name"]
            st.write(f"**{hora}** | {liga} | {home} 🆚 {away}")

elif fonte == "TheSportsDB":
    ligas = listar_ligas_tsd()
    liga_nomes = [l["strLeague"] for l in ligas]
    liga_escolhida = st.selectbox("🏆 Escolha a liga:", liga_nomes)

    if st.button("🔎 Buscar Jogos"):
        jogos = buscar_jogos_tsd(liga_escolhida, data_str)

        if not jogos:
            st.warning(f"❌ Não há jogos registrados para {liga_escolhida} em {data_str}.")
        else:
            st.success(f"🔎 Foram encontrados {len(jogos)} jogos no TheSportsDB:")
            for e in jogos:
                home = e.get("strHomeTeam", "TBD")
                away = e.get("strAwayTeam", "TBD")
                hora = e.get("strTime", "00:00")
                st.write(f"**{home} 🆚 {away}** ⏰ {hora}")
