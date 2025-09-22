# Futebol_Alertas_OpenLiga_Top3.py
import streamlit as st
import requests
import json
import os
import math
from datetime import datetime, date, timedelta
from collections import defaultdict
import numpy as np

# =============================
# Configurações OpenLigaDB + Telegram
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "Premier League (Inglaterra)": "pl",
    "La Liga (Espanha)": "es1",
    "Serie A (Itália)": "it1",
    "Ligue 1 (França)": "fr1",
    "Brasileirão Série A": "br1"
}

TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

def enviar_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        st.error(f"Erro ao enviar para Telegram: {e}")

# =============================
# Funções auxiliares
# =============================
def parse_data(data_str):
    return datetime.fromisoformat(data_str.replace("Z", "+00:00"))

def buscar_jogos_openliga(league, season, dia=None):
    url = f"{OPENLIGA_BASE}/getmatchdata/{league}/{season}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        jogos = resp.json()
        if dia:
            return [j for j in jogos if parse_data(j["matchDateTime"]).date() == dia]
        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos da {league}: {e}")
        return []

def calcular_medias_openliga(matches):
    stats = defaultdict(lambda: {"feitos": [], "sofridos": []})
    for m in matches:
        if not m.get("matchIsFinished"):
            continue
        home = m["team1"]["teamName"]
        away = m["team2"]["teamName"]
        gols_home = m["matchResults"][-1]["pointsTeam1"]
        gols_away = m["matchResults"][-1]["pointsTeam2"]
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

def calcular_media_confrontos(matches, team1, team2):
    gols_t1, gols_t2, jogos = [], [], []
    for m in matches:
        if not m.get("matchIsFinished"):
            continue
        h = m["team1"]["teamName"]
        a = m["team2"]["teamName"]
        if {h, a} == {team1, team2}:
            gols_home = m["matchResults"][-1]["pointsTeam1"]
            gols_away = m["matchResults"][-1]["pointsTeam2"]
            if h == team1:
                gols_t1.append(gols_home)
                gols_t2.append(gols_away)
            else:
                gols_t1.append(gols_away)
                gols_t2.append(gols_home)
            jogos.append(m)
    if not jogos:
        return None, None
    return np.mean(gols_t1), np.mean(gols_t2)

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

def selecionar_top3_distintos(jogos, chave):
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
def conferir_alertas_openliga(league, season, faixa, jogos_previstos):
    jogos_api = buscar_jogos_openliga(league, season)
    lista_final = []
    for jogo in jogos_api:
        if not jogo.get("matchIsFinished"):
            continue
        home = jogo["team1"]["teamName"]
        away = jogo["team2"]["teamName"]
        partida = f"{home} vs {away}"
        gols_home = jogo["matchResults"][-1]["pointsTeam1"]
        gols_away = jogo["matchResults"][-1]["pointsTeam2"]
        total_gols = gols_home + gols_away
        placar = f"{gols_home}x{gols_away}"
        limite = int(faixa.strip("+").split(".")[0])
        status = "GREEN" if total_gols > limite else "RED"
        if any(t in partida for t in jogos_previstos):
            lista_final.append({"faixa": faixa, "jogo": partida, "placar": placar, "status": status})
    return lista_final

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
st.title("⚽ Alertas Futebol - OpenLigaDB")

opcao_liga = st.selectbox("Escolha a liga:", list(ligas_openliga.keys()))
league = ligas_openliga[opcao_liga]
ano = st.number_input("Ano da temporada", min_value=2015, max_value=date.today().year, value=date.today().year)

aba = st.radio("Selecione:", ["Gerar Alertas", "Histórico", "Conferência"])

if aba == "Gerar Alertas":
    st.subheader("📢 Alertas Pré-Jogo")
    jogos = buscar_jogos_openliga(league, ano, date.today())
    medias = calcular_medias_openliga(buscar_jogos_openliga(league, ano))
    jogos_info = []
    for j in jogos:
        home, away = j["team1"]["teamName"], j["team2"]["teamName"]
        if home not in medias or away not in medias:
            continue
        exp_home = (medias[home]["feitos"] + medias[away]["sofridos"]) / 2
        exp_away = (medias[away]["feitos"] + medias[home]["sofridos"]) / 2
        h2h_home, h2h_away = calcular_media_confrontos(buscar_jogos_openliga(league, ano), home, away)
        if h2h_home and h2h_away:
            exp_home = (exp_home + h2h_home) / 2
            exp_away = (exp_away + h2h_away) / 2
        jogos_info.append({
            "home": home, "away": away,
            "prob_1_5": probabilidade_over(exp_home, exp_away, 1),
            "prob_2_5": probabilidade_over(exp_home, exp_away, 2),
            "prob_3_5": probabilidade_over(exp_home, exp_away, 3)
        })
    for faixa, chave in [("+1.5", "prob_1_5"), ("+2.5", "prob_2_5"), ("+3.5", "prob_3_5")]:
        top3 = selecionar_top3_distintos(jogos_info, chave)
        if not top3:
            continue
        msg = f"🔥 TOP 3 {faixa} - {opcao_liga}\n"
        for j in top3:
            msg += f"⚽ {j['home']} vs {j['away']} → {j[chave]}%\n"
        enviar_telegram(msg)
        st.text_area(f"Top 3 {faixa}", msg, height=150)
        with open(f"previstos_{faixa}.json", "w") as f:
            json.dump([f"{j['home']} vs {j['away']}" for j in top3], f)

elif aba == "Histórico":
    st.subheader("📜 Histórico de Jogos")
    jogos = buscar_jogos_openliga(league, ano)
    for j in jogos:
        data_j = parse_data(j["matchDateTime"]).strftime("%d/%m/%Y %H:%M")
        home, away = j["team1"]["teamName"], j["team2"]["teamName"]
        status = "Encerrado" if j["matchIsFinished"] else "Agendado"
        placar = ""
        if j["matchIsFinished"]:
            placar = f" {j['matchResults'][-1]['pointsTeam1']}x{j['matchResults'][-1]['pointsTeam2']}"
        st.write(f"📅 {data_j} - ⚽ {home} vs {away} → {status}{placar}")

elif aba == "Conferência":
    st.subheader("📊 Conferência Pós-Jogo")
    lista_final = []
    for faixa in ["+1.5", "+2.5", "+3.5"]:
        if os.path.exists(f"previstos_{faixa}.json"):
            with open(f"previstos_{faixa}.json") as f:
                previstos = json.load(f)
            lista_final.extend(conferir_alertas_openliga(league, ano, faixa, previstos))
    if lista_final:
        processar_lista_e_mandar(lista_final)
    else:
        st.info("Nenhum jogo previsto para conferir ainda.")
