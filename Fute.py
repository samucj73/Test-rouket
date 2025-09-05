import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime

# =============================
# Configuração da API
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"  # sua chave
BASE_URL = "https://api.football-data.org/v4"
headers = {"X-Auth-Token": API_KEY}

# =============================
# Ligas disponíveis
# =============================
LIGAS = {
    "Brasileirão Série A": "BSA",
    "Championship": "ELC",
    "Premier League": "PL",
    "Champions League": "CL",
    "European Championship": "EC",
    "Ligue 1": "FL1",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
    "Copa Libertadores": "CLI",
    "Primera Division": "PD",
    "FIFA World Cup": "WC"
}

# =============================
# Funções auxiliares
# =============================
def buscar_partidas(codigo_liga, status="SCHEDULED"):
    """Busca partidas de uma liga"""
    url = f"{BASE_URL}/competitions/{codigo_liga}/matches"
    params = {"status": status}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        return r.json().get("matches", [])
    else:
        st.warning(f"Não foi possível carregar partidas da liga {codigo_liga}. Status: {r.status_code}")
        return []

def calcular_estatisticas(codigo_liga, time_id, linha=2.5, n=10):
    """Média de gols e % over X.5 nos últimos n jogos"""
    partidas = buscar_partidas(codigo_liga, status="FINISHED")
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

def analisar_jogo(codigo_liga, home, away, linha=2.5):
    """Analisa um jogo baseado nos últimos resultados dos times"""
    mediaA, overA = calcular_estatisticas(codigo_liga, home["id"], linha)
    mediaB, overB = calcular_estatisticas(codigo_liga, away["id"], linha)
    media_total = round((mediaA + mediaB) / 2, 2)
    prob_over = round((overA + overB) / 2, 1)
    prob_under = 100 - prob_over
    return media_total, prob_over, prob_under

# =============================
# Estilo visual (CSS)
# =============================
st.markdown("""
    <style>
    .block-container { max-width: 950px; margin: auto; padding-top: 2rem; background-color: #0e1117; color: white; }
    h1, h2 { text-align: center; color: #1DB954; }
    .game-card { border-radius: 10px; padding: 15px; margin: 10px 0; background-color: #1e222b; }
    .over { border-left: 5px solid #21bf73; }
    .under { border-left: 5px solid #f39c12; }
    </style>
""", unsafe_allow_html=True)

# =============================
# Interface Streamlit
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

# Buscar jogos agendados
codigo_liga = LIGAS[liga_escolhida]
proximos = buscar_partidas(codigo_liga, status="SCHEDULED")
proximos = [p for p in proximos if p["utcDate"].startswith(str(data_escolhida))]

# =============================
# Resultados
# =============================
if proximos:
    st.subheader(f"📊 Jogos em {data_escolhida}")

    dados_tabela = []
    recomendados = []

    for jogo in proximos:
        home = jogo["homeTeam"]
        away = jogo["awayTeam"]

        media, prob_over, prob_under = analisar_jogo(
            codigo_liga, home, away, linha_escolhida
        )

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

    # Mostrar tabela geral
    df = pd.DataFrame(dados_tabela)
    st.dataframe(df, use_container_width=True)

    # Mostrar destaques
    if recomendados:
        st.subheader("🔥 Jogos recomendados")
        for tipo, home, away, media, prob in recomendados:
            if tipo == "over":
                st.markdown(f"""
                    <div class="game-card over">
                        <h4>{home['name']} x {away['name']}</h4>
                        <p>📊 Média gols: <b>{media}</b></p>
                        <p>🔥 Prob. Mais de {linha_escolhida}: <b>{prob}%</b></p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="game-card under">
                        <h4>{home['name']} x {away['name']}</h4>
                        <p>📊 Média gols: <b>{media}</b></p>
                        <p>🛡️ Prob. Menos de {linha_escolhida}: <b>{prob}%</b></p>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Nenhum jogo forte identificado para essa linha nessa data.")

else:
    st.info("Nenhum jogo encontrado nessa data.")
