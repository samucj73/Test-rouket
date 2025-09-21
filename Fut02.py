# Futebol_Alertas_OpenLiga_Top3.py
import streamlit as st
from datetime import datetime, timedelta, date
import requests
import os
import json
import math

# =============================
# Configurações OpenLigaDB + Telegram
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"
ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "Premier League (Inglaterra)": "pl",
    "La Liga (Espanha)": "pd",
    "Serie A (Itália)": "sa",
    "Ligue 1 (França)": "fl1"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =============================
# Funções Auxiliares
# =============================
def enviar_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def calcular_tendencias_avancado(home, away, classificacao):
    media_marcados_home = classificacao.get(home, {}).get("scored",0) / max(1, classificacao.get(home, {}).get("played",1))
    media_sofridos_home = classificacao.get(home, {}).get("against",0) / max(1, classificacao.get(home, {}).get("played",1))
    media_marcados_away = classificacao.get(away, {}).get("scored",0) / max(1, classificacao.get(away, {}).get("played",1))
    media_sofridos_away = classificacao.get(away, {}).get("against",0) / max(1, classificacao.get(away, {}).get("played",1))

    # Expectativa de gols total (simples)
    estimativa = (media_marcados_home + media_sofridos_home + media_marcados_away + media_sofridos_away) / 2

    tendencias = []
    if estimativa >= 3:
        tendencias.append(("Mais 3.5", round(estimativa,2), min(95, 70 + (estimativa-3)*10)))
    if estimativa >= 2:
        tendencias.append(("Mais 2.5", round(estimativa,2), min(90, 65 + (estimativa-2)*10)))
    if estimativa >= 1.5:
        tendencias.append(("Mais 1.5", round(estimativa,2), min(85, 60 + (estimativa-1.5)*10)))
    else:
        tendencias.append(("Menos 1.5", round(estimativa,2), 70))
    
    return tendencias

def buscar_jogos(liga):
    url = f"{OPENLIGA_BASE}/getmatchdata/{liga}/{date.today().year}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    return resp.json()

def processar_partidas(liga_codigo):
    partidas = buscar_jogos(liga_codigo)
    resultados = []

    # Montar "classificação fake" com médias por time
    classificacao = {}
    for p in partidas:
        home, away = p["team1"]["teamName"], p["team2"]["teamName"]
        gols_home, gols_away = 0, 0
        if p.get("matchResults"):
            for r in p["matchResults"]:
                if r["resultTypeID"] == 2:  # Final
                    gols_home, gols_away = r["pointsTeam1"], r["pointsTeam2"]
        # Atualiza estatísticas
        for team, scored, against in [(home, gols_home, gols_away), (away, gols_away, gols_home)]:
            if team not in classificacao:
                classificacao[team] = {"scored":0, "against":0, "played":0}
            classificacao[team]["scored"] += scored
            classificacao[team]["against"] += against
            classificacao[team]["played"] += 1

    for p in partidas:
        home, away = p["team1"]["teamName"], p["team2"]["teamName"]
        status = p["matchIsFinished"]
        placar = None
        if status and p.get("matchResults"):
            for r in p["matchResults"]:
                if r["resultTypeID"] == 2:
                    placar = f"{r['pointsTeam1']} x {r['pointsTeam2']}"

        tendencias = calcular_tendencias_avancado(home, away, classificacao)

        resultados.append({
            "home": home,
            "away": away,
            "status": "FINISHED" if status else "SCHEDULED",
            "placar": placar,
            "hora": datetime.fromisoformat(p["matchDateTimeUTC"]).strftime("%H:%M"),
            "liga": liga_codigo,
            "tendencias": tendencias
        })

    return resultados

# =============================
# Streamlit App
# =============================
st.title("⚽ Alertas de Futebol - OpenLiga TOP 3")

liga_nome = st.selectbox("Selecione a Liga", list(ligas_openliga.keys()))
if st.button("Buscar Partidas"):
    partidas = processar_partidas(ligas_openliga[liga_nome])

    partidas_info = []
    for p in partidas:
        partidas_info.append(p)

    # Ordena pelas estimativas mais altas (primeira tendência)
    partidas_info.sort(key=lambda x: x["tendencias"][0][1], reverse=True)
    top3 = partidas_info[:3]

    msg = "📢 *TOP 3 Jogos do Dia*\n\n"
    for jogo in top3:
        msg += f"🏟️ {jogo['home']} vs {jogo['away']}\n"
        msg += f"🕒 {jogo['hora']} BRT | Liga: {liga_nome} | Status: {jogo['status']}\n"
        if jogo['placar']:
            msg += f"📊 Placar: {jogo['placar']}\n"
        msg += "📈 Tendências:\n"
        for t in jogo["tendencias"]:
            msg += f"- {t[0]} | Estimativa: {t[1]} | Confiança: {t[2]}%\n"
        msg += "\n"

    st.text_area("Mensagem Final", msg, height=300)
    enviar_telegram(msg)
