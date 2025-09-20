# app_alertas_gols_top3.py
import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json

# =============================
# Configurações (substitua se quiser)
# =============================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

OPENLIGA_BASE = "https://api.openligadb.de"
ligas_openliga = {
    "Bundesliga (Alemanha)": "bl1",
    "2. Bundesliga (Alemanha)": "bl2",
    "DFB-Pokal (Alemanha)": "dfb",
    "Premier League (Inglaterra)": "eng1",
    "La Liga (Espanha)": "esp1",
    "Serie A (Itália)": "ita1",
    "Ligue 1 (França)": "fra1",
    "Brasileirão Série A": "bra1",
    "Brasileirão Série B": "bra2"
}

# Telegram
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal (se quiser)
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo (onde enviaremos o consolidado)
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Arquivo de persistência de alertas
ALERTAS_PATH = "alertas.json"

# =============================
# Streamlit config
# =============================
st.set_page_config(page_title="⚽ Alertas de Gols + Top 3", layout="wide")
st.title("⚽ Sistema de Alertas de Gols + Top 3 (Over & BTTS)")

# =============================
# Persistência: carregar / salvar alertas
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        try:
            with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_alertas(alertas):
    try:
        with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
            json.dump(alertas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Erro ao salvar alertas: {e}")

# =============================
# Envio Telegram
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID_ALT2):
    try:
        requests.post(BASE_URL_TG, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        st.warning(f"Erro ao enviar mensagem para Telegram: {e}")

# =============================
# Função para verificar e enviar alertas (persistente, evita duplicados)
# =============================
def verificar_enviar_alerta(match_fixture, mensagem_resumida, confianca, estimativa):
    """
    match_fixture: o objeto 'match' tal como retornado pela API-Football
    mensagem_resumida: texto curto indicando tendência(s)
    confianca: int
    estimativa: float
    """
    alertas = carregar_alertas()
    fixture_id = str(match_fixture.get("fixture", {}).get("id") or match_fixture.get("fixture_id") or "unknown")
    chave = f"{fixture_id}::{mensagem_resumida}"

    # se não existe, envia e registra
    if chave not in alertas:
        # preparar campos do match para mensagem
        home = match_fixture.get("teams", {}).get("home", {}).get("name", "")
        away = match_fixture.get("teams", {}).get("away", {}).get("name", "")
        data_iso = match_fixture.get("fixture", {}).get("date", "")
        try:
            data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
            data_formatada = data_jogo.strftime("%d/%m/%Y")
            hora_formatada = data_jogo.strftime("%H:%M")
        except Exception:
            data_formatada = data_iso or "Desconhecida"
            hora_formatada = ""

        msg = (
            f"⚽ *Alerta de Jogo*\n"
            f"🏟️ {home} vs {away}\n"
            f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
            f"{mensagem_resumida}\n"
            f"📊 Confiança: {confianca}% | Estimativa: {estimativa:.2f}\n"
        )

        enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

        # salvar registro para evitar duplicados
        alertas[chave] = {
            "fixture_id": fixture_id,
            "home": home,
            "away": away,
            "mensagem": mensagem_resumida,
            "confianca": confianca,
            "estimativa": estimativa,
            "enviado_em": datetime.utcnow().isoformat()
        }
        salvar_alertas(alertas)

# =============================
# Funções de cálculo de tendência
# =============================
def calcular_tendencia_confianca_realista(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    """
    Retorna: (estimativa_final: float, confianca: int, tendencia: str)
    mesma lógica que você usava, com fallback seguro.
    """
    media_casa_marcados = media_casa.get("media_gols_marcados", 1.5)
    media_casa_sofridos = media_casa.get("media_gols_sofridos", 1.2)
    media_fora_marcados = media_fora.get("media_gols_marcados", 1.4)
    media_fora_sofridos = media_fora.get("media_gols_sofridos", 1.1)
    
    media_time_casa = media_casa_marcados + media_fora_sofridos
    media_time_fora = media_fora_marcados + media_casa_sofridos
    estimativa_base = (media_time_casa + media_time_fora) / 2

    h2h_media = media_h2h.get("media_gols", 2.5) if media_h2h.get("total_jogos",0) > 0 else 2.5
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * h2h_media

    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5) * 15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5) * 20)
    else:
        tendencia = "Menos 1.5"
        confianca = max(50, min(75, 55 + (1.5 - estimativa_final) * 20))

    return round(estimativa_final, 2), int(round(confianca)), tendencia

# =============================
# H2H use (mantive a sua)
# =============================
def media_gols_confrontos_diretos(home_id, away_id, temporada=None, max_jogos=5):
    try:
        url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"media_gols": 0, "total_jogos": 0}
        jogos = response.json().get("response", [])
        if temporada:
            jogos = [j for j in jogos if j.get("league", {}).get("season") == temporada]
        jogos = sorted(jogos, key=lambda x: x.get("fixture", {}).get("date", ""), reverse=True)[:max_jogos]
        if not jogos:
            return {"media_gols": 0, "total_jogos": 0}

        total_pontos, total_peso = 0, 0
        for idx, j in enumerate(jogos):
            try:
                if j.get("fixture", {}).get("status", {}).get("short") != "FT":
                    continue
                home_goals = j.get("score", {}).get("fulltime", {}).get("home") or 0
                away_goals = j.get("score", {}).get("fulltime", {}).get("away") or 0
                gols = home_goals + away_goals
            except Exception:
                gols = 0
            peso = max_jogos - idx
            total_pontos += gols * peso
            total_peso += peso

        media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
        return {"media_gols": media_ponderada, "total_jogos": len(jogos)}
    except Exception:
        return {"media_gols": 0, "total_jogos": 0}

# =============================
# OpenLigaDB: médias por time
# =============================
def obter_jogos_liga_temporada(liga_id, temporada):
    try:
        r = requests.get(f"{OPENLIGA_BASE}/getmatchdata/{liga_id}/{temporada}", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.warning(f"Erro ao obter jogos OpenLigaDB: {e}")
    return []

def calcular_media_gols_times(jogos_hist):
    stats = {}
    for j in jogos_hist:
        home = j.get("team1", {}).get("teamName") or j.get("Team1", {}).get("TeamName")
        away = j.get("team2", {}).get("teamName") or j.get("Team2", {}).get("TeamName")
        if not home or not away:
            continue
        placar = None
        for r in j.get("matchResults", []):
            if r.get("resultTypeID") == 2:
                placar = (r.get("pointsTeam1", 0), r.get("pointsTeam2", 0))
                break
        if not placar:
            continue
        stats.setdefault(home, {"marcados": [], "sofridos": []})
        stats.setdefault(away, {"marcados": [], "sofridos": []})
        stats[home]["marcados"].append(placar[0])
        stats[home]["sofridos"].append(placar[1])
        stats[away]["marcados"].append(placar[1])
        stats[away]["sofridos"].append(placar[0])

    medias = {}
    for time, gols in stats.items():
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 1.5
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 1.2
        medias[time] = {"media_gols_marcados": round(media_marcados,2), "media_gols_sofridos": round(media_sofridos,2)}
    return medias

# =============================
# Obter odds (API-Football) - Over1.5, Over2.5 e BTTS (yes)
# =============================
def obter_odds(fixture_id):
    try:
        url = f"{BASE_URL}/odds?fixture={fixture_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"1.5": None, "2.5": None, "btts": None}
        response_json = resp.json().get("response", [])
        if not response_json:
            return {"1.5": None, "2.5": None, "btts": None}
        bookmakers = response_json[0].get("bookmakers", [])
        if not bookmakers:
            return {"1.5": None, "2.5": None, "btts": None}
        # usa a primeira casa
        markets = bookmakers[0].get("markets", [])
        odds_15 = None; odds_25 = None; odds_btts = None
        for bet in markets:
            label = (bet.get("label") or "").lower()
            if label == "goals over/under":
                for outcome in bet.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price")
                    if name == "Over 1.5" and price:
                        odds_15 = price
                    elif name == "Over 2.5" and price:
                        odds_25 = price
            elif label == "both teams to score":
                for outcome in bet.get("outcomes", []):
                    if outcome.get("name", "").lower() == "yes":
                        odds_btts = outcome.get("price")
        return {"1.5": odds_15, "2.5": odds_25, "btts": odds_btts}
    except Exception:
        return {"1.5": None, "2.5": None, "btts": None}

# =============================
# BTTS por médias históricas
# =============================
def calcular_btts_por_medias(media_casa, media_fora):
    gf_home = media_casa.get("media_gols_marcados", 1.2)
    gs_home = media_casa.get("media_gols_sofridos", 1.1)
    gf_away = media_fora.get("media_gols_marcados", 1.1)
    gs_away = media_fora.get("media_gols_sofridos", 1.2)

    estimativa = round((gf_home + gf_away + gs_home + gs_away) / 4, 2)
    if gf_home > 1.0 and gf_away > 1.0 and gs_home >= 0.9 and gs_away >= 0.9:
        return True, 75, estimativa
    elif gf_home >= 0.9 and gf_away >= 0.9:
        return True, 60, estimativa
    else:
        return False, 45, estimativa

# =============================
# GUI inputs
# =============================
aba = st.tabs(["⚡ Alertas de Jogos Hoje", "📊 Jogos de Temporadas Passadas"])

temporada_atual = st.selectbox("📅 Temporada (API-Football):", [2022, 2023, 2024, 2025], index=1)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

ligas_principais = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Brasileirão Série A": 71,
    "UEFA Champions League": 2,
    "Copa Libertadores": 13
}

# -----------------------------
# ABA 0: Alertas do dia
# -----------------------------
with aba[0]:
    st.subheader("📅 Jogos do dia e alertas de tendência")
    col1, col2 = st.columns([2,1])
    with col1:
        liga_filtrar = st.selectbox("Filtrar por liga (API-Football):", ["Todas"] + list(ligas_principais.keys()))
    with col2:
        liga_openliga_nome = st.selectbox("Liga histórica (OpenLigaDB) para médias:", list(ligas_openliga.keys()))
    temporada_hist = st.selectbox("Temporada histórica (OpenLigaDB):", ["2022","2023","2024","2025"], index=2)

    if st.button("🔍 Buscar jogos do dia"):
        with st.spinner("Buscando jogos da API-Football..."):
            try:
                url = f"{BASE_URL}/fixtures?date={hoje}"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                jogos_api = resp.json().get("response", [])
            except Exception as e:
                st.error(f"Erro ao consultar API-Football: {e}")
                jogos_api = []

        liga_openliga_id = ligas_openliga.get(liga_openliga_nome)
        jogos_hist = obter_jogos_liga_temporada(liga_openliga_id, temporada_hist) if liga_openliga_id else []
        medias_historicas = calcular_media_gols_times(jogos_hist) if jogos_hist else {}

        st.subheader(f"📝 Jogos retornados ({len(jogos_api)})")
        st.write(f"Filtro liga API-Football: {liga_filtrar} | Liga histórico: {liga_openliga_nome} ({temporada_hist})")

        melhores_15 = []
        melhores_25 = []
        melhores_btts = []

        for match in jogos_api:
            league_name = match.get("league", {}).get("name")
            if liga_filtrar != "Todas" and league_name != liga_filtrar:
                continue

            home = match.get("teams", {}).get("home", {}).get("name")
            away = match.get("teams", {}).get("away", {}).get("name")
            home_id = match.get("teams", {}).get("home", {}).get("id")
            away_id = match.get("teams", {}).get("away", {}).get("id")

            # H2H
            media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada_atual, max_jogos=5)

            # médias históricas por time (OpenLigaDB)
            media_casa = medias_historicas.get(home, {"media_gols_marcados": 1.5, "media_gols_sofridos": 1.2})
            media_fora = medias_historicas.get(away, {"media_gols_marcados": 1.4, "media_gols_sofridos": 1.1})

            # tendência + confiança
            estimativa, confianca, tendencia = calcular_tendencia_confianca_realista(media_h2h, media_casa, media_fora)

            # data/hora BRT formatada
            data_iso = match.get("fixture", {}).get("date", "")
            try:
                data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
                data_formatada = data_jogo.strftime("%d/%m/%Y")
                hora_formatada = data_jogo.strftime("%H:%M")
            except Exception:
                data_formatada = data_iso or "Desconhecida"
                hora_formatada = ""

            competicao = league_name or "Desconhecido"

            # odds reais
            odds = obter_odds(match.get("fixture", {}).get("id"))

            # BTTS por médias
            btts_flag, conf_btts, est_btts = calcular_btts_por_medias(media_casa, media_fora)

            # exibição
            with st.container():
                st.subheader(f"🏟️ {home} vs {away} — {competicao}")
                st.caption(f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)")
                st.write(f"📊 Estimativa de gols: **{estimativa:.2f}** | Tendência: **{tendencia}** | Confiança: **{confianca}%**")
                st.write(f"💰 Odds Over1.5 / Over2.5 / BTTS: {odds.get('1.5')} / {odds.get('2.5')} / {odds.get('btts')}")
                if btts_flag:
                    st.write(f"⚡ BTTS provável — Conf: {conf_btts}% | Est(BTTS): {est_btts:.2f}")

            # montar texto de tendência resumida para persistência
            tendencia_texto = ""
            if tendencia.startswith("Mais"):
                tendencia_texto += f"{tendencia} (est {estimativa:.2f})"
            if btts_flag:
                if tendencia_texto:
                    tendencia_texto += " | "
                tendencia_texto += f"Ambas Marcam (conf {conf_btts}%)"

            # se houver sinal, verificar e enviar alerta persistente
            if tendencia_texto:
                verificar_enviar_alerta(match, tendencia_texto, max(confianca, conf_btts), estimativa)

            # adicionar aos pools Top-3
            entry = {
                "home": home, "away": away, "competicao": competicao,
                "data": data_formatada, "hora": hora_formatada,
                "estimativa": estimativa, "confianca": confianca,
                "odd_15": odds.get("1.5"), "odd_25": odds.get("2.5"), "odd_btts": odds.get("btts"),
                "conf_btts": conf_btts, "est_btts": est_btts
            }

            if estimativa >= 1.8:
                melhores_15.append(entry)
            if estimativa >= 2.6:
                melhores_25.append(entry)
            if btts_flag:
                melhores_btts.append(entry)

        # ordenar e pegar top3
        melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
        melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
        melhores_btts = sorted(melhores_btts, key=lambda x: (x["conf_btts"], x["est_btts"]), reverse=True)[:3]

        # construir mensagem consolidada (única) e enviar ao canal alternativo 2
        if melhores_15 or melhores_25 or melhores_btts:
            msg_alt = f"📢 *TOP ENTRADAS - Alertas Consolidados* ({datetime.today().strftime('%d/%m/%Y')})\n\n"

            if melhores_15:
                odd_combinada_15 = 1.0
                msg_alt += "🔥 Top 3 +1.5 Gols\n"
                for j in melhores_15:
                    try: odd_combinada_15 *= float(j.get("odd_15") or 1.0)
                    except Exception: odd_combinada_15 *= 1.0
                    msg_alt += (f"🏆 {j['competicao']} | {j['data']} {j['hora']} BRT\n"
                                f"⚽ {j['home']} vs {j['away']}\n"
                                f"📊 Est: {j['estimativa']:.2f} | ✅ Conf: {j['confianca']}%\n"
                                f"💰 Odd Over1.5: {j.get('odd_15','N/A')}\n\n")
                msg_alt += f"🎯 Odd combinada (+1.5): {odd_combinada_15:.2f}\n\n"

            if melhores_25:
                odd_combinada_25 = 1.0
                msg_alt += "⚡ Top 3 +2.5 Gols\n"
                for j in melhores_25:
                    try: odd_combinada_25 *= float(j.get("odd_25") or 1.0)
                    except Exception: odd_combinada_25 *= 1.0
                    msg_alt += (f"🏆 {j['competicao']} | {j['data']} {j['hora']} BRT\n"
                                f"⚽ {j['home']} vs {j['away']}\n"
                                f"📊 Est: {j['estimativa']:.2f} | ✅ Conf: {j['confianca']}%\n"
                                f"💰 Odd Over2.5: {j.get('odd_25','N/A')}\n\n")
                msg_alt += f"🎯 Odd combinada (+2.5): {odd_combinada_25:.2f}\n\n"

            if melhores_btts:
                odd_combinada_btts = 1.0
                msg_alt += "🎯 Top 3 Ambas Marcam (BTTS)\n"
                for j in melhores_btts:
                    try: odd_combinada_btts *= float(j.get("odd_btts") or 1.0)
                    except Exception: odd_combinada_btts *= 1.0
                    msg_alt += (f"🏆 {j['competicao']} | {j['data']} {j['hora']} BRT\n"
                                f"⚽ {j['home']} vs {j['away']}\n"
                                f"📊 Est(BTTS): {j.get('est_btts',0):.2f} | ✅ Conf BTTS: {j.get('conf_btts','N/A')}%\n"
                                f"💰 Odd BTTS: {j.get('odd_btts','N/A')}\n\n")
                msg_alt += f"🎯 Odd combinada (BTTS): {odd_combinada_btts:.2f}\n\n"

            enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
            st.success("🚀 Top jogos consolidados enviados para o canal alternativo 2!")
        else:
            st.info("Nenhum jogo com tendência clara encontrado para Top-3.")

# -----------------------------
# ABA 1: Histórico (OpenLigaDB)
# -----------------------------
with aba[1]:
    st.subheader("📊 Jogos de Temporadas Passadas (OpenLigaDB)")
    temporada_hist2 = st.selectbox("📅 Temporada histórica:", ["2022","2023","2024","2025"], index=2, key="hist2")
    liga_nome_hist = st.selectbox("🏆 Liga (OpenLigaDB):", list(ligas_openliga.keys()), key="hist_liga2")
    liga_id_hist = ligas_openliga.get(liga_nome_hist)

    if st.button("🔍 Buscar jogos da temporada", key="btn_hist2"):
        with st.spinner("Buscando jogos..."):
            jogos_hist2 = obter_jogos_liga_temporada(liga_id_hist, temporada_hist2)
            if not jogos_hist2:
                st.info("Nenhum jogo encontrado para essa temporada/liga.")
            else:
                medias_hist2 = calcular_media_gols_times(jogos_hist2)
                st.success(f"{len(jogos_hist2)} jogos encontrados - exibindo médias (parcial)")
                shown = 0
                for team, vals in medias_hist2.items():
                    st.write(f"{team}: Marcados {vals['media_gols_marcados']:.2f} | Sofridos {vals['media_gols_sofridos']:.2f}")
                    shown += 1
                    if shown >= 50:
                        break
