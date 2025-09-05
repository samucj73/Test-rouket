import streamlit as st
import requests
import pandas as pd
from datetime import date

# =============================
# CONFIGURAÇÃO
# =============================
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
BASE_URL = "https://api.football-data.org/v4"

HEADERS = {"X-Auth-Token": API_TOKEN}


# =============================
# FUNÇÕES
# =============================

def listar_competicoes():
    """Lista as competições disponíveis"""
    url = f"{BASE_URL}/competitions"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return []
    data = r.json()
    competicoes = []
    for comp in data.get("competitions", []):
        competicoes.append({
            "id": comp["id"],
            "nome": comp["name"],
            "codigo": comp.get("code", "N/A")
        })
    return competicoes


def listar_partidas(competicao_id, data_escolhida):
    """Lista partidas de uma competição e data escolhida"""
    url = f"{BASE_URL}/competitions/{competicao_id}/matches?dateFrom={data_escolhida}&dateTo={data_escolhida}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("matches", [])


def media_gols_time(time_id, qtd=5):
    """Calcula a média de gols de um time nas últimas partidas"""
    url = f"{BASE_URL}/teams/{time_id}/matches?limit={qtd}&status=FINISHED"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return 1.0  # valor padrão
    matches = r.json().get("matches", [])
    if not matches:
        return 1.0

    gols = []
    for m in matches:
        if m["homeTeam"]["id"] == time_id:
            gols.append(m["score"]["fullTime"]["home"] + m["score"]["fullTime"]["away"])
        else:
            gols.append(m["score"]["fullTime"]["home"] + m["score"]["fullTime"]["away"])

    return sum(gols) / len(gols)


def prever_mais_menos_gols(home_id, away_id, linha):
    """Previsão se vai ser Over ou Under"""
    media_home = media_gols_time(home_id)
    media_away = media_gols_time(away_id)
    expectativa = (media_home + media_away) / 2

    if expectativa >= linha:
        return f"🔼 Over {linha} (Mais Gols) - Média esperada: {expectativa:.2f}"
    else:
        return f"🔽 Under {linha} (Menos Gols) - Média esperada: {expectativa:.2f}"


# =============================
# INTERFACE STREAMLIT
# =============================

st.set_page_config(page_title="Futebol - Mais/Menos Gols", layout="centered")

st.title("⚽ Analisador de Jogos - Mais/Menos Gols")

# Seleção de competição
competicoes = listar_competicoes()
if not competicoes:
    st.error("Não foi possível carregar as competições. Verifique sua API Key.")
else:
    nomes = [c["nome"] for c in competicoes]
    escolha = st.selectbox("Escolha a competição", nomes)

    comp_id = next(c["id"] for c in competicoes if c["nome"] == escolha)

    # Seleção de data
    data_jogo = st.date_input("Escolha a data", value=date.today())

    # Linha de gols escolhida pelo usuário
    linha_gol = st.number_input("Linha de gols (ex: 2.5)", min_value=0.5, max_value=5.0, step=0.5, value=2.5)

    if st.button("Buscar Partidas"):
        partidas = listar_partidas(comp_id, data_jogo)

        if not partidas:
            st.warning("Nenhuma partida disponível para esta liga e data.")
        else:
            tabela = []
            for match in partidas:
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                previsao = prever_mais_menos_gols(match["homeTeam"]["id"], match["awayTeam"]["id"], linha_gol)

                tabela.append({
                    "Data": match["utcDate"][:10],
                    "Hora": match["utcDate"][11:16],
                    "Casa": home,
                    "Fora": away,
                    "Status": match["status"],
                    "Previsão": previsao
                })
            df = pd.DataFrame(tabela)
            st.dataframe(df, use_container_width=True)
