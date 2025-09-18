import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json
from collections import defaultdict

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
    status = "FT" if jogo.get("matchIsFinished") else "Not started/ongoing"
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
# Helpers OpenLigaDB
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
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}" if temporada else f"{OPENLIGA_BASE}/getmatchdata/{liga_id}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Erro obter_jogos_liga_temporada:", e)
    return []

def obter_jogos_por_data(jogos, data_iso):
    selecionados = []
    for j in jogos:
        dt = j.get("matchDateTime") or j.get("matchDateTimeUTC")
        if dt and dt.split("T")[0] == data_iso:
            selecionados.append(j)
    return selecionados

def obter_h2h(liga_id, home_name, away_name, max_jogos=6):
    try:
        t1 = slugify_team(home_name)
        t2 = slugify_team(away_name)
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{t1}/{t2}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            jogos = r.json()
            return sorted(jogos, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)[:max_jogos]
    except Exception as e:
        print("Erro obter_h2h:", e)
    return []

def extrair_jogos_time(all_matches, team_name, max_jogos=10):
    team_games = [j for j in all_matches if team_name.lower() in [j.get("team1",{}).get("teamName","").lower(), j.get("team2",{}).get("teamName","").lower()]]
    return sorted(team_games, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)[:max_jogos]

# =============================
# Helpers ESPN (histórico passado)
# =============================
def obter_historico_time_espn(team_id, league_id, max_jogos=10):
    """
    Busca resultados passados do time via API ESPN.
    Retorna lista de jogos no mesmo formato do OpenLigaDB.
    """
    try:
        url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            jogos_time = []
            for ev in data.get("events", []):
                comps = ev.get("competitions", [])
                if not comps: continue
                comp = comps[0]
                home = comp["competitors"][0]["team"]["displayName"]
                away = comp["competitors"][1]["team"]["displayName"]
                pts_home = int(comp["competitors"][0].get("score",0) or 0)
                pts_away = int(comp["competitors"][1].get("score",0) or 0)
                jogos_time.append({
                    "team1":{"teamName":home},
                    "team2":{"teamName":away},
                    "matchResults":[{"resultTypeID":2,"pointsTeam1":pts_home,"pointsTeam2":pts_away}],
                    "matchDateTime":comp.get("date")
                })
            # Filtrar apenas jogos do time_id
            jogos_time = [j for j in jogos_time if home.lower() == str(team_id).lower() or away.lower() == str(team_id).lower()]
            return sorted(jogos_time, key=lambda x:x.get("matchDateTime") or "", reverse=True)[:max_jogos]
    except Exception as e:
        print("Erro obter_historico_time_espn:", e)
    return []

# =============================
# Cálculo de estatísticas
# =============================
def calcular_stats_time_por_nome(jogos, team_name):
    gols_marc = gols_sof = jogos_validos = over15 = over25 = over35 = gd_total = 0
    for j in jogos:
        final = next((r for r in j.get("matchResults", []) if r.get("resultTypeID")==2), None)
        if not final: continue
        jogos_validos +=1
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1 = final.get("pointsTeam1",0)
        pts2 = final.get("pointsTeam2",0)
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
        return {"jogos_validos":0,"gols_marc":0,"gols_sof":0,"media_marc":0.0,"media_sof":0.0,"over15_pct":0.0,"over25_pct":0.0,"over35_pct":0.0,"avg_gd":0.0}
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

# =============================
# Tabela
# =============================
def construir_tabela_from_matches(matches):
    table = defaultdict(lambda: {"points":0,"gd":0,"gf":0,"ga":0,"played":0})
    for j in matches:
        final = next((r for r in j.get("matchResults",[]) if r.get("resultTypeID")==2), None)
        if not final: continue
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1 = final.get("pointsTeam1",0)
        pts2 = final.get("pointsTeam2",0)
        table[home]["played"] +=1
        table[away]["played"] +=1
        table[home]["gf"] += pts1
        table[home]["ga"] += pts2
        table[away]["gf"] += pts2
        table[away]["ga"] += pts1
        table[home]["gd"] += (pts1-pts2)
        table[away]["gd"] += (pts2-pts1)
        if pts1>pts2: table[home]["points"]+=3
        elif pts2>pts1: table[away]["points"]+=3
        else: table[home]["points"]+=1; table[away]["points"]+=1
    return table

# =============================
# Cálculo estimativa e tendência
# =============================
def calcular_estimativa_e_tendencia(match, all_matches_current, past_season_matches, peso_config=None):
    if peso_config is None:
        peso_config = {"h2h":0.3, "recent":0.4, "table":0.15, "gd":0.15}

    home = match["team1"]["teamName"]
    away = match["team2"]["teamName"]

    # --- H2H ---
    h2h_jogs = obter_h2h(match.get("league", {}).get("leagueName","") or match.get("group",""), home, away, max_jogos=6)
    total_gols_h2h = 0
    h2h_count = 0
    for j in h2h_jogs:
        for r in j.get("matchResults",[]):
            if r.get("resultTypeID") == 2:
                total_gols_h2h += r.get("pointsTeam1",0) + r.get("pointsTeam2",0)
                h2h_count += 1
    media_h2h = round(total_gols_h2h/h2h_count,2) if h2h_count else 0.0

    # --- Últimos N jogos recentes da temporada atual ---
    recent_n = 8
    recent_home = extrair_jogos_time(all_matches_current, home, max_jogos=recent_n)
    recent_away = extrair_jogos_time(all_matches_current, away, max_jogos=recent_n)
    stats_home = calcular_stats_time_por_nome(recent_home, home)
    stats_away = calcular_stats_time_por_nome(recent_away, away)

    media_recente_total = (stats_home["media_marc"] + stats_away["media_marc"])

    # --- Tabela baseada nos jogos históricos (passados) ---
    tabela = construir_tabela_from_matches(past_season_matches)

    def calcular_posicoes(tabela):
        if not tabela:
            return {}
        sorted_times = sorted(
            tabela.items(),
            key=lambda x: (x[1].get("points",0), x[1].get("gd",0), x[1].get("gf",0)),
            reverse=True
        )
        pos_dict = {}
        for i, (time, stats) in enumerate(sorted_times,1):
            pos_dict[time] = i
        return pos_dict

    posicoes = calcular_posicoes(tabela)
    pos_home = posicoes.get(home,None)
    pos_away = posicoes.get(away,None)
    pos_diff = (pos_away - pos_home) if (pos_home and pos_away) else 0

    # --- GD relativo ---
    avg_gd_abs = (stats_home.get("avg_gd",0) + stats_away.get("avg_gd",0))/2

    # --- Combinar fatores com pesos ---
    comp_h2h = media_h2h if media_h2h>0 else media_recente_total
    comp_recent = media_recente_total
    comp_table = max(-1.0, min(1.5, pos_diff/10))
    comp_gd = avg_gd_abs

    w_h2h = peso_config.get("h2h",0.3)
    w_recent = peso_config.get("recent",0.4)
    w_table = peso_config.get("table",0.15)
    w_gd = peso_config.get("gd",0.15)

    estimativa = (w_h2h*comp_h2h) + (w_recent*comp_recent) + (w_table*comp_table) + (w_gd*comp_gd)
    estimativa = max(0.2, min(5.0, estimativa))

    # --- Calcular confiança ---
    data_score = 0
    if h2h_count>=3: data_score += 25
    data_score += min(25,(stats_home["jogos_validos"]+stats_away["jogos_validos"])*2)
    coerencia = 100 - abs(comp_h2h - comp_recent)*20
    coerencia = max(0, min(100, coerencia))
    confianca = min(95, 40 + data_score + (coerencia/3))

    # --- Definir tendência ---
    if estimativa>=3.5:
        tendencia_line = "Mais 3.5"
    elif estimativa>=2.5:
        tendencia_line = "Mais 2.5"
    elif estimativa>=1.5:
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
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alerta Over/Under", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos - Over/Under")
st.markdown("Calcula tendência Over/Under (1.5 / 2.5 / 3.5) usando H2H + médias passadas + posição da tabela + saldo de gols.")

# Temporada e data
temporada_atual = st.selectbox("📅 Escolha a temporada atual (para jogos do dia):", ["2023","2024","2025"], index=2)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# Ligas
ligas_principais_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1",
}
liga_escolhida_nome = st.selectbox("🏆 Escolha a Liga:", list(ligas_principais_openliga.keys()))
liga_id = ligas_principais_openliga[liga_escolhida_nome]

#if st.button("🔍 Buscar
if st.button("🔍 Buscar jogos do dia e calcular tendência"):
    with st.spinner("Buscando jogos e calculando estatísticas..."):
        # Jogos do dia: temporada atual
        all_matches_current = obter_jogos_liga_temporada(liga_id, temporada_atual)
        matches_today = obter_jogos_por_data(all_matches_current, hoje)
        if not matches_today:
            st.info("Nenhum jogo encontrado para essa data/ligue/temporada.")
        else:
            st.subheader(f"📝 {len(matches_today)} jogos encontrados em {liga_escolhida_nome} para {hoje}")
            
            # Estatísticas históricas via ESPN para cada time
            past_season_matches = []
            for match in matches_today:
                home = match["team1"]["teamName"]
                away = match["team2"]["teamName"]
                
                # Obter últimos 10 jogos de cada time via ESPN
                jogos_home = obter_historico_time_espn(home, liga_id, max_jogos=10)
                jogos_away = obter_historico_time_espn(away, liga_id, max_jogos=10)
                past_season_matches += jogos_home + jogos_away

            melhores_por_linha = {"1.5": [], "2.5": [], "3.5": []}
            alertas = carregar_alertas()

            for match in matches_today:
                home = match["team1"]["teamName"]
                away = match["team2"]["teamName"]
                detalhe = calcular_estimativa_e_tendencia(match, all_matches_current, past_season_matches)

                estimativa = detalhe["estimativa"]
                confianca = detalhe["confianca"]
                tendencia_line = detalhe["tendencia_line"]

                st.subheader(f"🏟️ {home} vs {away}")
                st.write(f"📊 Estimativa total (gols): **{estimativa:.2f}** | Tendência: **{tendencia_line}** | Confiança: **{confianca:.0f}%**")
                st.write(f"- Média H2H: {detalhe['media_h2h']} (últimos {detalhe['h2h_count']})")
                st.write(f"- Média recente total: {detalhe['media_recente_total']:.2f}")
                st.write(f"- Posição tabela (histórico): Home={detalhe['pos_home']} | Away={detalhe['pos_away']}")
                st.write("---")

                # Adicionar ao bucket
                for linha in ["1.5","2.5","3.5"]:
                    if estimativa >= float(linha):
                        melhores_por_linha[linha].append({"home":home,"away":away,"estimativa":estimativa,"confianca":confianca,"tendencia_line":tendencia_line})

                # Alertas individuais persistentes
                fixture_id = str(match.get("matchID"))
                precisa = fixture_id not in alertas or alertas[fixture_id].get("tendencia") != tendencia_line
                if precisa:
                    enviar_alerta_telegram(match, tendencia_line, confianca, estimativa)
                    alertas[fixture_id] = {"tendencia":tendencia_line,"estimativa":estimativa,"confianca":confianca}
                    salvar_alertas(alertas)

            # Top 3 para canal alternativo
            msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
            sent_any = False
            for linha in ["1.5","2.5","3.5"]:
                lista = sorted(melhores_por_linha[linha], key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
                if lista:
                    sent_any = True
                    msg_alt += f"🔥 Top {len(lista)} Jogos para +{linha} Gols\n"
                    for j in lista:
                        msg_alt += f"🏟️ {j['home']} vs {j['away']} | Estimativa: {j['estimativa']:.2f} | Confiança: {j['confianca']:.0f}%\n"
                    msg_alt += "\n"
            if sent_any:
                enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
                st.success("🚀 Top jogos enviados para o canal alternativo 2!")
            else:
                st.info("Nenhum jogo com tendência suficientemente forte para 1.5/2.5/3.5.")
