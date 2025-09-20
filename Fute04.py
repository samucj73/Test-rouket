# FutebolApp_OpenLigaDB_Telegram.py
import os
import json
import time
from datetime import datetime
import requests
import streamlit as st

# =============================
# Configurações
# =============================
CACHE_FILE = "openligadb_cache.json"
CACHE_TTL = 300  # tempo de cache em segundos (5 minutos)
OPENLIGA_BASE = "https://api.openligadb.de"

TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# =============================
# Funções utilitárias
# =============================
def get_from_openligadb(url):
    """Busca dados da OpenLigaDB com cache local"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

        if (time.time() - cache["timestamp"]) < CACHE_TTL and cache["url"] == url:
            return cache["data"]

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"url": url, "timestamp": time.time(), "data": data}, f, ensure_ascii=False, indent=2)
        return data
    else:
        st.error(f"Erro ao chamar OpenLigaDB: {response.status_code}")
        return None


def get_matches(liga, temporada):
    """Pega todos os jogos de uma liga/temporada"""
    url = f"{OPENLIGA_BASE}/getmatchdata/{liga}/{temporada}"
    return get_from_openligadb(url)


def calcular_media_gols(matches):
    """Calcula médias de gols feitos/sofridos por time na temporada"""
    stats = {}

    for match in matches:
        if not match.get("MatchResults"):
            continue

        home = match["Team1"]["TeamName"]
        away = match["Team2"]["TeamName"]

        result = match["MatchResults"][-1]
        gols_home = result["PointsTeam1"]
        gols_away = result["PointsTeam2"]

        for team, gf, gs in [(home, gols_home, gols_away), (away, gols_away, gols_home)]:
            if team not in stats:
                stats[team] = {"jogos": 0, "gf": 0, "gs": 0}

            stats[team]["jogos"] += 1
            stats[team]["gf"] += gf
            stats[team]["gs"] += gs

    medias = {}
    for team, d in stats.items():
        if d["jogos"] > 0:
            medias[team] = {"gf": d["gf"] / d["jogos"], "gs": d["gs"] / d["jogos"]}
    return medias


def calcular_tendencia_confianca_realista(media_h2h, media_casa, media_fora):
    """Cálculo realista de tendência +1.5 gols"""
    estimativa = (media_h2h + media_casa + media_fora) / 3
    if estimativa >= 3.0:
        return estimativa, 80, True
    elif estimativa >= 2.0:
        return estimativa, 65, True
    elif estimativa >= 1.5:
        return estimativa, 55, True
    else:
        return estimativa, 40, False


def calcular_tendencia_btts(media_home, media_away):
    """Estima probabilidade de ambas marcam"""
    # se os dois marcam e sofrem acima de 1 → alta chance de BTTS
    score_home = media_home["gf"] + media_home["gs"]
    score_away = media_away["gf"] + media_away["gs"]
    estimativa = (score_home + score_away) / 2

    if estimativa >= 3.5:
        return estimativa, 80, True
    elif estimativa >= 3.0:
        return estimativa, 65, True
    elif estimativa >= 2.5:
        return estimativa, 55, True
    else:
        return estimativa, 40, False


def send_telegram_message(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")


# =============================
# App Streamlit
# =============================
st.title("⚽ Scanner de Jogos - OpenLigaDB + Telegram")

# Ligas disponíveis (códigos da OpenLigaDB)
ligas = {
    "Bundesliga 1": "bl1",
    "Bundesliga 2": "bl2",
    "Premier League": "pl",
    "Brasileirão Série A": "bra1",
    "Brasileirão Série B": "bra2",
}

tabs = st.tabs(["Jogos de Hoje", "Histórico"])

# =============================
# Aba 0 - Jogos de hoje
# =============================
with tabs[0]:
    liga_nome = st.selectbox("Escolha a liga:", list(ligas.keys()))
    temporada = st.number_input("Ano da temporada", min_value=2000, max_value=datetime.now().year, value=datetime.now().year)

    if st.button("🔍 Buscar jogos do dia"):
        matches = get_matches(ligas[liga_nome], temporada)

        if matches:
            medias = calcular_media_gols(matches)
            hoje = datetime.now().date()
            jogos_hoje = [
                m for m in matches
                if "MatchDateTimeUTC" in m and datetime.fromisoformat(m["MatchDateTimeUTC"].replace("Z", "+00:00")).date() == hoje
            ]

            st.subheader(f"Jogos de hoje ({len(jogos_hoje)}) - {liga_nome}")

            for match in jogos_hoje:
                home = match["Team1"]["TeamName"]
                away = match["Team2"]["TeamName"]

                if home in medias and away in medias:
                    media_h2h = (medias[home]["gf"] + medias[away]["gf"]) / 2
                    estimativa, confianca, tendencia = calcular_tendencia_confianca_realista(media_h2h, medias[home]["gf"], medias[away]["gf"])

                    if tendencia:
                        msg = f"🔥 <b>{home} x {away}</b>\n📅 {hoje}\nTendência: +1.5 gols\nConfiança: {confianca}%\nEstimativa: {estimativa:.2f}"
                        st.success(msg, icon="✅")
                        send_telegram_message(msg)

                    # Agora checa BTTS
                    estimativa_btts, confianca_btts, tendencia_btts = calcular_tendencia_btts(medias[home], medias[away])
                    if tendencia_btts:
                        msg_btts = f"⚡ <b>{home} x {away}</b>\n📅 {hoje}\nTendência: Ambas Marcam\nConfiança: {confianca_btts}%\nForça: {estimativa_btts:.2f}"
                        st.warning(msg_btts, icon="⚡")
                        send_telegram_message(msg_btts)

        else:
            st.warning("Nenhum jogo encontrado ou problema na API.")

# =============================
# Aba 1 - Histórico
# =============================
with tabs[1]:
    liga_nome_hist = st.selectbox("Liga histórica:", list(ligas.keys()), key="hist")
    temporada_hist = st.number_input("Ano da temporada histórica", min_value=2000, max_value=datetime.now().year, value=datetime.now().year - 1, key="hist_year")

    if st.button("📜 Buscar histórico"):
        matches_hist = get_matches(ligas[liga_nome_hist], temporada_hist)
        if matches_hist:
            medias_hist = calcular_media_gols(matches_hist)
            st.subheader(f"Médias da temporada {temporada_hist} - {liga_nome_hist}")
            for team, d in medias_hist.items():
                st.write(f"{team}: {d['gf']:.2f} GF | {d['gs']:.2f} GS")
        else:
            st.warning("Nenhum dado histórico encontrado.")
