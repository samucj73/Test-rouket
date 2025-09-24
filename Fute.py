# Futebol_Alertas_Principal.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # troque pela sua chave real se tiver
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Funções
# =============================

# Buscar lista de ligas disponíveis
def listar_ligas():
    url = f"{BASE_URL}/all_leagues.php"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        ligas = data.get("leagues", [])
        # Apenas futebol (Soccer)
        return [l for l in ligas if l.get("strSport") == "Soccer"]
    except Exception as e:
        st.error(f"Erro ao obter lista de ligas: {e}")
        return []

# Buscar eventos do dia
def buscar_eventos(data, liga=None):
    url = f"{BASE_URL}/eventsday.php"
    params = {"d": data, "s": "Soccer"}
    if liga:
        params["l"] = liga
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("events", [])
    except Exception as e:
        st.error(f"Erro ao buscar eventos: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Alertas de Jogos - TheSportsDB")
st.markdown("Selecione a data e a liga para ver os jogos:")

# Seleção de data
data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Opção: todas as ligas ou escolher uma
todas_ligas = st.checkbox("📌 Buscar jogos de todas as ligas do dia", value=True)

liga_escolhida = None
if not todas_ligas:
    ligas_disponiveis = listar_ligas()
    if ligas_disponiveis:
        nomes_ligas = [l["strLeague"] for l in ligas_disponiveis]
        liga_escolhida = st.selectbox("📌 Escolha a liga:", nomes_ligas)
    else:
        st.warning("⚠️ Nenhuma liga encontrada.")
        ligas_disponiveis = []

# Buscar eventos
if todas_ligas:
    eventos = buscar_eventos(data_str)
else:
    eventos = buscar_eventos(data_str, liga_escolhida)

# =============================
# Exibir resultados
# =============================
if not eventos:
    st.warning(f"Não há jogos registrados para {data_str}.")
else:
    st.success(f"🔎 Foram encontrados {len(eventos)} jogos para {data_str}:")
    for e in eventos:
        home = e.get("strHomeTeam") or "Desconhecido"
        away = e.get("strAwayTeam") or "Desconhecido"
        hora = e.get("strTime") or "??:??"
        liga = e.get("strLeague") or "Liga desconhecida"
        logo_home = e.get("strHomeTeamBadge") or ""
        logo_away = e.get("strAwayTeamBadge") or ""

        cols = st.columns([1,3,1])
        with cols[0]:
            if logo_home:
                st.image(logo_home, width=40)
            st.write(home)
        with cols[1]:
            st.write(f"**{hora}** | {liga} | {home} x {away}")
        with cols[2]:
            if logo_away:
                st.image(logo_away, width=40)
            st.write(away)

        st.markdown("---")
