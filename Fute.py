import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
import time

# =============================
# Configurações API-Football
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
}

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
    except:
        st.warning("Falha ao enviar mensagem para o Telegram")

# =============================
# Funções principais
# =============================
def buscar_jogos_por_data(data, competicoes=[]):
    todos_jogos = []
    for comp_id in competicoes:
        url = f"{BASE_URL}/fixtures?league={comp_id}&season={datetime.now().year}&date={data}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            jogos = response.json().get("response", [])
            for j in jogos:
                fixture_time = datetime.fromisoformat(j["fixture"]["date"].replace("Z", "+00:00"))
                todos_jogos.append({
                    "time_casa": j["teams"]["home"]["name"],
                    "time_fora": j["teams"]["away"]["name"],
                    "data": fixture_time,
                    "league": j["league"]["name"],
                    "fixture_id": j["fixture"]["id"]
                })
        else:
            st.error(f"Erro ao buscar jogos: {response.status_code}")
    return pd.DataFrame(todos_jogos)

def buscar_odd_over_1_5(fixture_id):
    """Busca odds Over 1.5 gols do jogo no endpoint /odds"""
    url = f"{BASE_URL}/odds?fixture={fixture_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None
    odds_data = response.json().get("response", [])
    for bookie in odds_data:
        for bet in bookie.get("bookmakers", []):
            for market in bet.get("bets", []):
                if market["name"] == "Over/Under":
                    for value in market.get("values", []):
                        if value["value"] == "Over 1.5":
                            return float(value["odd"])
    return None

def calcular_probabilidade(odd):
    if odd:
        return round(1 / odd, 2)
    return None

def filtrar_jogos_mais_1_5(df, limiar_prob=0.5):
    resultados = []
    for _, row in df.iterrows():
        odd = buscar_odd_over_1_5(row["fixture_id"])
        prob = calcular_probabilidade(odd)
        if prob and prob >= limiar_prob:
            row["prob_mais_1_5"] = prob
            resultados.append(row)
    df_filtrado = pd.DataFrame(resultados)
    if not df_filtrado.empty:
        df_filtrado = df_filtrado.sort_values(by="prob_mais_1_5", ascending=False)
    return df_filtrado

# =============================
# Streamlit UI
# =============================
st.title("⚽ Jogos com Probabilidade de +1.5 Gols")

# Seletor de data
data_selecionada = st.date_input(
    "Escolha a data do jogo",
    value=datetime.today()
)
data_formatada = data_selecionada.strftime("%Y-%m-%d")

# Seleção de campeonatos
competicoes_disponiveis = {
    "Premier League": 39,
    "Serie A": 61,
    "La Liga": 140,
    "Bundesliga": 78
}
competicoes_selecionadas = st.multiselect(
    "Selecione os campeonatos",
    list(competicoes_disponiveis.keys()),
    default=["Premier League", "Serie A"]
)

limiar_prob = st.slider("Limite mínimo de probabilidade (+1.5 gols)", 0.1, 1.0, 0.5, 0.05)
enviar_alerta = st.checkbox("Enviar alerta para Telegram")

if st.button("Buscar jogos"):
    ids_competicoes = [competicoes_disponiveis[c] for c in competicoes_selecionadas]
    with st.spinner("Buscando jogos e odds..."):
        df_jogos = buscar_jogos_por_data(data_formatada, ids_competicoes)
        if df_jogos.empty:
            st.warning("Nenhum jogo encontrado para a data selecionada.")
        else:
            # Filtra apenas jogos futuros
            agora = datetime.now(timezone.utc)
            df_jogos = df_jogos[df_jogos["data"] >= agora]

            df_filtrado = filtrar_jogos_mais_1_5(df_jogos, limiar_prob)
            if df_filtrado.empty:
                st.info("Nenhum jogo com probabilidade de +1.5 gols acima do limite.")
            else:
                st.success(f"{len(df_filtrado)} jogos encontrados com probabilidade >= {limiar_prob*100}%")
                st.dataframe(df_filtrado[["time_casa", "time_fora", "league", "prob_mais_1_5"]])

                if enviar_alerta:
                    for _, row in df_filtrado.iterrows():
                        msg = f"⚽ {row['time_casa']} x {row['time_fora']} ({row['league']}) - Probabilidade +1.5 gols: {row['prob_mais_1_5']*100}%"
                        enviar_telegram(msg)
                        time.sleep(1)
