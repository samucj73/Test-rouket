import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# =============================
# Configurações API-Football
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# =============================
# Funções principais
# =============================
def listar_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []
    data = response.json()["response"]
    ligas = [{"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]} for l in data]
    return ligas

def buscar_jogos(data, competicoes_ids):
    todos_jogos = []
    for comp_id in competicoes_ids:
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
                    "league": j["league"]["name"],
                    "país": j["league"]["country"]
                })
        else:
            st.error(f"Erro ao buscar jogos: {response.status_code}")
    # Garantir que o DataFrame sempre tenha as colunas corretas
    if not todos_jogos:
        return pd.DataFrame(columns=["time_casa", "time_fora", "data", "league", "país"])
    return pd.DataFrame(todos_jogos)

# =============================
# Streamlit UI
# =============================
st.title("⚽ Jogos do Dia - API Football")

# 1️⃣ Seleção de data
data_selecionada = st.date_input(
    "Escolha a data do jogo",
    value=datetime.today()
)
data_formatada = data_selecionada.strftime("%Y-%m-%d")

# 2️⃣ Seleção de campeonatos
ligas_disponiveis = listar_ligas()
if ligas_disponiveis:
    ligas_dict = {f"{l['nome']} ({l['pais']})": l['id'] for l in ligas_disponiveis}
    ligas_selecionadas = st.multiselect(
        "Selecione os campeonatos",
        list(ligas_dict.keys()),
        default=list(ligas_dict.keys())[:5]  # seleciona os primeiros 5 por padrão
    )
    competicoes_ids = [ligas_dict[l] for l in ligas_selecionadas]
else:
    competicoes_ids = []

# 3️⃣ Buscar jogos
if st.button("Buscar jogos"):
    if not competicoes_ids:
        st.warning("Selecione pelo menos um campeonato.")
    else:
        with st.spinner("Buscando jogos..."):
            df_jogos = buscar_jogos(data_formatada, competicoes_ids)

            # Verifica se a coluna 'data' existe e se não está vazio
            if df_jogos.empty or "data" not in df_jogos.columns:
                st.info("Nenhum jogo encontrado para a data e campeonatos selecionados.")
            else:
                # Filtra apenas jogos futuros
                agora = datetime.now(timezone.utc)
                df_jogos = df_jogos[df_jogos["data"] >= agora]

                if df_jogos.empty:
                    st.info("Nenhum jogo futuro encontrado para a data e campeonatos selecionados.")
                else:
                    st.success(f"{len(df_jogos)} jogos encontrados")
                    st.dataframe(df_jogos[["time_casa", "time_fora", "league", "país", "data"]])
