import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import time

BASE_URL = "https://api.football-data.org/v4"
API_TOKEN = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_TOKEN}

ALERTA_GOLS_EXTRA = 0.5  # Alerta se gols esperados > linha + 0.5
REFRESH_INTERVAL = 30    # Atualiza a cada 30 segundos

# =============================
# Funções auxiliares
# =============================
@st.cache_data(ttl=60)
def listar_competicoes():
    try:
        r = requests.get(f"{BASE_URL}/competitions", headers=HEADERS)
        r.raise_for_status()
        return r.json().get("competitions", [])
    except Exception as e:
        return {"erro": str(e)}

@st.cache_data(ttl=60)
def listar_partidas(codigo, data_escolhida=None, status=None):
    try:
        url = f"{BASE_URL}/competitions/{codigo}/matches"
        params = {}
        if data_escolhida:
            dt_to = (data_escolhida + timedelta(days=1)).strftime("%Y-%m-%d")
            params["dateFrom"] = data_escolhida.strftime("%Y-%m-%d")
            params["dateTo"] = dt_to
        if status:
            params["status"] = status
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception as e:
        return {"erro": str(e)}

@st.cache_data(ttl=60)
def historico_time(time_id, limite=10):
    try:
        r = requests.get(f"{BASE_URL}/teams/{time_id}/matches?status=FINISHED&limit={limite}", headers=HEADERS)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception:
        return []

def calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols=2.5, limite=10):
    home_historico = historico_time(home_id, limite)
    away_historico = historico_time(away_id, limite)

    if not home_historico or not away_historico:
        return None, "Sem histórico suficiente"

    def media_gols(matches, time_id):
        gols_marcados, gols_sofridos, cont = 0, 0, 0
        for m in matches:
            if not isinstance(m, dict):
                continue
            ht = m.get("homeTeam", {})
            at = m.get("awayTeam", {})
            score = m.get("score", {}).get("fullTime", {})
            if not ht or not at or not score:
                continue
            ht_id = ht.get("id")
            at_id = at.get("id")
            if not ht_id or not at_id:
                continue
            if ht_id == time_id:
                gols_marcados += score.get("home", 0)
                gols_sofridos += score.get("away", 0)
            elif at_id == time_id:
                gols_marcados += score.get("away", 0)
                gols_sofridos += score.get("home", 0)
            cont += 1
        if cont == 0:
            return 0, 0
        return gols_marcados/cont, gols_sofridos/cont

    home_marcados, home_sofridos = media_gols(home_historico, home_id)
    away_marcados, away_sofridos = media_gols(away_historico, away_id)

    gols_esperados = (home_marcados + away_sofridos + away_marcados + home_sofridos)/2
    resultado = f"Mais de {linha_gols} 🟢" if gols_esperados > linha_gols else f"Menos de {linha_gols} 🔴"

    alerta = gols_esperados > (linha_gols + ALERTA_GOLS_EXTRA)
    return gols_esperados, resultado, alerta

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="Painel Mais/Menos Gols - Alertas", layout="centered")
st.title("⚽ Painel Profissional - Mais/Menos Gols com Alertas 🔔")

data_escolhida = st.date_input("Escolha a data:", value=date.today())
status_selecionado = st.selectbox("Status da partida:", ["SCHEDULED", "LIVE", "FINISHED"], index=0)

competicoes_disponiveis = []
dados_comp = listar_competicoes()
if isinstance(dados_comp, dict) and dados_comp.get("erro"):
    st.error(f"❌ {dados_comp['erro']}")
elif dados_comp:
    for c in dados_comp:
        codigo = c.get("code", "")
        partidas = listar_partidas(codigo, data_escolhida, status_selecionado)
        if isinstance(partidas, list) and partidas:
            competicoes_disponiveis.append({"nome": c.get("name","Desconhecido"), "codigo": codigo})

if not competicoes_disponiveis:
    st.warning("⚠️ Nenhuma competição disponível com partidas nesta data.")
else:
    nomes = [f"{c['nome']} ({c['codigo']})" for c in competicoes_disponiveis]
    selecao = st.selectbox("Selecione uma competição:", nomes)

    if selecao:
        codigo = selecao.split("(")[1].split(")")[0]
        linha_gols = st.number_input("Linha de gols:", min_value=0.0, max_value=10.0, value=2.5, step=0.1)

        st.info(f"⏱️ Atualizando automaticamente a cada {REFRESH_INTERVAL} segundos...")

        placeholder = st.empty()

        while True:
            partidas = listar_partidas(codigo, data_escolhida, status_selecionado)
            jogos, gols_esperados_list, resultados_list, alertas_list = [], [], [], []

            for p in partidas:
                home = p.get("homeTeam")
                away = p.get("awayTeam")
                if not home or not away:
                    continue
                home_id, away_id = home.get("id"), away.get("id")
                if not home_id or not away_id:
                    continue
                gols_esperados, resultado, alerta = calcular_mais_menos_gols_avancado(home_id, away_id, linha_gols)
                if gols_esperados is None:
                    continue
                jogos.append(f"{home.get('name','Desconhecido')} vs {away.get('name','Desconhecido')}")
                gols_esperados_list.append(gols_esperados)
                resultados_list.append(resultado)
                alertas_list.append(alerta)

            if jogos:
                df = pd.DataFrame({
                    "Partida": jogos,
                    "Gols Esperados": gols_esperados_list,
                    "Sugestão": resultados_list,
                    "Alerta": alertas_list
                })
                with placeholder.container():
                    st.subheader("Tabela de Partidas")
                    st.dataframe(df.style.apply(lambda x: ["background-color: yellow" if v else "" 
                                                           for v in x], subset=["Alerta"]))

                    fig = px.bar(df, x="Partida", y="Gols Esperados", text="Sugestão",
                                 color=df["Alerta"], color_discrete_map={True: "orange", False: "blue"})
                    fig.update_layout(title=f"Gols esperados vs Linha ({linha_gols})",
                                      yaxis_title="Gols esperados",
                                      xaxis_title="Partidas",
                                      xaxis_tickangle=-45,
                                      template="plotly_white",
                                      height=500)
                    st.plotly_chart(fig)
            else:
                placeholder.warning("⚠️ Nenhum jogo encontrado ou sem histórico suficiente para cálculo.")

            time.sleep(REFRESH_INTERVAL)
