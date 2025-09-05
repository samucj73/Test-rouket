import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime

# =============================
# Configuração da API
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"  # substitua pela sua chave
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}

# =============================
# Buscar códigos oficiais das ligas
# =============================
@st.cache_data
def carregar_competicoes():
    uri = f"{BASE_URL}/competitions"
    response = requests.get(uri, headers=HEADERS)
    comps = {}
    if response.status_code == 200:
        data = response.json()
        for comp in data.get("competitions", []):
            name = comp["name"]
            code = comp["code"]
            comps[name] = code
    else:
        st.warning(f"Erro ao buscar competições: {response.status_code}")
    return comps

COMPETICOES = carregar_competicoes()

# =============================
# Funções auxiliares
# =============================
def buscar_partidas(codigo_liga=None, status="FINISHED"):
    """Busca partidas já finalizadas de uma liga"""
    uri = f"{BASE_URL}/matches"
    response = requests.get(uri, headers=HEADERS)
    matches = []
    if response.status_code == 200:
        data = response.json()
        matches = data.get('matches', [])
        if codigo_liga:
            matches = [m for m in matches if m.get("competition", {}).get("code") == codigo_liga]
        matches = [m for m in matches if m.get("status") == status]
    else:
        st.warning(f"Erro ao buscar partidas: {response.status_code}")
    return matches

def calcular_estatisticas(time_id, partidas, linha=2.5, n=10):
    ultimos = [p for p in partidas if p["homeTeam"]["id"] == time_id or p["awayTeam"]["id"] == time_id]
    ultimos = ultimos[-n:]

    gols = []
    overs = 0
    for p in ultimos:
        gh = p["score"]["fullTime"]["home"]
        ga = p["score"]["fullTime"]["away"]
        if gh is None or ga is None:
            continue
        total = gh + ga
        gols.append(total)
        if total > linha:
            overs += 1

    if not gols:
        return 0, 0
    media = np.mean(gols)
    prob_over = (overs / len(gols)) * 100
    return round(media, 2), round(prob_over, 1)

def analisar_jogo(home, away, partidas, linha=2.5):
    mediaA, overA = calcular_estatisticas(home["id"], partidas, linha)
    mediaB, overB = calcular_estatisticas(away["id"], partidas, linha)
    media_total = round((mediaA + mediaB)/2, 2)
    prob_over = round((overA + overB)/2, 1)
    prob_under = 100 - prob_over
    return media_total, prob_over, prob_under

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="Mais/Menos Gols", layout="wide")
st.title("⚽ Mais/Menos Gols - Previsões Inteligentes")

# Seleção de liga e linha de gols
col1, col2 = st.columns(2)
with col1:
    liga_escolhida = st.selectbox("🏆 Campeonato", list(COMPETICOES.keys()))
with col2:
    linha_escolhida = st.radio("📏 Linha de gols", [1.5, 2.5, 3.5], horizontal=True)

tipo_aposta = st.radio("🎯 Analisar", ["Mais (Over)", "Menos (Under)"], horizontal=True)

# =============================
# Buscar partidas já finalizadas da liga
# =============================
codigo_liga = COMPETICOES[liga_escolhida]
partidas = buscar_partidas(codigo_liga=codigo_liga)

if partidas:
    st.subheader(f"📊 Últimos jogos de {liga_escolhida} ({len(partidas)} partidas)")

    dados_tabela = []
    recomendados = []

    for jogo in partidas[-20:]:  # analisar últimos 20 jogos
        home = jogo["homeTeam"]
        away = jogo["awayTeam"]

        media, prob_over, prob_under = analisar_jogo(home, away, partidas, linha_escolhida)

        dados_tabela.append({
            "Jogo": f"{home['name']} x {away['name']}",
            "Média Gols": media,
            f"Prob. Over {linha_escolhida}": f"{prob_over}%",
            f"Prob. Under {linha_escolhida}": f"{prob_under}%"
        })

        if tipo_aposta == "Mais (Over)" and prob_over >= 60:
            recomendados.append(("over", home, away, media, prob_over))
        elif tipo_aposta == "Menos (Under)" and prob_under >= 60:
            recomendados.append(("under", home, away, media, prob_under))

    # Tabela geral
    df = pd.DataFrame(dados_tabela)
    st.dataframe(df, use_container_width=True)

    # Jogos recomendados
    if recomendados:
        st.subheader("🔥 Jogos recomendados")
        for tipo, home, away, media, prob in recomendados:
            cor = "21bf73" if tipo=="over" else "f39c12"
            emoji = "🔥" if tipo=="over" else "🛡️"
            st.markdown(f"""
                <div style='border-left:5px solid #{cor}; padding:10px; margin:5px; background-color:#1e222b; border-radius:8px'>
                    <h4>{home['name']} x {away['name']}</h4>
                    <p>📊 Média gols: <b>{media}</b></p>
                    <p>{emoji} Probabilidade {tipo}: <b>{prob}%</b></p>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhum jogo forte identificado para essa linha.")

else:
    st.info("Nenhuma partida disponível para esta liga.")
