import requests
import streamlit as st
import datetime
import pytz
import json
import os

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configuração Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# =============================
# Campeonatos disponíveis
# =============================
COMPETICOES_PADRAO = {
    "PL": "Premier League (Inglaterra)",
    "PD": "La Liga (Espanha)",
    "SA": "Serie A (Itália)",
    "BL1": "Bundesliga (Alemanha)",
    "FL1": "Ligue 1 (França)",
    "BSA": "Brasileirão Série A (Brasil)",
    "PPL": "Primeira Liga (Portugal)"
}

# =============================
# Funções auxiliares
# =============================

def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def buscar_jogos_fd(codigo_liga: str, data: str):
    """Busca partidas de uma liga em uma data."""
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/matches?dateFrom={data}&dateTo={data}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro buscar jogos:", resp.status_code, resp.text)
        return []
    data = resp.json()
    return data.get("matches", [])

def conferir_jogo_fd(match_id: int):
    """Consulta o status e placar final de um jogo."""
    url = f"{BASE_URL_FD}/matches/{match_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro conferir jogo:", resp.status_code, resp.text)
        return None
    return resp.json().get("match", {})

def calcular_gols_estimados(match):
    """Exemplo simples: média de gols esperada = 2.5 (ajustar futuramente com stats reais)."""
    return 2.5

def selecionar_top3_distintos(partidas, max_por_faixa=3):
    """Seleciona até 3 partidas distintas para cada faixa de gols."""
    top_15, top_25, top_35 = [], [], []

    for match in partidas:
        estimativa = calcular_gols_estimados(match)
        fixture_id = match["id"]
        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]

        partida_info = {
            "id": fixture_id,
            "home": home,
            "away": away,
            "estimativa": estimativa
        }

        if estimativa >= 1.5 and len(top_15) < max_por_faixa:
            top_15.append(partida_info)
        if estimativa >= 2.5 and len(top_25) < max_por_faixa:
            top_25.append(partida_info)
        if estimativa >= 3.5 and len(top_35) < max_por_faixa:
            top_35.append(partida_info)

    return top_15, top_25, top_35

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Futebol Alertas Top3", layout="wide")
st.title("⚽ Futebol Alertas Top3 — Football-Data.org")

aba = st.tabs(["📊 Seleção & Envio", "✅ Conferência Resultados"])

# -----------------------------
# Aba 1 - Seleção & Envio
# -----------------------------
with aba[0]:
    st.subheader("📅 Selecionar Campeonatos")
    ligas_escolhidas = st.multiselect("Escolha os campeonatos:",
                                      options=list(COMPETICOES_PADRAO.keys()),
                                      format_func=lambda x: COMPETICOES_PADRAO[x])

    hoje = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%Y-%m-%d")

    if st.button("🔎 Buscar Jogos & Enviar Alertas"):
        todas_partidas = []
        for liga in ligas_escolhidas:
            jogos = buscar_jogos_fd(liga, hoje)
            todas_partidas.extend(jogos)

        if not todas_partidas:
            st.warning("Nenhum jogo encontrado.")
        else:
            top15, top25, top35 = selecionar_top3_distintos(todas_partidas)

            mensagem = "📢 *Top3 Alertas do Dia*\n"
            for titulo, lista in [("+1.5 Gols", top15), ("+2.5 Gols", top25), ("+3.5 Gols", top35)]:
                mensagem += f"\n🎯 *{titulo}*\n"
                for p in lista:
                    mensagem += f"🏟️ {p['home']} vs {p['away']} | Estim.: {p['estimativa']}\n"

            st.code(mensagem)
            enviar_telegram(mensagem)

# -----------------------------
# Aba 2 - Conferência
# -----------------------------
with aba[1]:
    st.subheader("📊 Conferência dos Jogos")

    match_id = st.text_input("Digite o ID do jogo para conferir:")
    if st.button("Conferir Jogo"):
        info = conferir_jogo_fd(match_id)
        if not info:
            st.error("Não foi possível buscar o jogo.")
        else:
            home = info["homeTeam"]["name"]
            away = info["awayTeam"]["name"]
            status = info["status"]
            gols_home = info["score"]["fullTime"]["home"]
            gols_away = info["score"]["fullTime"]["away"]
            total = (gols_home or 0) + (gols_away or 0)

            st.write(f"🏟️ {home} vs {away}")
            st.write(f"📌 Status: {status}")
            st.write(f"⚽ Placar final: {gols_home} x {gols_away}")

            for faixa in [1.5, 2.5, 3.5]:
                resultado = "🟢 GREEN" if total > faixa else "🔴 RED"
                st.write(f"{resultado} para +{faixa} gols")
