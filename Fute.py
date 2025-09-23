# Futebol_Alertas_Principal.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY = "SUA_CHAVE_AQUI"  # Substitua pela sua chave
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL = "https://api.football-data.org/v4"

# =============================
# Dicionário de Ligas Importantes
# =============================
liga_dict = {
    "Premier League (Inglaterra)": 2021,
    "Championship (Inglaterra)": 2016,
    "Bundesliga (Alemanha)": 2002,
    "2. Bundesliga (Alemanha)": 2005,
    "La Liga (Espanha)": 2014,
    "Segunda División (Espanha)": 2015,
    "Serie A (Itália)": 2019,
    "Serie B (Itália)": 2017,
    "Ligue 1 (França)": 2015,
    "Ligue 2 (França)": 2016,
    "Primeira Liga (Portugal)": 2017,
    "Campeonato Brasileiro Série A": 2013,
    "Campeonato Brasileiro Série B": 2014,
    "UEFA Champions League": 2001,
    "UEFA Europa League": 2003,
    "Copa Libertadores (CONMEBOL)": 2019,
    "Copa Sudamericana (CONMEBOL)": 2017,
}

# =============================
# Função para buscar jogos de uma liga e data específica
# =============================
def buscar_jogos(liga_id, data_evento):
    url = f"{BASE_URL}/matches"
    params = {
        "dateFrom": data_evento,
        "dateTo": data_evento,
        "competitions": liga_id
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("matches", [])
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro ao buscar jogos: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Alertas de Jogos - Futebol")
st.markdown("Selecione a data e a liga para ver os jogos do dia:")

# Seleção de data
data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

# Opção de buscar todas as ligas ou uma específica
todas_ligas = st.checkbox("📌 Buscar jogos de todas as ligas do dia", value=True)

liga_selecionada = None
if not todas_ligas:
    liga_selecionada = st.selectbox("📌 Escolha a liga:", list(liga_dict.keys()))

# Determinar IDs de busca
ligas_busca = liga_dict.values() if todas_ligas else [liga_dict[liga_selecionada]]

# =============================
# Exibir jogos
# =============================
todos_jogos = []

for liga_id in ligas_busca:
    jogos = buscar_jogos(liga_id, data_str)
    todos_jogos.extend(jogos)

if not todos_jogos:
    st.warning(f"Não há jogos registrados para a(s) liga(s) selecionada(s) no dia {data_str}.")
else:
    st.success(f"🔎 Foram encontrados {len(todos_jogos)} jogos para {data_str}:")
    for jogo in todos_jogos:
        home = jogo["homeTeam"]["name"]
        away = jogo["awayTeam"]["name"]
        hora = jogo["utcDate"][11:16]  # HH:MM
        competicao = jogo["competition"]["name"]
        st.write(f"**{hora}** | {competicao} | {home} x {away}")
