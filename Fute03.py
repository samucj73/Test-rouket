import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json
from collections import defaultdict, Counter

# =============================
# Configurações (Telegram + persistência)
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo 2
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
OPENLIGA_BASE = "https://api.openligadb.de"

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

def enviar_alerta_telegram(jogo, tendencia_text, confianca, estimativa, chat_id=TELEGRAM_CHAT_ID):
    home = jogo["team1"]["teamName"]
    away = jogo["team2"]["teamName"]

    date_iso = jogo.get("matchDateTime") or jogo.get("matchDateTimeUTC")
    if date_iso:
        try:
            data_jogo = datetime.fromisoformat(date_iso.replace("Z", "+00:00")) - timedelta(hours=3)
            data_formatada = data_jogo.strftime("%d/%m/%Y")
            hora_formatada = data_jogo.strftime("%H:%M")
        except:
            data_formatada = date_iso
            hora_formatada = ""
    else:
        data_formatada = "Desconhecida"
        hora_formatada = ""

    status = "Desconhecido"
    if "matchIsFinished" in jogo:
        status = "FT" if jogo["matchIsFinished"] else "Not started/ongoing"
    placar = ""
    if jogo.get("matchIsFinished"):
        for r in jogo.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                break

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia_text}\n"
        f"Estimativa total (gols): {estimativa:.2f}\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar (se final): {placar}"
    )
    enviar_telegram(msg, chat_id)

# =============================
# Utilitários para OpenLigaDB
# =============================
def slugify_team(name: str):
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace(" ", "-").replace(".", "").replace("/", "-")
    s = s.replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return s

def obter_jogos_liga_temporada(liga_id: str, temporada: str = None):
    try:
        if temporada:
            url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}"
        else:
            url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Erro obter_jogos_liga_temporada:", e)
    return []

def obter_jogos_por_data(liga_id: str, data_iso_date: str):
    jogos = obter_jogos_liga_temporada(liga_id)
    selecionados = []
    for j in jogos:
        dt = j.get("matchDateTime") or j.get("matchDateTimeUTC")
        if not dt:
            continue
        date_only = dt.split("T")[0]
        if date_only == data_iso_date:
            selecionados.append(j)
    return selecionados

def obter_h2h(liga_id: str, home_name: str, away_name: str, max_jogos=6):
    try:
        t1 = slugify_team(home_name)
        t2 = slugify_team(away_name)
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{t1}/{t2}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            jogos = r.json()
            jogos_sorted = sorted(jogos, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)
            return jogos_sorted[:max_jogos]
    except Exception as e:
        print("Erro obter_h2h:", e)
    return []

# =============================
# Estatísticas por time
# =============================
def extrair_jogos_time(all_matches, team_name, max_jogos=10):
    team_games = []
    for j in all_matches:
        home = j.get("team1", {}).get("teamName")
        away = j.get("team2", {}).get("teamName")
        if not home or not away:
            continue
        if team_name.lower() in (home.lower(), away.lower()):
            team_games.append(j)
    team_games_sorted = sorted(team_games, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)
    return team_games_sorted[:max_jogos]

def calcular_stats_time_por_nome(jogos, team_name):
    gols_marc = gols_sof = jogos_validos = over15 = over25 = over35 = gd_total = 0
    for j in jogos:
        final = next((r for r in j.get("matchResults", []) if r.get("resultTypeID") == 2), None)
        if not final:
            continue
        jogos_validos += 1
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1, pts2 = final.get("pointsTeam1",0), final.get("pointsTeam2",0)

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

        if total_gols >= 2: over15 +=1
        if total_gols >= 3: over25 +=1
        if total_gols >= 4: over35 +=1

    if jogos_validos == 0:
        return {"jogos_validos":0,"gols_marc":0,"gols_sof":0,"media_marc":0.0,"media_sof":0.0,
                "over15_pct":0.0,"over25_pct":0.0,"over35_pct":0.0,"avg_gd":0.0}

    return {
        "jogos_validos": jogos_validos,
        "gols_marc": gols_marc,
        "gols_sof": gols_sof,
        "media_marc": round(gols_marc/jogos_validos,2),
        "media_sof": round(gols_sof/jogos_validos,2),
        "over15_pct": round(100*over15/jogos_validos,1),
        "over25_pct": round(100*over25/jogos_validos,1),
        "over35_pct": round(100*over35/jogos_validos,1),
        "avg_gd": round(gd_total/jogos_validos,2)
    }

# =============================
# Montar tabela (posição) da liga
# =============================
def construir_tabela_from_matches(matches):
    table = defaultdict(lambda: {"points":0,"gd":0,"gf":0,"ga":0,"played":0})
    for j in matches:
        final = next((r for r in j.get("matchResults",[]) if r.get("resultTypeID")==2), None)
        if not final: continue
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1, pts2 = final.get("pointsTeam1",0), final.get("pointsTeam2",0)
        table[home]["played"] += 1
        table[away]["played"] += 1
        table[home]["gf"] += pts1
        table[home]["ga"] += pts2
        table[away]["gf"] += pts2
        table[away]["ga"] += pts1
        table[home]["gd"] += pts1-pts2
        table[away]["gd"] += pts2-pts1
        if pts1>pts2: table[home]["points"]+=3
        elif pts2>pts1: table[away]["points"]+=3
        else: table[home]["points"]+=1; table[away]["points"]+=1
    ranking = sorted(table.items(), key=lambda x: (x[1]["points"],x[1]["gd"],x[1]["gf"]), reverse=True)
    resultado,pos = {},1
    for team,stats in ranking:
        stats["position"] = pos
        resultado[team]=stats
        pos+=1
    return resultado

# =============================
# Cálculo estimativa e tendência
# =============================
def calcular_estimativa_e_tendencia(match, all_league_matches, season_matches, peso_config=None):
    if peso_config is None:
        peso_config = {"h2h":0.3,"recent":0.4,"table":0.15,"gd":0.15}

    home, away = match["team1"]["teamName"], match["team2"]["teamName"]
    h2h_jogs = obter_h2h(match.get("league", {}).get("leagueName","") or match.get("group",""), home, away, 6)
    total_gols_h2h,h2h_count = 0,0
    for j in h2h_jogs:
        for r in j.get("matchResults", []):
            if r.get("resultTypeID")==2:
                total_gols_h2h += r.get("pointsTeam1",0)+r.get("pointsTeam2",0)
                h2h_count+=1
    media_h2h = round(total_gols_h2h/h2h_count,2) if h2h_count else 0.0

    recent_n=8
    recent_home = extrair_jogos_time(all_league_matches, home, recent_n)
    recent_away = extrair_jogos_time(all_league_matches, away, recent_n)
    stats_home = calcular_stats_time_por_nome(recent_home, home)
    stats_away = calcular_stats_time_por_nome(recent_away, away)
    media_recente_total = stats_home["media_marc"]+stats_away["media_marc"]

    tabela = construir_tabela_from_matches(season_matches)
    pos_home, pos_away = tabela.get(home,{}).get("position"), tabela.get(away,{}).get("position")
    pos_diff = (pos_away - pos_home) if (pos_home and pos_away) else 0
    avg_gd_abs = (stats_home.get("avg_gd",0)+stats_away.get("avg_gd",0))/2

    comp_h2h, comp_recent, comp_table, comp_gd = media_h2h if media_h2h>0 else media_recente_total, media_recente_total, max(-1.0,min(1.5,pos_diff/10)), avg_gd_abs
    w_h2h, w_recent, w_table, w_gd = peso_config["h2h"], peso_config["recent"], peso_config["table"], peso_config["gd"]
    estimativa = (w_h2h*comp_h2h)+(w_recent*comp_recent)+(w_table*comp_table)+(w_gd*comp_gd)
    estimativa = max(0.2,min(5.0,estimativa))

    data_score = (25 if h2h_count>=3 else 0)
    data_score += min(25, (stats_home["jogos_validos"] + stats_away["jogos_validos"]) * 2)
    coerencia = max(0, min(100, 100 - abs(comp_h2h - comp_recent)*20))
    confianca = min(95, 40 + data_score + (coerencia/3))

    if estimativa >= 3.5:
        tendencia_line = "Mais 3.5"
    elif estimativa >= 2.5:
        tendencia_line = "Mais 2.5"
    elif estimativa >= 1.5:
        tendencia_line = "Mais 1.5"
    else:
        tendencia_line = "Menos 1.5"

    detalhe = {
        "estimativa": round(estimativa,2),
        "confianca": round(confianca,1),
        "tendencia_line": tendencia_line,
        "media_h2h": round(media_h2h,2),
        "h2h_count": h2h_count,
        "media_recente_total": round(media_recente_total,2),
        "stats_home": stats_home,
        "stats_away": stats_away,
        "pos_home": pos_home,
        "pos_away": pos_away
    }

    return detalhe

# =============================
# Streamlit interface
# =============================
st.set_page_config(page_title="⚽ Alerta Over/Under (OpenLigaDB)", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos - Over/Under (OpenLigaDB)")
st.markdown("Calcula tendência Over/Under (1.5 / 2.5 / 3.5) usando H2H + médias recentes + posição da tabela + saldo de gols.")

temporada = st.selectbox("📅 Escolha a temporada:", ["2022","2023","2024","2025"], index=2)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# Mapeamento ligas
ligas_principais_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1",
}

# Seleção múltipla de ligas
ligas_escolhidas = st.multiselect("🏆 Escolha uma ou mais ligas:", list(ligas_principais_openliga.keys()), default=list(ligas_principais_openliga.keys())[:1])

if st.button("🔍 Buscar jogos do dia e calcular tendência"):
    if not ligas_escolhidas:
        st.warning("Selecione pelo menos uma liga!")
    else:
        with st.spinner("Buscando jogos e calculando estatísticas..."):
            all_matches_total = []
            matches_today_total = []

            # Puxar jogos de todas ligas selecionadas
            for liga_nome in ligas_escolhidas:
                liga_id = ligas_principais_openliga[liga_nome]
                all_matches = obter_jogos_liga_temporada(liga_id, temporada)
                all_matches_total.extend(all_matches)
                matches_today = [j for j in all_matches if (j.get("matchDateTime") or j.get("matchDateTimeUTC","")).split("T")[0]==hoje]
                matches_today_total.extend(matches_today)

            if not matches_today_total:
                st.info("Nenhum jogo encontrado para as ligas selecionadas nesta data.")
            else:
                st.subheader(f"📝 {len(matches_today_total)} jogos encontrados para {hoje}")
                melhores_por_linha = {"1.5": [], "2.5": [], "3.5": []}
                season_matches = all_matches_total

                alertas = carregar_alertas()

                for match in matches_today_total:
                    home, away = match["team1"]["teamName"], match["team2"]["teamName"]
                    detalhe = calcular_estimativa_e_tendencia(match, all_matches_total, season_matches)
                    estimativa = detalhe["estimativa"]
                    confianca = detalhe["confianca"]
                    tendencia_line = detalhe["tendencia_line"]

                    with st.container():
                        st.subheader(f"🏟️ {home} vs {away}")
                        st.caption(f"Liga(s) selecionada(s) | Temporada: {temporada}")
                        st.write(f"📊 Estimativa total (gols): **{estimativa:.2f}**")
                        st.write(f"🔥 Tendência linha: **{tendencia_line}** | Confiança: **{confianca:.0f}%**")
                        st.write("📈 Detalhes:")
                        st.write(f"- Média H2H: {detalhe['media_h2h']} (últimos {detalhe['h2h_count']})")
                        st.write(f"- Média recente total: {detalhe['media_recente_total']:.2f}")
                        st.write(f"- Home stats: {detalhe['stats_home']}")
                        st.write(f"- Away stats: {detalhe['stats_away']}")
                        st.write(f"- Posição tabela: Home={detalhe['pos_home']} | Away={detalhe['pos_away']}")
                        st.write("---")

                    item = {"home": home,"away": away,"estimativa": estimativa,"confianca": confianca,"tendencia_line": tendencia_line,"detalhe": detalhe}
                    if estimativa >= 3.5: melhores_por_linha["3.5"].append(item)
                    if estimativa >= 2.5: melhores_por_linha["2.5"].append(item)
                    if estimativa >= 1.5: melhores_por_linha["1.5"].append(item)

                    fixture_id = str(match.get("matchID"))
                    precisa = fixture_id not in alertas or alertas[fixture_id].get("tendencia") != tendencia_line
                    if precisa:
                        enviar_alerta_telegram(match, tendencia_line, confianca, estimativa)
                        alertas[fixture_id] = {"tendencia": tendencia_line,"estimativa": estimativa,"confianca": confianca}
                        salvar_alertas(alertas)

                # Top alertas consolidados
                msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
                sent_any = False
                for linha in ["1.5","2.5","3.5"]:
                    lista = sorted(melhores_por_linha[linha], key=lambda x:(x["confianca"],x["estimativa"]), reverse=True)[:3]
                    if not lista: continue
                    sent_any=True
                    msg_alt += f"🔥 Top {len(lista)} Jogos para +{linha} Gols\n"
                    for j in lista:
                        msg_alt += f"🏟️ {j['home']} vs {j['away']}\n📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n\n"
                    msg_alt += "\n"

                if sent_any:
                    enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
                    st.success("🚀 Top jogos enviados para o canal alternativo 2!")
                else:
                    st.info("Nenhum jogo com tendência suficientemente forte para as linhas 1.5/2.5/3.5.")
