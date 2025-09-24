# Futebol_Alertas_TheSportsDB_v2.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # Substitua pela sua chave
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Funções para buscar dados
# =============================
def buscar_todas_ligas():
    url = f"{BASE_URL}/all_leagues.php"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("leagues") or []
    except Exception as e:
        st.error(f"Erro ao buscar ligas: {e}")
        return []

def buscar_ligas_por_pais_esporte(pais, esporte="Soccer"):
    url = f"{BASE_URL}/search_all_leagues.php?c={pais}&s={esporte}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("countrys") or []
    except Exception as e:
        st.error(f"Erro ao buscar ligas por país/esporte: {e}")
        return []

def buscar_times_liga(liga_nome):
    url = f"{BASE_URL}/search_all_teams.php?l={liga_nome}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("teams") or []
    except Exception as e:
        st.error(f"Erro ao buscar times da liga: {e}")
        return []

def buscar_eventos_dia(data_evento, liga_id=None, esporte="Soccer"):
    url = f"{BASE_URL}/eventsday.php"
    params = {"d": data_evento, "s": esporte}
    if liga_id:
        params["l"] = liga_id
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("events") or []
    except Exception as e:
        st.error(f"Erro ao buscar eventos do dia: {e}")
        return []

def buscar_proximos_eventos_time(id_team):
    url = f"{BASE_URL}/eventsnext.php?id={id_team}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("events") or []
    except Exception as e:
        st.error(f"Erro ao buscar próximos eventos do time: {e}")
        return []

def buscar_eventos_proximos_liga(id_league):
    url = f"{BASE_URL}/eventsnextleague.php?id={id_league}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("events") or []
    except Exception as e:
        st.error(f"Erro ao buscar próximos eventos da liga: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Alertas de Jogos - TheSportsDB")
st.markdown("Escolha a forma de busca: por data, liga ou time.")

# Data
data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Modo de busca
modo = st.radio("🔎 Modo de busca:", ["Data", "Liga específica", "Time específico"])

eventos = []

if modo == "Data":
    ligas = st.multiselect("Selecione ligas específicas (ou deixe vazio para todas)", [l['strLeague'] for l in buscar_todas_ligas()])
    if ligas:
        for liga in ligas:
            eventos.extend(buscar_eventos_dia(data_str, liga_id=liga))
    else:
        eventos = buscar_eventos_dia(data_str)

elif modo == "Liga específica":
    todas_ligas = buscar_todas_ligas()
    liga_selecionada = st.selectbox("Escolha a liga:", [l['strLeague'] for l in todas_ligas])
    eventos = buscar_eventos_proximos_liga(liga_selecionada)

else:  # Time específico
    id_team = st.text_input("Digite o ID do time:")
    if id_team:
        eventos = buscar_proximos_eventos_time(id_team)

# =============================
# Exibição dos resultados
# =============================
if not eventos:
    st.warning("Nenhum evento encontrado.")
else:
    st.success(f"🔎 Foram encontrados {len(eventos)} eventos:")
    for e in eventos:
        home = e.get("strHomeTeam")
        away = e.get("strAwayTeam")
        hora = e.get("strTime") or e.get("strTimestamp","")[:5]
        competicao = e.get("strLeague") or e.get("strCompetition")
        logo_home = e.get("strHomeTeamBadge") or ""
        logo_away = e.get("strAwayTeamBadge") or ""

        cols = st.columns([1,3,1])
        with cols[0]:
            if logo_home:
                st.image(logo_home, width=40)
            st.write(home)
        with cols[1]:
            st.write(f"**{hora}** | {competicao} | {home} x {away}")
        with cols[2]:
            if logo_away:
                st.image(logo_away, width=40)
            st.write(away)

        st.markdown("---")
