import streamlit as st
import requests
from datetime import datetime

# ==========================
# Configurações da API
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.set_page_config(page_title="Análise de Gols", layout="wide")
st.title("⚽ Jogos e Tendência de Gols - API Football")

# ==========================
# Funções
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        return [{"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]} for l in data]
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

def media_gols_time(team_id):
    url = f"{BASE_URL}/fixtures?team={team_id}&last=5"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return 0, 0
    jogos = response.json()["response"]
    if not jogos:
        return 0, 0
    gols_marcados = [j["goals"]["home"] if j["teams"]["home"]["id"] == team_id else j["goals"]["away"] for j in jogos]
    gols_sofridos = [j["goals"]["away"] if j["teams"]["home"]["id"] == team_id else j["goals"]["home"] for j in jogos]
    return sum(gols_marcados)/len(gols_marcados), sum(gols_sofridos)/len(gols_sofridos)

def exibir_jogo_card(fixture, teams, media_casa, media_fora, estimativa, tendencia):
    # Definir cor
    if "Mais 2.5" in tendencia:
        cor = "red"
    elif "Menos 1.5" in tendencia:
        cor = "blue"
    else:
        cor = "orange"

    col1, col2, col3 = st.columns([3,1,3])
    with col1:
        st.image(teams["home"]["logo"], width=50)
        st.markdown(f"### {teams['home']['name']}")
        st.caption(f"⚽ {media_casa[0]:.1f} | 🛡️ {media_casa[1]:.1f}")

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:{cor}; font-size:18px;'>"
            f"<b>{tendencia}</b><br>({estimativa:.2f} gols)</div>",
            unsafe_allow_html=True
        )
        st.caption(f"📍 {fixture['venue']['name'] if fixture['venue'] else 'Desconhecido'}\n{fixture['date'][:16].replace('T',' ')}")

    with col3:
        st.image(teams["away"]["logo"], width=50)
        st.markdown(f"### {teams['away']['name']}")
        st.caption(f"⚽ {media_fora[0]:.1f} | 🛡️ {media_fora[1]:.1f}")

    st.divider()

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if not ligas:
    st.error("Não foi possível carregar as ligas.")
else:
    liga_opcao = st.selectbox("🏆 Escolha a liga:", [f'{l["nome"]} - {l["pais"]}' for l in ligas])
    liga_id = [l["id"] for l in ligas if f'{l["nome"]} - {l["pais"]}' == liga_opcao][0]

    data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("🔍 Buscar Jogos"):
        url = f"{BASE_URL}/fixtures?date={data_formatada}&league={liga_id}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            st.error(f"Erro {response.status_code}: {response.text}")
        else:
            data = response.json()["response"]
            if not data:
                st.warning("⚠️ Nenhum jogo encontrado para essa liga/data.")
            else:
                jogos_lista = []
                # Calcular médias e estimativa
                for j in data:
                    fixture = j["fixture"]
                    teams = j["teams"]

                    media_casa = media_gols_time(teams["home"]["id"])
                    media_fora = media_gols_time(teams["away"]["id"])
                    estimativa = ((media_casa[0] + media_fora[1])/2 + (media_fora[0] + media_casa[1])/2)

                    if estimativa >= 2.5:
                        tendencia = "🔥 Mais 2.5"
                    elif estimativa <= 1.5:
                        tendencia = "❄️ Menos 1.5"
                    else:
                        tendencia = "⚖️ Equilibrado"

                    jogos_lista.append({
                        "fixture": fixture,
                        "teams": teams,
                        "estimativa": estimativa,
                        "tendencia": tendencia,
                        "media_casa": media_casa,
                        "media_fora": media_fora
                    })

                # Ranking TOP 5 jogos Mais 2.5 gols
                top5 = sorted(jogos_lista, key=lambda x: x["estimativa"], reverse=True)[:5]
                st.subheader("🏅 TOP 5 jogos com maior probabilidade de +2.5 gols")
                for jogo in top5:
                    exibir_jogo_card(jogo["fixture"], jogo["teams"], jogo["media_casa"], jogo["media_fora"], jogo["estimativa"], jogo["tendencia"])

                st.subheader("📋 Demais jogos")
                for jogo in jogos_lista:
                    if jogo not in top5:
                        exibir_jogo_card(jogo["fixture"], jogo["teams"], jogo["media_casa"], jogo["media_fora"], jogo["estimativa"], jogo["tendencia"])
