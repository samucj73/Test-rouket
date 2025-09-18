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
    # jogo: objeto OpenLigaDB
    home = jogo["team1"]["teamName"]
    away = jogo["team2"]["teamName"]

    # data
    date_iso = jogo.get("matchDateTime") or jogo.get("matchDateTimeUTC") or jogo.get("matchDateTimeUTC")
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
    # Preparo do placar (quando disponível)
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
    """Normaliza nome do time para usar em endpoints H2H"""
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace(" ", "-")
    s = s.replace(".", "")
    s = s.replace("/", "-")
    s = s.replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return s

def obter_jogos_liga_temporada(liga_id: str, temporada: str = None):
    """Puxa todos os jogos de uma liga (ou temporada específica)"""
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
    """
    Puxa os jogos de uma liga e filtra por data (YYYY-MM-DD)
    Usamos obter_jogos_liga_temporada e filtramos.
    """
    jogos = obter_jogos_liga_temporada(liga_id)
    selecionados = []
    for j in jogos:
        dt = j.get("matchDateTime") or j.get("matchDateTimeUTC")
        if not dt:
            continue
        # extrair data YYYY-MM-DD
        try:
            date_only = dt.split("T")[0]
        except:
            continue
        if date_only == data_iso_date:
            selecionados.append(j)
    return selecionados

def obter_h2h(liga_id: str, home_name: str, away_name: str, max_jogos=6):
    """
    Usa endpoint H2H: /getmatchdata/{liga}/{team1}/{team2}
    Retorna lista de jogos recentes entre os dois.
    """
    try:
        t1 = slugify_team(home_name)
        t2 = slugify_team(away_name)
        url = f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{t1}/{t2}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            jogos = r.json()
            # já vem em ordem cronológica, vamos inverter para mais recentes primeiro
            jogos_sorted = sorted(jogos, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)
            return jogos_sorted[:max_jogos]
    except Exception as e:
        print("Erro obter_h2h:", e)
    return []

# =============================
# Estatísticas por time (a partir dos jogos da liga)
# =============================
def extrair_jogos_time(all_matches, team_name, max_jogos=10):
    """
    Filtra all_matches para os últimos jogos do team_name (considerando home/away).
    Retorna os mais recentes até max_jogos.
    """
    team_games = []
    for j in all_matches:
        home = j.get("team1", {}).get("teamName")
        away = j.get("team2", {}).get("teamName")
        if not home or not away:
            continue
        if team_name.lower() in (home.lower(), away.lower()):
            team_games.append(j)
    # ordenar por data desc
    team_games_sorted = sorted(team_games, key=lambda x: x.get("matchDateTime") or x.get("matchDateTimeUTC") or "", reverse=True)
    return team_games_sorted[:max_jogos]

def calcular_stats_time(jogos):
    """
    Jogs: lista de partidas (OpenLigaDB)
    Retorna dict com:
     - jogos_validos, gols_marcados_total, gols_sofridos_total
     - media_gols_marcados, media_gols_sofridos
     - over15_pct, over25_pct, over35_pct (nas partidas consideradas)
     - avg_goal_diff
    """
    gols_marc = 0
    gols_sof = 0
    jogos_validos = 0
    over15 = over25 = over35 = 0
    gd_total = 0

    for j in jogos:
        # procurar resultado final
        final = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = r
                break
        if not final:
            continue
        jogos_validos += 1
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1 = final.get("pointsTeam1", 0)
        pts2 = final.get("pointsTeam2", 0)
        # identificar se nosso time jogou em casa ou fora
        # assumiremos que the caller fez a filtragem por time específico e que ambos gols contam igualmente:
        gols_marc += pts1 if True else 0  # we'll adjust below
        # BUT safer: compute for each match relative to team: determine team goals vs opponent goals
        # We'll re-compute properly:
    # Recompute properly (so we need team name from context). To avoid complexity, we'll recalc with team context below.

    # Note: We'll instead return raw per-match totals and let caller compute with team name.
    return {
        "jogos": jogos
    }

# We'll implement a safer per-team stats function that requires the team_name
def calcular_stats_time_por_nome(jogos, team_name):
    gols_marc = 0
    gols_sof = 0
    jogos_validos = 0
    over15 = over25 = over35 = 0
    gd_total = 0

    for j in jogos:
        final = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = r
                break
        if not final:
            continue
        jogos_validos += 1
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1 = final.get("pointsTeam1", 0)
        pts2 = final.get("pointsTeam2", 0)

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
            # não é partida do time
            continue

        if total_gols >= 2:
            over15 += 1
        if total_gols >= 3:
            over25 += 1
        if total_gols >= 4:
            over35 += 1

    if jogos_validos == 0:
        return {
            "jogos_validos": 0,
            "gols_marc": 0,
            "gols_sof": 0,
            "media_marc": 0.0,
            "media_sof": 0.0,
            "over15_pct": 0.0,
            "over25_pct": 0.0,
            "over35_pct": 0.0,
            "avg_gd": 0.0
        }

    media_marc = gols_marc / jogos_validos
    media_sof = gols_sof / jogos_validos
    return {
        "jogos_validos": jogos_validos,
        "gols_marc": gols_marc,
        "gols_sof": gols_sof,
        "media_marc": round(media_marc, 2),
        "media_sof": round(media_sof, 2),
        "over15_pct": round(100 * over15 / jogos_validos, 1),
        "over25_pct": round(100 * over25 / jogos_validos, 1),
        "over35_pct": round(100 * over35 / jogos_validos, 1),
        "avg_gd": round(gd_total / jogos_validos, 2)
    }

# =============================
# Montar tabela (posição) a partir dos jogos da liga/temporada
# =============================
def construir_tabela_from_matches(matches):
    """
    Recebe lista de matches da liga/temporada e retorna um dicionário com:
    {team_name: {"points":..., "gd":..., "gf":..., "ga":..., "played":..., "position":...}}
    """
    table = defaultdict(lambda: {"points":0, "gd":0, "gf":0, "ga":0, "played":0})
    for j in matches:
        final = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                final = r
                break
        if not final:
            continue
        home = j["team1"]["teamName"]
        away = j["team2"]["teamName"]
        pts1 = final.get("pointsTeam1", 0)
        pts2 = final.get("pointsTeam2", 0)

        # atualiza jogos
        table[home]["played"] += 1
        table[away]["played"] += 1
        table[home]["gf"] += pts1
        table[home]["ga"] += pts2
        table[away]["gf"] += pts2
        table[away]["ga"] += pts1
        table[home]["gd"] += (pts1 - pts2)
        table[away]["gd"] += (pts2 - pts1)

        # pontos
        if pts1 > pts2:
            table[home]["points"] += 3
        elif pts2 > pts1:
            table[away]["points"] += 3
        else:
            table[home]["points"] += 1
            table[away]["points"] += 1

    # transformar em lista ordenada e atribuir posições
    ranking = sorted(table.items(), key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]), reverse=True)
    resultado = {}
    pos = 1
    for team, stats in ranking:
        stats["position"] = pos
        resultado[team] = stats
        pos += 1
    return resultado

# =============================
# Função principal de cálculo de estimativa (combina várias features)
# =============================
def calcular_estimativa_e_tendencia(match, all_league_matches, season_matches, peso_config=None):
    """
    match: objeto OpenLigaDB do jogo em análise
    all_league_matches: todos os jogos da liga (para calcular recentes e tabela)
    season_matches: jogos da temporada para montar tabela (pode ser igual a all_league_matches)
    Retorna: estimativa_total_gols, confianca_percent, tendencia_string (por ex "Mais 2.5")
    """

    # parâmetros de peso (podem ser ajustados)
    if peso_config is None:
        peso_config = {
            "h2h": 0.30,
            "recent": 0.40,   # média dos dois times
            "table": 0.15,
            "gd": 0.15
        }

    home = match["team1"]["teamName"]
    away = match["team2"]["teamName"]
    # pegar H2H
    h2h_jogs = obter_h2h(match.get("league", {}).get("leagueName", "") or match.get("group", ""), home, away, max_jogos=6)
    # Nota: o endpoint H2H aceita liga ID; mas se não funcionar, ainda teremos dados recentes dos times.

    # média de gols H2H
    total_gols_h2h = 0
    h2h_count = 0
    for j in h2h_jogs:
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                total_gols_h2h += r.get("pointsTeam1", 0) + r.get("pointsTeam2", 0)
                h2h_count += 1
    media_h2h = round(total_gols_h2h / h2h_count, 2) if h2h_count else 0.0

    # últimas N partidas de cada time na liga
    recent_n = 8
    recent_home = extrair_jogos_time(all_league_matches, home, max_jogos=recent_n)
    recent_away = extrair_jogos_time(all_league_matches, away, max_jogos=recent_n)

    stats_home = calcular_stats_time_por_nome(recent_home, home)
    stats_away = calcular_stats_time_por_nome(recent_away, away)

    # média conjunta recente = média dos gols marcados por ambos (nas suas últimas N)
    media_recente = (stats_home["media_marc"] + stats_away["media_marc"] + stats_home["media_sof"] + stats_away["media_sof"]) / 4
    # alternativa: média direta dos totais por jogo:
    media_recente_total = (stats_home["media_marc"] + stats_away["media_marc"])

    # tabela da temporada (positions)
    tabela = construir_tabela_from_matches(season_matches)
    pos_home = tabela.get(home, {}).get("position", None)
    pos_away = tabela.get(away, {}).get("position", None)

    # diferença de posição (quanto menor -> home é melhor na tabela)
    pos_diff = None
    if pos_home and pos_away:
        pos_diff = pos_away - pos_home  # positivo se home está acima (melhor) que away

    # GD relativo (média dos avg_gd)
    avg_gd = (stats_home.get("avg_gd", 0) + (-stats_away.get("avg_gd", 0))) / 2  # home gd vs away gd inverted
    # but simpler: use absolute averages:
    avg_gd_abs = (stats_home.get("avg_gd", 0) + stats_away.get("avg_gd", 0)) / 2

    # cálculo ponderado da estimativa total de gols
    # componentes:
    comp_h2h = media_h2h
    comp_recent = media_recente_total
    comp_table = 0
    if pos_diff is not None:
        # se dois times com posições altas (baixa numérica) normalmente têm menos gols? Não necessariamente.
        # Aqui usamos pos_diff para ajustar: se times estão próximos (abs small) => ligeira redução de gols esperados (mais equilíbrio)
        # se estão muito distantes => pode aumentar a chance de mais gols? para simplificar:
        comp_table = max(-1.0, min(1.5, (pos_diff / 10)))  # escala pequena
    comp_gd = avg_gd_abs

    # Normalizar e combinar:
    # Três fatores principais que representam "média esperada": h2h, recent, gd-influence
    base = 0.0
    w_h2h = peso_config.get("h2h", 0.3)
    w_recent = peso_config.get("recent", 0.4)
    w_table = peso_config.get("table", 0.15)
    w_gd = peso_config.get("gd", 0.15)

    # Some heuristics to avoid zeros dominating:
    if comp_h2h <= 0:
        comp_h2h = comp_recent  # fallback
    estimativa = (w_h2h * comp_h2h) + (w_recent * comp_recent) + (w_table * comp_table) + (w_gd * comp_gd)

    # small floor/ceiling
    estimativa = max(0.2, min(5.0, estimativa))

    # Calcular confiança baseada em:
    # - quantidade de dados disponíveis (mais jogos recentes e H2H -> mais confiança)
    # - coerência entre fontes (h2h vs recente próximo -> maior confiança)
    data_score = 0
    if h2h_count >= 3:
        data_score += 25
    data_score += min(25, (stats_home["jogos_validos"] + stats_away["jogos_validos"]) * 2)  # até 25
    # coerência
    coerencia = 100 - abs( (comp_h2h if comp_h2h else comp_recent) - comp_recent )*20
    coerencia = max(0, min(100, coerencia))
    confianca = min(95, 40 + data_score + (coerencia/3))  # escala para até ~95

    # Definir tendência para linhas
    tendencia = []
    if estimativa >= 3.5:
        tendencia_line = "Mais 3.5"
    elif estimativa >= 2.5:
        tendencia_line = "Mais 2.5"
    elif estimativa >= 1.5:
        tendencia_line = "Mais 1.5"
    else:
        tendencia_line = "Menos 1.5"

    # devolve detalhes também para debug / UI
    detalhe = {
        "estimativa": round(estimativa, 2),
        "confianca": round(confianca, 1),
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
# Streamlit interface (adaptada)
# =============================
st.set_page_config(page_title="⚽ Alerta Over/Under (OpenLigaDB)", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos - Over/Under (OpenLigaDB)")
st.markdown("Calcula tendência Over/Under (1.5 / 2.5 / 3.5) usando H2H + médias recentes + posição da tabela + saldo de gols.")

temporada = st.selectbox("📅 Escolha a temporada:", ["2022", "2023", "2024", "2025"], index=2)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

# Mapeamento de ligas (IDs da OpenLigaDB)
ligas_principais_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1",
    # Você pode adicionar outras conforme a disponibilidade da OpenLigaDB
}

liga_escolhida_nome = st.selectbox("🏆 Escolha a Liga:", list(ligas_principais_openliga.keys()))
liga_id = ligas_principais_openliga[liga_escolhida_nome]

if st.button("🔍 Buscar jogos do dia e calcular tendência"):
    with st.spinner("Buscando jogos e calculando estatísticas..."):
        # puxar todos os jogos da liga (para stats e tabela)
        all_matches = obter_jogos_liga_temporada(liga_id, temporada)
        # filtrar jogos da data selecionada
        matches_today = []
        for j in all_matches:
            dt = j.get("matchDateTime") or j.get("matchDateTimeUTC")
            if not dt:
                continue
            date_only = dt.split("T")[0]
            if date_only == hoje:
                matches_today.append(j)

        if not matches_today:
            st.info("Nenhum jogo encontrado para essa data/ligue/temporada.")
        else:
            st.subheader(f"📝 {len(matches_today)} jogos encontrados em {liga_escolhida_nome} para {hoje}")
            melhores_por_linha = {"1.5": [], "2.5": [], "3.5": []}

            # Para construir tabela da temporada usamos todos os matches da temporada (all_matches)
            season_matches = all_matches

            # Iterar jogos do dia
            for match in matches_today:
                home = match["team1"]["teamName"]
                away = match["team2"]["teamName"]
                # Calcular estimativa detalhada
                detalhe = calcular_estimativa_e_tendencia(match, all_matches, season_matches)

                estimativa = detalhe["estimativa"]
                confianca = detalhe["confianca"]
                tendencia_line = detalhe["tendencia_line"]

                # Mostrar bloco informativo no Streamlit
                with st.container():
                    st.subheader(f"🏟️ {home} vs {away}")
                    st.caption(f"Liga: {liga_escolhida_nome} | Temporada: {temporada}")
                    st.write(f"📊 Estimativa total (gols): **{estimativa:.2f}**")
                    st.write(f"🔥 Tendência linha: **{tendencia_line}** | Confiança: **{confianca:.0f}%**")
                    st.write("📈 Detalhes:")
                    st.write(f"- Média H2H: {detalhe['media_h2h']} (últimos {detalhe['h2h_count']})")
                    st.write(f"- Média recente total (soma médias times): {detalhe['media_recente_total']:.2f}")
                    st.write(f"- Home stats (últimos jogos): {detalhe['stats_home']}")
                    st.write(f"- Away stats (últimos jogos): {detalhe['stats_away']}")
                    st.write(f"- Posição tabela: Home={detalhe['pos_home']} | Away={detalhe['pos_away']}")
                    st.write("---")

                # Montar representação compacta para top lists
                item = {
                    "home": home,
                    "away": away,
                    "estimativa": estimativa,
                    "confianca": confianca,
                    "tendencia_line": tendencia_line,
                    "detalhe": detalhe
                }

                # adicionar nos buckets apropriados (1.5, 2.5, 3.5)
                if estimativa >= 3.5:
                    melhores_por_linha["3.5"].append(item)
                if estimativa >= 2.5:
                    melhores_por_linha["2.5"].append(item)
                if estimativa >= 1.5:
                    melhores_por_linha["1.5"].append(item)

                # verificar e enviar alerta individual (persistente)
                # usaremos match['matchID'] como fixture id
                fixture_wrapper = {"matchID": match.get("matchID", ""), "match": match}
                # note: ajustar o envio para usar estrutura esperada na função de verificação original
                # vou adaptar: armazenar por matchID no arquivo de alertas
                alertas = carregar_alertas()
                fixture_id = str(match.get("matchID"))
                precisa = False
                if fixture_id not in alertas:
                    precisa = True
                else:
                    ultimo = alertas[fixture_id]
                    if ultimo.get("tendencia") != tendencia_line:
                        precisa = True
                if precisa:
                    enviar_alerta_telegram(match, tendencia_line, confianca, estimativa)
                    alertas[fixture_id] = {
                        "tendencia": tendencia_line,
                        "estimativa": estimativa,
                        "confianca": confianca
                    }
                    salvar_alertas(alertas)

            # Ordenar e pegar top 3 por confiança/estimativa para cada linha e enviar consolidado
            msg_alt = "📢 TOP ENTRADAS - Alertas Consolidados\n\n"
            sent_any = False
            for linha in ["1.5", "2.5", "3.5"]:
                lista = sorted(melhores_por_linha[linha], key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
                if not lista:
                    continue
                sent_any = True
                msg_alt += f"🔥 Top {len(lista)} Jogos para +{linha} Gols\n"
                for j in lista:
                    msg_alt += (
                        f"🏟️ {j['home']} vs {j['away']}\n"
                        f"📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n\n"
                    )
                msg_alt += "\n"

            if sent_any:
                enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
                st.success("🚀 Top jogos enviados para o canal alternativo 2!")
            else:
                st.info("Nenhum jogo com tendência suficientemente forte para as linhas 1.5/2.5/3.5.")
