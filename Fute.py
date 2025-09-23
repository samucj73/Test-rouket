import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações TheSportsDB
# =============================
API_KEY = "123"  # Sua chave gratuita
BASE_URL_TSDB = "https://www.thesportsdb.com/api/v2/json"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# =============================
# Caminhos de cache e alertas
# =============================
ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_LIGAS = "cache_ligas.json"

# =============================
# Funções de cache
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, dados):
    with open(caminho, "w") as f:
        json.dump(dados, f)

def carregar_alertas(): return carregar_json(ALERTAS_PATH)
def salvar_alertas(alertas): salvar_json(ALERTAS_PATH, alertas)
def carregar_cache_jogos(): return carregar_json(CACHE_JOGOS)
def salvar_cache_jogos(dados): salvar_json(CACHE_JOGOS, dados)
def carregar_cache_ligas(): return carregar_json(CACHE_LIGAS)
def salvar_cache_ligas(dados): salvar_json(CACHE_LIGAS, dados)

# =============================
# Funções Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except:
        pass

# =============================
# Obter ligas de futebol
# =============================
def obter_ligas():
    cache = carregar_cache_ligas()
    if cache:
        return cache
    try:
        url = f"{BASE_URL_TSDB}/{API_KEY}/search_all_leagues.php?s=Soccer"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ligas = {liga["strLeague"]: liga["idLeague"] for liga in data.get("countrys", [])}
        salvar_cache_ligas(ligas)
        return ligas
    except Exception as e:
        st.error(f"Erro ao obter lista de ligas do TheSportsDB: {e}")
        return {}

# =============================
# Obter jogos do dia por liga
# =============================
def obter_jogos(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]
    try:
        url = f"{BASE_URL_TSDB}/{API_KEY}/eventsday.php?d={data}&l={liga_id}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        jogos = resp.json().get("events", [])
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao obter jogos da liga {liga_id}: {e}")
        return []

# =============================
# Calcular tendência
# =============================
def calcular_tendencia(home, away, classificacao={}):
    # Mantém mesmo método que você já usava
    dados_home = classificacao.get(home, {"scored":0, "against":0, "played":1})
    dados_away = classificacao.get(away, {"scored":0, "against":0, "played":1})
    media_home_feitos = dados_home["scored"] / dados_home["played"]
    media_home_sofridos = dados_home["against"] / dados_home["played"]
    media_away_feitos = dados_away["scored"] / dados_away["played"]
    media_away_sofridos = dados_away["against"] / dados_away["played"]

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0)*10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0)*10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa)*10)
    return estimativa, confianca, tendencia

# =============================
# Enviar alerta
# =============================
def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["strHomeTeam"]
    away = fixture["strAwayTeam"]
    data_iso = fixture["dateEvent"]
    data_jogo = datetime.strptime(data_iso, "%Y-%m-%d") - timedelta(hours=3)
    data_formatada = data_jogo.strftime("%d/%m/%Y")
    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada}\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%"
    )
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["idEvent"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Streamlit Interface
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")

data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# -----------------------------
# Seleção de liga
# -----------------------------
ligas_disponiveis = obter_ligas()
liga_selecionada = st.selectbox("📌 Escolha a liga:", list(ligas_disponiveis.keys()))

if st.button("🔍 Buscar partidas"):
    liga_id = ligas_disponiveis[liga_selecionada]
    st.write(f"⏳ Buscando jogos da liga {liga_selecionada} para {hoje}...")
    jogos = obter_jogos(liga_id, hoje)
    if not jogos:
        st.warning("⚠️ Nenhum jogo encontrado para esta liga/data.")
    else:
        for match in jogos:
            home = match["strHomeTeam"]
            away = match["strAwayTeam"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away)
            verificar_enviar_alerta(match, tendencia, estimativa, confianca)
        st.success(f"✅ Alertas enviados para {len(jogos)} jogos!")

# -----------------------------
# Conferir resultados e gerar PDF
# (igual ao seu código atual)
# -----------------------------
