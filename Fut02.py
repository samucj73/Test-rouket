# Futebol_Alertas_FD.py
import streamlit as st
import requests
import json
import os
import math
from datetime import datetime, date
from collections import defaultdict
import numpy as np

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

# =============================
# Buscar jogos do dia por liga
# =============================
def buscar_jogos_fd(league_id, dia=None):
    if dia is None:
        dia = date.today()
    dia_str = dia.strftime("%Y-%m-%d")
    url = f"{BASE_URL_FD}/competitions/{league_id}/matches?dateFrom={dia_str}&dateTo={dia_str}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except Exception as e:
        st.error(f"Erro ao buscar jogos: {e}")
        return []

# =============================
# Calcular médias de gols
# =============================
def calcular_medias_fd(matches):
    stats = defaultdict(lambda: {"feitos": [], "sofridos": []})
    for m in matches:
        if m["status"] != "FINISHED":
            continue
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        gols_home = m["score"]["fullTime"]["home"] or 0
        gols_away = m["score"]["fullTime"]["away"] or 0
        stats[home]["feitos"].append(gols_home)
        stats[home]["sofridos"].append(gols_away)
        stats[away]["feitos"].append(gols_away)
        stats[away]["sofridos"].append(gols_home)
    medias = {}
    for t, val in stats.items():
        feitos = np.mean(val["feitos"]) if val["feitos"] else 1.2
        sofridos = np.mean(val["sofridos"]) if val["sofridos"] else 1.2
        medias[t] = {"feitos": feitos, "sofridos": sofridos}
    return medias

# =============================
# Probabilidade via Poisson
# =============================
def probabilidade_over(gols_casa, gols_fora, limite):
    max_gols = 10
    prob = 0
    for i in range(max_gols):
        for j in range(max_gols):
            p = (math.exp(-gols_casa) * gols_casa**i / math.factorial(i)) * \
                (math.exp(-gols_fora) * gols_fora**j / math.factorial(j))
            if i + j > limite:
                prob += p
    return round(prob * 100, 2)

# =============================
# Selecionar Top 3 distintos
# =============================
def selecionar_top3(jogos, chave):
    usados = set()
    top3 = []
    for jogo in sorted(jogos, key=lambda x: x[chave], reverse=True):
        times = (jogo["home"], jogo["away"])
        if any(t in usados for t in times):
            continue
        top3.append(jogo)
        usados.update(times)
        if len(top3) == 3:
            break
    return top3

# =============================
# Conferência dos resultados
# =============================
def conferir_alertas_fd(league_id, faixa, jogos_previstos):
    jogos_api = buscar_jogos_fd(league_id)
    lista_final = []
    for jogo in jogos_api:
        home = jogo["homeTeam"]["name"]
        away = jogo["awayTeam"]["name"]
        partida = f"{home} vs {away}"
        ft = jogo["score"]["fullTime"]
        gols_home = ft.get("home", 0) or 0
        gols_away = ft.get("away", 0) or 0
        total_gols = gols_home + gols_away
        placar = f"{gols_home}x{gols_away}"
        limite = int(faixa.strip("+").split(".")[0])
        status = "GREEN" if total_gols > limite else "RED"
        if any(t in partida for t in jogos_previstos):
            lista_final.append({"faixa": faixa, "jogo": partida, "placar": placar, "status": status})
    return lista_final

# =============================
# Processar e mandar conferência
# =============================
def processar_lista_e_mandar(lista_final):
    for faixa in ["+1.5", "+2.5", "+3.5"]:
        jogos_faixa = [j for j in lista_final if j["faixa"] == faixa]
        if not jogos_faixa:
            continue
        msg = f"📊 Conferência {faixa}\n"
        for jogo in jogos_faixa:
            msg += f"⚽ {jogo['jogo']} → {jogo['placar']} - {jogo['status']}\n"
        enviar_telegram(msg)
        st.text_area(f"Conferência {faixa}", msg, height=150)

# =============================
# App Streamlit
# =============================
st.title("⚽ Alertas Futebol - Football-Data.org")

ligas_fd = {
    "Premier League": 2021,
    "La Liga": 2014,
    "Serie A (Itália)": 2019,
    "Bundesliga": 2002,
    "Brasileirão Série A": 2013
}

opcao_liga = st.selectbox("Escolha a liga:", list(ligas_fd.keys()))
league_id = ligas_fd[opcao_liga]

aba = st.radio("Selecione:", ["Gerar Alertas", "Conferência"])

if aba == "Gerar Alertas":
    st.subheader("📢 Alertas Pré-Jogo")
    matches = buscar_jogos_fd(league_id)
    medias = calcular_medias_fd(matches)
    jogos_info = []
    for m in matches:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        if home not in medias or away not in medias:
            continue
        exp_home = (medias[home]["feitos"] + medias[away]["sofridos"]) / 2
        exp_away = (medias[away]["feitos"] + medias[home]["sofridos"]) / 2
        prob_15 = probabilidade_over(exp_home, exp_away, 1)
        prob_25 = probabilidade_over(exp_home, exp_away, 2)
        prob_35 = probabilidade_over(exp_home, exp_away, 3)
        jogos_info.append({"home": home, "away": away, "prob_1_5": prob_15, "prob_2_5": prob_25, "prob_3_5": prob_35})

    for faixa, chave in [("+1.5", "prob_1_5"), ("+2.5", "prob_2_5"), ("+3.5", "prob_3_5")]:
        top3 = selecionar_top3(jogos_info, chave)
        if not top3:
            continue
        msg = f"🔥 TOP 3 {faixa} - {opcao_liga}\n"
        for j in top3:
            msg += f"⚽ {j['home']} vs {j['away']} → {j[chave]}%\n"
        enviar_telegram(msg)
        st.text_area(f"Top 3 {faixa}", msg, height=150)
        # salva previsões
        with open(f"previstos_{faixa}.json", "w") as f:
            json.dump([f"{j['home']} vs {j['away']}" for j in top3], f)

elif aba == "Conferência":
    st.subheader("📊 Conferência Pós-Jogo")
    lista_final = []
    for faixa in ["+1.5", "+2.5", "+3.5"]:
        if os.path.exists(f"previstos_{faixa}.json"):
            with open(f"previstos_{faixa}.json") as f:
                previstos = json.load(f)
            lista_final.extend(conferir_alertas_fd(league_id, faixa, previstos))
    if lista_final:
        processar_lista_e_mandar(lista_final)
    else:
        st.info("Nenhum jogo previsto para conferir ainda.")
