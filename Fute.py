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
    """Lista competições principais"""
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


def listar_partidas(comp_code):
    """Lista partidas de hoje de uma competição"""
    url = f"{BASE_URL}/competitions/{comp_code}/matches"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("matches", [])


def classificacao_liga(comp_code):
    """Tabela de classificação da liga"""
    url = f"{BASE_URL}/competitions/{comp_code}/standings"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return None
    return r.json()


def artilheiros_liga(comp_code):
    """Lista artilheiros da competição"""
    url = f"{BASE_URL}/competitions/{comp_code}/scorers"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return None
    return r.json()


def media_gols_time(team_id, qtd=5):
    """Média de gols dos últimos jogos do time"""
    url = f"{BASE_URL}/teams/{team_id}/matches?limit={qtd}&status=FINISHED"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return 1.0
    matches = r.json().get("matches", [])
    if not matches:
        return 1.0

    gols = []
    for m in matches:
        total_gols = (m["score"]["fullTime"]["home"] or 0) + (m["score"]["fullTime"]["away"] or 0)
        gols.append(total_gols)

    return sum(gols) / len(gols)


def prever_mais_menos_gols(home_id, away_id, linha):
    """Previsão de Over/Under baseado em médias"""
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
    nomes = [f"{c['nome']} ({c['codigo']})" for c in competicoes]
    escolha = st.selectbox("Escolha a competição", nomes)

    comp_code = escolha.split("(")[-1].replace(")", "").strip()

    # Linha de gols escolhida pelo usuário
    linha_gol = st.number_input("Linha de gols (ex: 2.5)", min_value=0.5, max_value=5.0, step=0.5, value=2.5)

    if st.button("Analisar Jogos de Hoje"):
        partidas = listar_partidas(comp_code)

        if not partidas:
            st.warning("Nenhuma partida disponível para esta liga hoje.")
        else:
            tabela = []
            for match in partidas:
                if match["status"] not in ["SCHEDULED", "TIMED"]:
                    continue
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                previsao = prever_mais_menos_gols(match["homeTeam"]["id"], match["awayTeam"]["id"], linha_gol)

                tabela.append({
                    "Data": match["utcDate"][:10],
                    "Hora": match["utcDate"][11:16],
                    "Casa": home,
                    "Fora": away,
                    "Previsão": previsao
                })

            if tabela:
                st.subheader("📊 Jogos de Hoje com Previsão Over/Under")
                df = pd.DataFrame(tabela)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Nenhum jogo futuro encontrado para hoje nessa competição.")

        # Classificação da liga
        standings = classificacao_liga(comp_code)
        if standings and "standings" in standings:
            st.subheader("🏆 Classificação da Liga")
            table_data = []
            for team in standings["standings"][0]["table"]:
                table_data.append({
                    "Posição": team["position"],
                    "Time": team["team"]["name"],
                    "Pontos": team["points"],
                    "Vitórias": team["won"],
                    "Empates": team["draw"],
                    "Derrotas": team["lost"],
                    "Gols Pró": team["goalsFor"],
                    "Gols Contra": team["goalsAgainst"]
                })
            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, use_container_width=True)

        # Artilheiros
        scorers = artilheiros_liga(comp_code)
        if scorers and "scorers" in scorers:
            st.subheader("⚽ Artilheiros da Competição")
            top_scorers = []
            for s in scorers["scorers"]:
                top_scorers.append({
                    "Jogador": s["player"]["name"],
                    "Time": s["team"]["name"],
                    "Gols": s["goals"]
                })
            df_scorers = pd.DataFrame(top_scorers)
            st.dataframe(df_scorers, use_container_width=True)
