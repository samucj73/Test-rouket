import streamlit as st
import requests
import json

# =========================
# Função para puxar dados
# =========================
def pegar_jogos_espn(league_code="bra.1"):
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
    response = requests.get(url)

    if response.status_code != 200:
        st.error(f"Erro {response.status_code} ao acessar a API")
        return None

    return response.json()

# =========================
# Interface Streamlit
# =========================
st.set_page_config(page_title="Placar ESPN", layout="wide")

st.title("⚽ Jogos de Futebol - ESPN API")

# Seleção da liga
ligas = {
    "Brasileirão Série A": "bra.1",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1"
}

liga_escolhida = st.selectbox("Escolha a liga:", list(ligas.keys()))
codigo_liga = ligas[liga_escolhida]

# Pegar jogos
data = pegar_jogos_espn(codigo_liga)

if data and "events" in data:
    st.subheader(f"📅 Jogos de hoje - {liga_escolhida}")

    for jogo in data["events"]:
        try:
            time_casa = jogo["competitions"][0]["competitors"][0]["team"]["displayName"]
            placar_casa = jogo["competitions"][0]["competitors"][0]["score"]

            time_fora = jogo["competitions"][0]["competitors"][1]["team"]["displayName"]
            placar_fora = jogo["competitions"][0]["competitors"][1]["score"]

            status = jogo["status"]["type"]["description"]

            st.markdown(
                f"**{time_casa} {placar_casa} x {placar_fora} {time_fora}**  \n"
                f"🕒 {status}"
            )
        except Exception as e:
            st.warning(f"Erro ao processar jogo: {e}")

else:
    st.info("Nenhum jogo encontrado para hoje.")
