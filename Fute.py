import streamlit as st
import requests
import numpy as np
import datetime

# =============================
# Configuração da API
# =============================
API_KEY = "SUA_CHAVE_AQUI"  # insira sua chave gratuita da Football-Data.org
BASE_URL = "https://api.football-data.org/v4"
headers = {"X-Auth-Token": API_KEY}

# =============================
# Campeonatos principais
# =============================
LIGAS = {
    "Premier League": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
    "Brasileirão Série A": "BSA",
    "Champions League": "CL"
}

# =============================
# Funções auxiliares
# =============================
def buscar_partidas(liga_id, status="SCHEDULED"):
    url = f"{BASE_URL}/competitions/{liga_id}/matches"
    params = {"status": status}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("matches", [])

def calcular_estatisticas(liga_id, time_id, linha=2.5, n=10):
    partidas = buscar_partidas(liga_id, status="FINISHED")
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

def analisar_jogo(liga_id, home, away, linha=2.5):
    mediaA, overA = calcular_estatisticas(liga_id, home["id"], linha)
    mediaB, overB = calcular_estatisticas(liga_id, away["id"], linha)
    media_total = round((mediaA + mediaB) / 2, 2)
    prob_over = round((overA + overB) / 2, 1)
    prob_under = 100 - prob_over
    return media_total, prob_over, prob_under

# =============================
# Estilo CSS
# =============================
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
        color: white;
    }
    .block-container {
        max-width: 800px;
        margin: auto;
        padding-top: 2rem;
    }
    h1, h2, h3 {
        text-align: center;
        color: #1DB954;
    }
    .game-card {
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        background-color: #1e222b;
    }
    .over {
        border-left: 5px solid #21bf73;
    }
    .under {
        border-left: 5px solid #f39c12;
    }
    </style>
""", unsafe_allow_html=True)

# =============================
# Interface
# =============================
st.title("⚽ Mais/Menos Gols - Previsões Inteligentes")

col1, col2 = st.columns(2)
with col1:
    liga_escolhida = st.selectbox("🏆 Campeonato", list(LIGAS.keys()))
with col2:
    data_escolhida = st.date_input(
        "📅 Data do jogo",
        value=datetime.date.today(),
        min_value=datetime.date.today(),
        max_value=datetime.date.today() + datetime.timedelta(days=7)
    )

col3, col4 = st.columns(2)
with col3:
    linha_escolhida = st.radio("📏 Linha de gols", [1.5, 2.5, 3.5], horizontal=True)
with col4:
    tipo_aposta = st.radio("🎯 Analisar", ["Mais (Over)", "Menos (Under)"], horizontal=True)

# Buscar jogos
proximos = buscar_partidas(LIGAS[liga_escolhida], status="SCHEDULED")

# Filtrar pela data
proximos = [
    p for p in proximos
    if p["utcDate"].startswith(str(data_escolhida))
]

# =============================
# Resultados
# =============================
if proximos:
    st.subheader(f"📊 Jogos em {data_escolhida}")
    encontrados = 0

    for jogo in proximos:
        home = jogo["homeTeam"]
        away = jogo["awayTeam"]

        media, prob_over, prob_under = analisar_jogo(
            LIGAS[liga_escolhida], home, away, linha_escolhida
        )

        if tipo_aposta == "Mais (Over)" and prob_over >= 60:
            encontrados += 1
            st.markdown(f"""
                <div class="game-card over">
                    <h4>{home['name']} x {away['name']}</h4>
                    <p>📊 Média gols: <b>{media}</b></p>
                    <p>🔥 Prob. Mais de {linha_escolhida}: <b>{prob_over}%</b></p>
                </div>
            """, unsafe_allow_html=True)

        elif tipo_aposta == "Menos (Under)" and prob_under >= 60:
            encontrados += 1
            st.markdown(f"""
                <div class="game-card under">
                    <h4>{home['name']} x {away['name']}</h4>
                    <p>📊 Média gols: <b>{media}</b></p>
                    <p>🛡️ Prob. Menos de {linha_escolhida}: <b>{prob_under}%</b></p>
                </div>
            """, unsafe_allow_html=True)

    if encontrados == 0:
        st.info("Nenhum jogo forte identificado para essa linha nessa data.")
else:
    st.info("Nenhum jogo encontrado nessa data.")
