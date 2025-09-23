# Futebol_Alertas_TheSportsDB.py
import streamlit as st
from datetime import datetime
import requests

# =============================
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # Chave gratuita
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# =============================
# Dicionário de Ligas Importantes
# =============================
liga_dict = {
    "Premier League (Inglaterra)": 4328,
    "Championship (Inglaterra)": 4329,
    "Bundesliga (Alemanha)": 4331,
    "2. Bundesliga (Alemanha)": 4332,
    "La Liga (Espanha)": 4335,
    "Segunda División (Espanha)": 4336,
    "Serie A (Itália)": 4332,
    "Serie B (Itália)": 4333,
    "Ligue 1 (França)": 4334,
    "Ligue 2 (França)": 4335,
    "Primeira Liga (Portugal)": 4344,
    "Campeonato Brasileiro Série A": 4357,
    "Campeonato Brasileiro Série B": 4358,
    "UEFA Champions League": 4415,
    "UEFA Europa League": 4462,
    "Copa Libertadores (CONMEBOL)": 4349,
    "Copa Sudamericana (CONMEBOL)": 4350,
}

# =============================
# Função para buscar jogos de uma liga e data específica
# =============================
def buscar_jogos(liga_id, data_evento):
    url = f"{BASE_URL}/eventsday.php"
    params = {
        "d": data_evento,
        "l": liga_id
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("events", [])
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
    if jogos:
        todos_jogos.extend(jogos)

if not todos_jogos:
    st.warning(f"Não há jogos registrados para a(s) liga(s) selecionada(s) no dia {data_str}.")
else:
    st.success(f"🔎 Foram encontrados {len(todos_jogos)} jogos para {data_str}:")
    for jogo in todos_jogos:
        home = jogo["strHomeTeam"]
        away = jogo["strAwayTeam"]
        hora = jogo.get("strTime", "??:??")  # Horário pode estar ausente
        competicao = jogo.get("strLeague", "Liga Desconhecida")
        st.write(f"**{hora}** | {competicao} | {home} x {away}")
