import streamlit as st
import requests
from datetime import datetime

API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.set_page_config(page_title="Análise de Gols", layout="wide")
st.title("⚽ Jogos e Tendência de Gols")

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
    return []

# ==========================
# Função para médias de gols
# ==========================
def media_gols_time(team_id):
    url = f"{BASE_URL}/fixtures?team={team_id}&last=5"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        jogos = response.json()["response"]
        if not jogos:
            return 0, 0

        gols_marcados = [
            j["goals"]["home"] if j["teams"]["home"]["id"] == team_id else j["goals"]["away"]
            for j in jogos
        ]
        gols_sofridos = [
            j["goals"]["away"] if j["teams"]["home"]["id"] == team_id else j["goals"]["home"]
            for j in jogos
        ]

        return sum(gols_marcados) / len(gols_marcados), sum(gols_sofridos) / len(gols_sofridos)
    return 0, 0

# ==========================
# Interface principal
# ==========================
ligas = get_ligas()

if ligas:
    liga_opcao = st.selectbox("🏆 Escolha a liga:", [f'{l["nome"]} - {l["pais"]}' for l in ligas])
    liga_id = [l["id"] for l in ligas if f'{l["nome"]} - {l["pais"]}' == liga_opcao][0]

    data_selecionada = st.date_input("📅 Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("🔍 Buscar Jogos"):
        url = f"{BASE_URL}/fixtures?date={data_formatada}&league={liga_id}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()["response"]

            if data:
                for j in data:
                    fixture = j["fixture"]
                    league = j["league"]
                    teams = j["teams"]

                    # Médias de gols
                    media_casa_marc, media_casa_sofr = media_gols_time(teams["home"]["id"])
                    media_fora_marc, media_fora_sofr = media_gols_time(teams["away"]["id"])

                    # Estimativa
                    estimativa = (
                        (media_casa_marc + media_fora_sofr) / 2
                        + (media_fora_marc + media_casa_sofr) / 2
                    )

                    if estimativa >= 2.5:
                        tendencia = "🔥 Mais 2.5"
                        cor = "red"
                    elif estimativa <= 1.5:
                        tendencia = "❄️ Menos 1.5"
                        cor = "blue"
                    else:
                        tendencia = "⚖️ Equilibrado"
                        cor = "orange"

                    # Layout em card
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 3])

                        with col1:
                            st.image(teams["home"]["logo"], width=50)
                            st.markdown(f"### {teams['home']['name']}")
                            st.caption(f"⚽ {media_casa_marc:.1f} | 🛡️ {media_casa_sofr:.1f}")

                        with col2:
                            st.markdown(
                                f"<div style='text-align:center; color:{cor}; font-size:20px;'>"
                                f"<b>{tendencia}</b><br>"
                                f"({estimativa:.2f} gols)</div>",
                                unsafe_allow_html=True
                            )
                            st.caption(f"📍 {fixture['venue']['name']}")

                        with col3:
                            st.image(teams["away"]["logo"], width=50)
                            st.markdown(f"### {teams['away']['name']}")
                            st.caption(f"⚽ {media_fora_marc:.1f} | 🛡️ {media_fora_sofr:.1f}")

                        st.divider()
            else:
                st.warning("⚠️ Nenhum jogo encontrado para essa liga/data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
