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
API_KEY = "123"  # Sua chave do TheSportsDB
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
# Persistência e cache
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
# Envio de Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except:
        pass

def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["strHomeTeam"]
    away = fixture["strAwayTeam"]
    data_str = fixture.get("dateEvent", fixture.get("dateEventLocal", ""))
    data_jogo = datetime.strptime(data_str, "%Y-%m-%d") if data_str else datetime.now()
    data_formatada = data_jogo.strftime("%d/%m/%Y")
    hora_formatada = data_jogo.strftime("%H:%M")
    competicao = fixture.get("strLeague", "Desconhecido")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Liga: {competicao}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["idEvent"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {
            "tendencia": tendencia,
            "estimativa": estimativa,
            "confianca": confianca,
            "conferido": False
        }
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Obter ligas do TheSportsDB
# =============================
def obter_ligas():
    cache = carregar_cache_ligas()
    if cache:
        return cache
    try:
        url = f"{BASE_URL_TSDB}/all_leagues.php"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ligas = {liga["strLeague"]: liga["idLeague"] for liga in data.get("leagues", []) if liga["strSport"] == "Soccer"}
        salvar_cache_ligas(ligas)
        return ligas
    except Exception as e:
        st.error(f"Erro ao obter lista de ligas do TheSportsDB: {e}")
        return {}

# =============================
# Obter jogos do dia
# =============================
def obter_jogos_da_liga(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]

    try:
        url = f"{BASE_URL_TSDB}/eventsday.php?d={data}&l={liga_id}"
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
# Obter classificação da liga (simulada)
# =============================
def obter_classificacao(liga_id):
    # TheSportsDB não fornece classificação em v2 para todas as ligas, usar cache vazio ou gerar dummy
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]
    # Simula classificação
    classificacao = {}
    jogos = obter_jogos_da_liga(liga_id, datetime.today().strftime("%Y-%m-%d"))
    for j in jogos:
        classificacao[j["strHomeTeam"]] = {"scored":1, "against":1, "played":1}
        classificacao[j["strAwayTeam"]] = {"scored":1, "against":1, "played":1}
    cache[liga_id] = classificacao
    salvar_cache_classificacao(cache)
    return classificacao

# =============================
# Cálculo tendência
# =============================
def calcular_tendencia(home, away, classificacao):
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
liga_selecionada = st.selectbox("📌 Escolha a liga do dia:", ["Todas"] + list(ligas_disponiveis.keys()))

# -----------------------------
# Botão para buscar partidas
# -----------------------------
if st.button("🔍 Buscar partidas"):
    if liga_selecionada == "Todas":
        ligas_busca = list(ligas_disponiveis.values())
    else:
        ligas_busca = [ligas_disponiveis[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {data_selecionada}...")

    top_jogos = []

    for liga_id in ligas_busca:
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos_da_liga(liga_id, hoje)

        for match in jogos:
            home = match["strHomeTeam"]
            away = match["strAwayTeam"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

            verificar_enviar_alerta(match, tendencia, estimativa, confianca)

            top_jogos.append({
                "id": match["idEvent"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("strLeague", "Desconhecido"),
                "hora": datetime.strptime(match.get("dateEvent","2025-01-01"), "%Y-%m-%d"),
                "status": match.get("strStatus","DESCONHECIDO"),
            })

    # -----------------------------
    # Top N jogos
    # -----------------------------
    top_n = st.selectbox("📊 Quantos jogos mostrar no Top?", [3,5,10], index=0)
    if top_jogos:
        top_jogos_sorted = sorted(top_jogos, key=lambda x: x["confianca"], reverse=True)[:top_n]
        msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
        for j in top_jogos_sorted:
            hora_format = j["hora"].strftime("%H:%M")
            msg += (
                f"🏟️ {j['home']} vs {j['away']}\n"
                f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
                f"Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
                f"Confiança: {j['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)
        st.success(f"🚀 Top {top_n} jogos enviados para o canal alternativo 2!")
    else:
        st.warning("⚠️ Nenhum jogo disponível ainda para montar o Top.")
