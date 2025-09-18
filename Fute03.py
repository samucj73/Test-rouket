import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json
from collections import defaultdict

# =============================
# Configurações Telegram + persistência
# =============================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ALERTAS_PATH = "alertas.json"
OPENLIGA_BASE = "https://api.openligadb.de"
ESPN_SCOREBOARD = "http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

# =============================
# Persistência
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

# =============================
# Telegram helper
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

# =============================
# OpenLigaDB helpers (para jogos do dia)
# =============================
def obter_jogos_liga_temporada(liga_id: str, temporada: str = None):
    try:
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}" if temporada else f"{OPENLIGA_BASE}/getmatchdata/{liga_id}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Erro obter_jogos_liga_temporada:", e)
    return []

def obter_jogos_por_data(jogos, data_iso):
    return [j for j in jogos if (j.get("matchDateTime") or j.get("matchDateTimeUTC") or "").split("T")[0] == data_iso]

# =============================
# ESPN API helpers (histórico e H2H)
# =============================
def obter_jogos_passados_espn(league, team_slug, temporadas=3):
    """
    Busca jogos passados do time usando a API ESPN.
    """
    jogos = []
    for i in range(temporadas):
        season = str(datetime.now().year - i)
        try:
            url = ESPN_SCOREBOARD.replace("{league}", league)
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for evt in data.get("events", []):
                    comps = evt.get("competitions", [])
                    if not comps: continue
                    for comp in comps:
                        teams = comp.get("competitors", [])
                        for t in teams:
                            if t.get("team",{}).get("shortDisplayName","").lower() == team_slug.lower():
                                jogos.append(evt)
            else:
                print(f"Falha ESPN {team_slug} temporada {season}")
        except Exception as e:
            print("Erro ESPN API:", e)
    return jogos

def calcular_stats_time_espn(jogos, team_name):
    gols_marc = gols_sof = jogos_validos = over15 = over25 = over35 = gd_total = 0
    for j in jogos:
        comps = j.get("competitions", [])
        if not comps: continue
        comp = comps[0]
        teams = comp.get("competitors",[])
        if len(teams)!=2: continue
        home = teams[0].get("team",{}).get("displayName","")
        away = teams[1].get("team",{}).get("displayName","")
        pts1 = teams[0].get("score",0)
        pts2 = teams[1].get("score",0)
        if pts1 is None or pts2 is None: continue
        jogos_validos +=1
        if team_name.lower() == home.lower():
            gols_marc += pts1
            gols_sof += pts2
            gd_total += (pts1 - pts2)
            total_gols = pts1 + pts2
        elif team_name.lower() == away.lower():
            gols_marc += pts2
            gols_sof += pts1
            gd_total += (pts2 - pts1)
            total_gols = pts1 + pts2
        else:
            continue
        if total_gols >= 2: over15+=1
        if total_gols >= 3: over25+=1
        if total_gols >= 4: over35+=1
    if jogos_validos==0:
        return {"jogos_validos":0,"gols_marc":0,"gols_sof":0,"media_marc":0.0,"media_sof":0.0,
                "over15_pct":0.0,"over25_pct":0.0,"over35_pct":0.0,"avg_gd":0.0}
    return {
        "jogos_validos":jogos_validos,
        "gols_marc":gols_marc,
        "gols_sof":gols_sof,
        "media_marc":round(gols_marc/jogos_validos,2),
        "media_sof":round(gols_sof/jogos_validos,2),
        "over15_pct":round(100*over15/jogos_validos,1),
        "over25_pct":round(100*over25/jogos_validos,1),
        "over35_pct":round(100*over35/jogos_validos,1),
        "avg_gd":round(gd_total/jogos_validos,2)
    }

def calcular_h2h_espn(jogos_home, jogos_away, home_name, away_name, max_h2h=6):
    """
    Calcula H2H de gols entre os times
    """
    h2h_gols = []
    for j in jogos_home:
        comps = j.get("competitions", [])
        if not comps: continue
        comp = comps[0]
        teams = comp.get("competitors",[])
        if len(teams)!=2: continue
        home = teams[0].get("team",{}).get("displayName","")
        away = teams[1].get("team",{}).get("displayName","")
        pts1 = teams[0].get("score",0)
        pts2 = teams[1].get("score",0)
        if ((home.lower()==home_name.lower() and away.lower()==away_name.lower()) or
            (home.lower()==away_name.lower() and away.lower()==home_name.lower())):
            h2h_gols.append(pts1+pts2)
    return sum(h2h_gols[-max_h2h:])/max_h2h if h2h_gols else 0.0

def calcular_estimativa_e_tendencia(match, league_slug):
    home = match["team1"]["teamName"]
    away = match["team2"]["teamName"]

    home_slug = home.lower().replace(" ","-")
    away_slug = away.lower().replace(" ","-")

    jogos_home = obter_jogos_passados_espn(league_slug, home_slug, temporadas=3)
    jogos_away = obter_jogos_passados_espn(league_slug, away_slug, temporadas=3)

    stats_home = calcular_stats_time_espn(jogos_home, home)
    stats_away = calcular_stats_time_espn(jogos_away, away)

    media_h2h = calcular_h2h_espn(jogos_home, jogos_away, home, away)

    media_total = stats_home["media_marc"] + stats_away["media_marc"]
    gd_total = (stats_home["avg_gd"] + stats_away["avg_gd"])/2

    estimativa = max(0.2, min(5.0, media_total*0.7 + gd_total*0.3 + media_h2h*0.2))

    # Confiança baseada na quantidade de jogos
    jogos_disponiveis = stats_home["jogos_validos"] + stats_away["jogos_validos"]
    confianca = min(95, 30 + jogos_disponiveis*5)

    # Tendência
    if estimativa>=3.5: tendencia_line = "Mais 3.5"
    elif estimativa>=2.5: tendencia_line = "Mais 2.5"
    elif estimativa>=1.5: tendencia_line = "Mais 1.5"
    else: tendencia_line = "Menos 1.5"

    return {
        "estimativa": round(estimativa,2),
        "tendencia_line": tendencia_line,
        "stats_home": stats_home,
        "stats_away": stats_away,
        "media_h2h": round(media_h2h,2),
        "confianca": round(confianca,1)
    }

# =============================
# Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta Over/Under Refinado", layout="wide")
st.title("⚽ Sistema de Alertas - Over/Under (OpenLigaDB + ESPN)")
st.markdown("Jogos do dia da OpenLigaDB + cálculos históricos e H2H da ESPN")

# Configuração
temporada_atual = st.selectbox("📅 Temporada atual:", ["2023","2024","2025"], index=2)
data_selecionada = st.date_input("📅 Data dos jogos", datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

ligas_openliga = {
    "Premier League (Inglaterra)":"eng.1",
    "Bundesliga (Alemanha)":"ger.1",
    "La Liga (Espanha)":"esp.1",
}
liga_nome = st.selectbox("🏆 Escolha a Liga", list(ligas_openliga.keys()))
liga_id = ligas_openliga[liga_nome]

if st.button("🔍 Buscar jogos e calcular tendência"):
    st.info("Buscando jogos do dia na OpenLigaDB...")
    jogos_dia = obter_jogos_liga_temporada(liga_id, temporada_atual)
    jogos_dia = obter_jogos_por_data(jogos_dia, hoje)
    if not jogos_dia:
        st.warning("Nenhum jogo encontrado para esta data/temporada.")
    else:
        alertas = carregar_alertas()
        for j in jogos_dia:
            detalhe = calcular_estimativa_e_tendencia(j, liga_id)
            home = j["team1"]["teamName"]
            away = j["team2"]["teamName"]
            st.subheader(f"🏟️ {home} vs {away}")
            st.write(f"Estimativa total (gols): {detalhe['estimativa']:.2f} | Tendência: {detalhe['tendencia_line']} | Confiança: {detalhe['confianca']}%")
            st.write(f"- Média H2H: {detalhe['media_h2h']}")
            st.write(f"- Média gols Home: {detalhe['stats_home']['media_marc']:.2f} | Away: {detalhe['stats_away']['media_marc']:.2f}")
            # Alertas Telegram
            fixture_id = str(j.get("matchID"))
            precisa = fixture_id not in alertas or alertas[fixture_id].get("tendencia") != detalhe["tendencia_line"]
            if precisa:
                enviar_telegram(f"⚽ {home} vs {away} | Tendência: {detalhe['tendencia_line']} | Estimativa: {detalhe['estimativa']:.2f} | Confiança: {detalhe['confianca']}%")
                alertas[fixture_id] = {"tendencia":detalhe["tendencia_line"],"estimativa":detalhe["estimativa"]}
                salvar_alertas(alertas)
                alertas = carregar_alertas()
melhores_por_linha = {"1.5": [], "2.5": [], "3.5": []}

for match in jogos_dia:
    detalhe = calcular_estimativa_e_tendencia(match, liga_id)
    home = match["team1"]["teamName"]
    away = match["team2"]["teamName"]
    
    estimativa = detalhe["estimativa"]
    confianca = detalhe["confianca"]
    tendencia_line = detalhe["tendencia_line"]

    # Interface Streamlit
    st.subheader(f"🏟️ {home} vs {away}")
    st.write(f"Estimativa total (gols): {estimativa:.2f} | Tendência: {tendencia_line} | Confiança: {confianca}%")
    st.write(f"- Média H2H: {detalhe['media_h2h']}")
    st.write(f"- Média gols Home: {detalhe['stats_home']['media_marc']:.2f} | Away: {detalhe['stats_away']['media_marc']:.2f}")

    # Adicionar ao bucket de linhas
    for linha in ["1.5","2.5","3.5"]:
        if estimativa >= float(linha):
            melhores_por_linha[linha].append({
                "home":home,
                "away":away,
                "estimativa":estimativa,
                "confianca":confianca,
                "tendencia_line":tendencia_line
            })

    # Alertas persistentes por jogo
    fixture_id = str(match.get("matchID"))
    precisa = fixture_id not in alertas or alertas[fixture_id].get("tendencia") != tendencia_line
    if precisa:
        enviar_telegram(f"⚽ {home} vs {away} | Tendência: {tendencia_line} | Estimativa: {estimativa:.2f} | Confiança: {confianca}%")
        alertas[fixture_id] = {"tendencia":tendencia_line,"estimativa":estimativa}
        salvar_alertas(alertas)

# Top 3 consolidados por linha para canal alternativo
msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
sent_any = False
for linha in ["1.5","2.5","3.5"]:
    lista = sorted(melhores_por_linha[linha], key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
    if lista:
        sent_any = True
        msg_alt += f"🔥 Top {len(lista)} Jogos para +{linha} Gols\n"
        for j in lista:
            msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']}%\n"
        msg_alt += "\n"

if sent_any:
    enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
    st.success("🚀 Top jogos enviados para o canal alternativo 2!")
else:
    st.info("Nenhum jogo com tendência suficientemente forte para 1.5/2.5/3.5.")

