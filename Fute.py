import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# =============================
# Configurações API-Football
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
}

# =============================
# Funções principais
# =============================
def buscar_jogos_por_data(data, competicoes=[]):
    todos_jogos = []
    for comp_id in competicoes:
        url = f"{BASE_URL}/fixtures?league={comp_id}&season={datetime.now().year}&date={data}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            jogos = response.json().get("response", [])
            for j in jogos:
                fixture_time = datetime.fromisoformat(j["fixture"]["date"].replace("Z", "+00:00"))
                todos_jogos.append({
                    "time_casa": j["teams"]["home"]["name"],
                    "time_fora": j["teams"]["away"]["name"],
                    "data": fixture_time,
                    "league": j["league"]["name"]
                })
        else:
            st.error(f"Erro ao buscar jogos: {response.status_code}")
    return pd.DataFrame(todos_jogos)

# =============================
# Streamlit UI
# =============================
st.title("⚽ Jogos do Dia")

# Seletor de data
data_selecionada = st.date_input(
    "Escolha a data do jogo",
    value=datetime.today()
)
data_formatada = data_selecionada.strftime("%Y-%m-%d")

# Seleção de campeonatos
competicoes_disponiveis = {
    "Premier League": 39,
    "Serie A": 61,
    "La Liga": 140,
    "Bundesliga": 78
}
competicoes_selecionadas = st.multiselect(
    "Selecione os campeonatos",
    list(competicoes_disponiveis.keys()),
    default=["Premier League", "Serie A"]
)

if st.button("Buscar jogos"):
    ids_competicoes = [competicoes_disponiveis[c] for c in competicoes_selecionadas]
    with st.spinner("Buscando jogos..."):
        df_jogos = buscar_jogos_por_data(data_formatada, ids_competicoes)
        if df_jogos.empty:
            st.warning("Nenhum jogo encontrado para a data selecionada.")
        else:
            # Filtra apenas jogos futuros
            agora = datetime.now(timezone.utc)
            df_jogos = df_jogos[df_jogos["data"] >= agora]

            st.success(f"{len(df_jogos)} jogos encontrados")
            st.dataframe(df_jogos[["time_casa", "time_fora", "league", "data"]])
