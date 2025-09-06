import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# =============================
# Configurações
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
    """Busca todos os jogos de uma data em competições selecionadas"""
    todos_jogos = []
    for comp_id in competicoes:
        url = f"{BASE_URL}/fixtures?league={comp_id}&season={datetime.now().year}&date={data}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            jogos = response.json().get("response", [])
            for j in jogos:
                todos_jogos.append({
                    "time_casa": j["teams"]["home"]["name"],
                    "time_fora": j["teams"]["away"]["name"],
                    "data": j["fixture"]["date"],
                    "league": j["league"]["name"],
                    "fixture_id": j["fixture"]["id"],
                    # Odds de +1.5 gols já incluídas aqui (evita requisições separadas)
                    "odds_over_1_5": obter_odds_jogo(j)
                })
        else:
            st.error(f"Erro ao buscar jogos: {response.status_code}")
    return pd.DataFrame(todos_jogos)

def obter_odds_jogo(jogo):
    """
    Tenta extrair a odd de Over 1.5 do JSON do jogo.
    Caso não tenha, retorna None.
    """
    odds_data = jogo.get("odds", {}).get("1.5", {})
    # Se houver múltiplas casas, pega a primeira
    if odds_data:
        for casa, odds in odds_data.items():
            if "Over" in odds:
                return float(odds["Over"])
    return None

def calcular_probabilidade(odd):
    """Converte odd em probabilidade implícita"""
    if odd:
        return round(1 / odd, 2)
    return None

def filtrar_jogos_mais_1_5(df, limiar_prob=0.5):
    resultados = []
    for _, row in df.iterrows():
        prob = calcular_probabilidade(row["odds_over_1_5"])
        if prob and prob >= limiar_prob:
            row["prob_mais_1_5"] = prob
            resultados.append(row)
    return pd.DataFrame(resultados)

# =============================
# Streamlit UI
# =============================
st.title("⚽ Jogos com Probabilidade de +1.5 Gols")

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

limiar_prob = st.slider("Limite mínimo de probabilidade (+1.5 gols)", 0.1, 1.0, 0.5, 0.05)

if st.button("Buscar jogos"):
    ids_competicoes = [competicoes_disponiveis[c] for c in competicoes_selecionadas]
    with st.spinner("Buscando jogos..."):
        df_jogos = buscar_jogos_por_data(data_formatada, ids_competicoes)
        if df_jogos.empty:
            st.warning("Nenhum jogo encontrado para a data selecionada.")
        else:
            df_filtrado = filtrar_jogos_mais_1_5(df_jogos, limiar_prob)
            if df_filtrado.empty:
                st.info("Nenhum jogo com probabilidade de +1.5 gols acima do limite.")
            else:
                st.success(f"{len(df_filtrado)} jogos encontrados com probabilidade >= {limiar_prob*100}%")
                st.dataframe(df_filtrado[["time_casa", "time_fora", "league", "prob_mais_1_5"]])
