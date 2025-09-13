import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.set_page_config(page_title="Jogos e Tendência de Gols", layout="wide")
st.title("⚽ Jogos e Tendência de Gols - API Football")

# ==========================
# Função para buscar ligas
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas = [
            {"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]}
            for l in data
        ]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

# ==========================
# Função para buscar jogos finalizados da liga e calcular estatísticas
# ==========================
@st.cache_data
def buscar_estatisticas_liga(liga_id, temporada):
    url_fixtures = f"{BASE_URL}/fixtures?league={liga_id}&season={temporada}"
    response = requests.get(url_fixtures, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code} ao buscar jogos da liga: {response.text}")
        return {}

    jogos = response.json()["response"]
    if not jogos:
        st.warning(f"🔎 API retornou 0 jogos da liga {liga_id} na temporada {temporada}")
        return {}

    times_stats = {}
    for j in jogos:
        fixture = j["fixture"]
        status = fixture["status"]["short"]
        if status != "FT":
            continue  # Apenas jogos finalizados

        home = j["teams"]["home"]
        away = j["teams"]["away"]
        home_goals = j["score"]["fulltime"]["home"] or 0
        away_goals = j["score"]["fulltime"]["away"] or 0

        # Inicializar estatísticas
        for t in [home, away]:
            if t["id"] not in times_stats:
                times_stats[t["id"]] = {
                    "nome": t["name"],
                    "logo": t["logo"],
                    "jogos_disputados": 0,
                    "vitorias": 0,
                    "empates": 0,
                    "derrotas": 0,
                    "gols_marcados": 0,
                    "gols_sofridos": 0
                }

        # Atualizar estatísticas
        times_stats[home["id"]]["jogos_disputados"] += 1
        times_stats[away["id"]]["jogos_disputados"] += 1
        times_stats[home["id"]]["gols_marcados"] += home_goals
        times_stats[home["id"]]["gols_sofridos"] += away_goals
        times_stats[away["id"]]["gols_marcados"] += away_goals
        times_stats[away["id"]]["gols_sofridos"] += home_goals

        # Vitórias / Empates / Derrotas
        if home_goals > away_goals:
            times_stats[home["id"]]["vitorias"] += 1
            times_stats[away["id"]]["derrotas"] += 1
        elif home_goals < away_goals:
            times_stats[away["id"]]["vitorias"] += 1
            times_stats[home["id"]]["derrotas"] += 1
        else:
            times_stats[home["id"]]["empates"] += 1
            times_stats[away["id"]]["empates"] += 1

    # Calcular médias
    for t_id, t_stats in times_stats.items():
        jogos = t_stats["jogos_disputados"]
        t_stats["media_gols_marcados"] = round(t_stats["gols_marcados"] / jogos, 2) if jogos else 0
        t_stats["media_gols_sofridos"] = round(t_stats["gols_sofridos"] / jogos, 2) if jogos else 0

    return times_stats

# ==========================
# Função para calcular tendência profissional com confiança
# ==========================
def calcular_tendencia_pro(media_casa_gols, media_fora_gols):
    estimativa = media_casa_gols + media_fora_gols

    if estimativa >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 50 + (estimativa - 2.5) * 20 + 10)  # maior confiança em jogos com média alta
    elif estimativa <= 1.5:
        tendencia = "Menos 1.5"
        confianca = min(95, 50 + (1.5 - estimativa) * 20 + 10)  # maior confiança em jogos com média baixa
    else:
        tendencia = "Equilibrado"
        confianca = 50 + (abs(2 - estimativa) * 10)  # ajuste sutil para médias entre 1.5 e 2.5

    return round(estimativa, 2), tendencia, round(confianca, 0)

# ==========================
# Função visual para exibir cada jogo (atualizada com confiança e cores profissionais)
# ==========================
def exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca):
    # cores e ícones
    if "Mais 2.5" in tendencia:
        cor = "red" if confianca >= 60 else "orange"
        icone = "🔥"
    elif "Menos 1.5" in tendencia:
        cor = "blue" if confianca >= 60 else "orange"
        icone = "❄️"
    else:
        cor = "orange"
        icone = "⚖️"

    # obter placar atual seguro
    home_goals = fixture.get("goals", {}).get("home") or 0
    away_goals = fixture.get("goals", {}).get("away") or 0
    elapsed = fixture.get("status", {}).get("elapsed", 0)

    col1, col2, col3 = st.columns([3,1,3])
    with col1:
        st.image(teams["home"]["logo"], width=50)
        st.markdown(f"### {teams['home']['name']}")
        st.caption(f"⚽ Média: {media_casa['media_gols_marcados']:.2f} | 🛡️ Sofridos: {media_casa['media_gols_sofridos']:.2f}")

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:{cor}; font-size:18px;'>"
            f"<b>{icone} {tendencia}</b><br>"
            f"Estimativa: {estimativa:.2f} gols<br>"
            f"Confiança: {confianca:.0f}%<br>"
            f"⚽ Placar Atual: {elapsed}’ - {teams['home']['name']} {home_goals} x {away_goals} {teams['away']['name']}</div>",
            unsafe_allow_html=True
        )
        st.caption(f"📍 {fixture['venue']['name'] if fixture['venue'] else 'Desconhecido'}<br>🏟️ Liga: {league['name']}<br>Status: {fixture['status']['long']}")

    with col3:
        st.image(teams["away"]["logo"], width=50)
        st.markdown(f"### {teams['away']['name']}")
        st.caption(f"⚽ Média: {media_fora['media_gols_marcados']:.2f} | 🛡️ Sofridos: {media_fora['media_gols_sofridos']:.2f}")

    st.divider()

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if ligas:
    df_ligas = pd.DataFrame(ligas)
    liga_escolhida = st.selectbox(
        "Escolha uma liga:",
        options=df_ligas["nome"].unique()
    )
    liga_id = df_ligas[df_ligas["nome"] == liga_escolhida]["id"].values[0]

    # escolha do ano/temporada
    temporada = st.number_input("Escolha o ano da temporada para estatísticas", min_value=2000, max_value=datetime.today().year, value=datetime.today().year, step=1)

    data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("Buscar Jogos"):
        st.info("⏳ Buscando jogos finalizados da liga e calculando estatísticas...")
        times_stats = buscar_estatisticas_liga(liga_id, temporada)

        url = f"{BASE_URL}/fixtures?date={data_formatada}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()["response"]
            if data:
                data_filtrada = [j for j in data if j["league"]["id"] == int(liga_id)]
                if data_filtrada:
                    for j in data_filtrada:
                        fixture = j["fixture"]
                        league = j["league"]
                        teams = j["teams"]

                        media_casa = times_stats.get(teams["home"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})
                        media_fora = times_stats.get(teams["away"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})

                        # Calcula tendência profissional
                        estimativa, tendencia, confianca = calcular_tendencia_pro(
                            media_casa["media_gols_marcados"], media_fora["media_gols_marcados"]
                        )

                        exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca)
                                    else:
                        st.warning("⚠️ Não há jogos dessa liga na data selecionada.")
            else:
                st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
                   
