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
# Configurações API TheSportsDB
# =============================
API_KEY = "123"  # sua chave
BASE_URL_TSDB = f"https://www.thesportsdb.com/api/v2/json/{API_KEY}"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
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

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

def carregar_cache_ligas():
    return carregar_json(CACHE_LIGAS)

def salvar_cache_ligas(dados):
    salvar_json(CACHE_LIGAS, dados)

# =============================
# Funções Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except:
        pass

# =============================
# Carregar ligas TheSportsDB
# =============================
def obter_ligas():
    cache = carregar_cache_ligas()
    if cache:
        return cache
    try:
        url = f"{BASE_URL_TSDB}/all_leagues.php"
        headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ligas = {liga["strLeague"]: liga["idLeague"] for liga in data.get("leagues", [])}
        salvar_cache_ligas(ligas)
        return ligas
    except Exception as e:
        st.error(f"Erro ao obter lista de ligas do TheSportsDB: {e}")
        return {}

# =============================
# Carregar jogos do dia
# =============================
def obter_jogos(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]

    try:
        url = f"{BASE_URL_TSDB}/eventsday.php?d={data}&l={liga_id}"
        headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        jogos = resp.json().get("events", [])
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao obter jogos da liga {liga_id}: {e}")
        return []

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos de Gols")

data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# -----------------------------
# Seleção de ligas
# -----------------------------
ligas_disponiveis = obter_ligas()
todas_ligas = st.checkbox("📌 Buscar jogos de todas as ligas do dia", value=True)
liga_selecionada = None
if not todas_ligas:
    liga_selecionada = st.selectbox("📌 Escolha a liga:", list(ligas_disponiveis.keys()))

# -----------------------------
# Botão para buscar partidas
# -----------------------------
if st.button("🔍 Buscar partidas"):
    ligas_busca = ligas_disponiveis.values() if todas_ligas else [ligas_disponiveis[liga_selecionada]]
    st.write(f"⏳ Buscando jogos para {data_selecionada}...")

    for liga_id in ligas_busca:
        jogos = obter_jogos(liga_id, hoje)
        st.write(f"🏟️ Liga ID {liga_id} - {len(jogos)} jogos encontrados")
        for j in jogos:
            st.write(f"{j.get('strHomeTeam')} vs {j.get('strAwayTeam')} - {j.get('dateEvent')}")

# =============================
# O restante da lógica de alertas, PDFs e cálculo de tendência
# você já pode integrar aqui mantendo suas funções existentes.
# =============================
