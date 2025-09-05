import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import time
from datetime import date

# =============================
# Configurações
# =============================
URL_BUNDESLIGA = "https://native-stats.org/competition/BL1/"
LINHA_GOLS_DEFAULT = 2.5
ALERTA_EXTRA = 0.5
REFRESH_INTERVAL = 60  # segundos

st.set_page_config(page_title="Bundesliga Mais/Menos Gols", layout="centered")
st.title("⚽ Bundesliga - Painel Mais/Menos Gols com Alertas 🔔")

# =============================
# Funções auxiliares
# =============================
def obter_dados_bundesliga():
    """ Faz scraping da página da BL1 e retorna partidas, xG e odds """
    try:
        response = requests.get(URL_BUNDESLIGA)
        soup = BeautifulSoup(response.text, 'html.parser')

        partidas = []
        xg_list = []
        odds_list = []

        # Exemplo genérico, ajuste conforme o HTML real do site
        jogos_html = soup.select(".match-row")  # cada partida
        for jogo in jogos_html:
            time_home = jogo.select_one(".home-team").text.strip()
            time_away = jogo.select_one(".away-team").text.strip()
            partida_nome = f"{time_home} vs {time_away}"

            xg_home = float(jogo.select_one(".home-xg").text.strip())
            xg_away = float(jogo.select_one(".away-xg").text.strip())
            xg_total = xg_home + xg_away

            # Odds ou placeholders
            odd_home = jogo.select_one(".home-odd").text.strip() if jogo.select_one(".home-odd") else "-"
            odd_draw = jogo.select_one(".draw-odd").text.strip() if jogo.select_one(".draw-odd") else "-"
            odd_away = jogo.select_one(".away-odd").text.strip() if jogo.select_one(".away-odd") else "-"

            partidas.append(partida_nome)
            xg_list.append(xg_total)
            odds_list.append(f"{odd_home}/{odd_draw}/{odd_away}")

        return partidas, xg_list, odds_list
    except Exception as e:
        st.error(f"Erro ao obter dados: {e}")
        return [], [], []

def calcular_alertas(xg_list, linha_gols):
    alertas = []
    for xg in xg_list:
        if xg > linha_gols + ALERTA_EXTRA:
            alertas.append("Mais de gols 🟢")
        else:
            alertas.append("Menos de gols 🔴")
    return alertas

# =============================
# Interface Streamlit
# =============================
linha_gols = st.number_input("Linha de gols:", min_value=0.0, max_value=10.0,
                             value=LINHA_GOLS_DEFAULT, step=0.1)

st.info(f"⏱️ Atualizando automaticamente a cada {REFRESH_INTERVAL} segundos...")

placeholder = st.empty()

while True:
    partidas, xg_list, odds_list = obter_dados_bundesliga()
    if partidas:
        alertas_list = calcular_alertas(xg_list, linha_gols)

        df = pd.DataFrame({
            "Partida": partidas,
            "xG Total": xg_list,
            "Odds (Home/Draw/Away)": odds_list,
            "Sugestão": alertas_list
        })

        with placeholder.container():
            st.subheader("Tabela de Partidas")
            st.dataframe(df.style.applymap(lambda x: "background-color: lightgreen" if "Mais" in str(x) else
                                           ("background-color: tomato" if "Menos" in str(x) else ""), subset=["Sugestão"]))

            # Gráfico interativo
            fig = px.bar(df, x="Partida", y="xG Total", text="Sugestão",
                         color=df["Sugestão"].apply(lambda x: "Mais" in x),
                         color_discrete_map={True: "green", False: "red"})
            fig.update_layout(title=f"Gols esperados vs Linha ({linha_gols})",
                              yaxis_title="Gols esperados",
                              xaxis_title="Partidas",
                              xaxis_tickangle=-45,
                              template="plotly_white",
                              height=500)
            st.plotly_chart(fig)
    else:
        placeholder.warning("⚠️ Nenhuma partida encontrada ou erro ao coletar dados.")

    time.sleep(REFRESH_INTERVAL)
