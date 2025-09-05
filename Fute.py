import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px

# =============================
# Configurações
# =============================
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_TOKEN}

st.set_page_config(page_title="Mais/Menos Gols - Futebol", layout="centered")
st.title("⚽ Previsão Mais/Menos Gols - Futebol")

# Competição
competicoes = {
    "Bundesliga": "BL1",
    "Premier League": "PL",
    "Champions League": "CL",
    "Serie A": "SA",
    "La Liga": "PD"
}
competicao_selecionada = st.selectbox("Selecione a competição:", list(competicoes.keys()))
codigo_competicao = competicoes[competicao_selecionada]

# Data
data_escolhida = st.date_input("Selecione a data para análise:", datetime.today())

# Linha de gols
linha_gols = st.number_input("Linha de gols:", min_value=0.0, max_value=10.0, value=2.5, step=0.1)

# =============================
# Funções
# =============================
def obter_partidas(codigo, data):
    """Puxa partidas da API para a competição e data selecionada"""
    date_from = data.strftime("%Y-%m-%d")
    date_to = (data + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api.football-data.org/v4/competitions/{codigo}/matches"
    params = {"dateFrom": date_from, "dateTo": date_to}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code}: {response.json().get('message')}")
        return []
    return response.json().get("matches", [])

def calcular_gols_esperados(partidas):
    """Calcula uma estimativa de gols esperados baseada em resultados passados"""
    resultados = []
    for p in partidas:
        home = p["homeTeam"]["name"]
        away = p["awayTeam"]["name"]
        # Para simplificação, usamos placar médio passado (0 se não tiver)
        home_goals = p.get("score", {}).get("fullTime", {}).get("home", 0)
        away_goals = p.get("score", {}).get("fullTime", {}).get("away", 0)
        xg_total = home_goals + away_goals  # estimativa simples
        resultados.append({
            "Partida": f"{home} vs {away}",
            "Gols Esperados": xg_total
        })
    return resultados

def gerar_alertas(df, linha):
    alertas = []
    for g in df["Gols Esperados"]:
        if g > linha:
            alertas.append("Mais de gols 🟢")
        else:
            alertas.append("Menos de gols 🔴")
    df["Sugestão"] = alertas
    return df

# =============================
# Execução
# =============================
partidas = obter_partidas(codigo_competicao, data_escolhida)
if not partidas:
    st.warning("Nenhuma partida encontrada para a data/competição selecionada.")
else:
    resultados = calcular_gols_esperados(partidas)
    df = pd.DataFrame(resultados)
    df = gerar_alertas(df, linha_gols)
    
    st.subheader("Tabela de partidas")
    st.dataframe(df.style.applymap(
        lambda x: "background-color: lightgreen" if "Mais" in str(x) else
                  ("background-color: tomato" if "Menos" in str(x) else ""),
        subset=["Sugestão"]
    ))

    # Gráfico interativo
    fig = px.bar(df, x="Partida", y="Gols Esperados", text="Sugestão",
                 color=df["Sugestão"].apply(lambda x: "Mais" in x),
                 color_discrete_map={True: "green", False: "red"})
    fig.update_layout(title=f"Gols esperados vs Linha ({linha_gols})",
                      yaxis_title="Gols esperados",
                      xaxis_title="Partidas",
                      xaxis_tickangle=-45,
                      template="plotly_white",
                      height=500)
    st.plotly_chart(fig)
