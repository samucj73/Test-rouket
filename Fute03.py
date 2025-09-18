import streamlit as st
from datetime import datetime, timedelta
import requests
import os
import json

# =============================
# Configurações API
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

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"

# =============================
# Funções de persistência
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

# =============================
# Funções auxiliares
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})
    except Exception as e:
        st.warning(f"Erro ao enviar mensagem Telegram: {e}")

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0
    status = fixture.get("fixture", {}).get("status", {}).get("long", "Desconhecido")

    data_iso = fixture["fixture"]["date"]
    data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ *Alerta de Gols!*\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"📌 Status: {status}\n"
        f"🔢 Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas()
    fixture_id = str(fixture["fixture"]["id"])
    home_goals = fixture.get("goals", {}).get("home", 0) or 0
    away_goals = fixture.get("goals", {}).get("away", 0) or 0

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (ultimo["home_goals"] != home_goals or
            ultimo["away_goals"] != away_goals or
            ultimo["tendencia"] != tendencia):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia
        }
        salvar_alertas(alertas)

# =============================
# Funções cálculo tendência
# =============================
# =============================
# Funções cálculo tendência (ajustadas)
# =============================
def calcular_tendencia_confianca_ajustada(media_h2h, media_casa, media_fora, peso_h2h=0.3):
    """
    Calcula estimativa de gols, confiança e tendência usando médias históricas e H2H.
    """
    # Média do time da casa e visitante
    media_time_casa = media_casa.get("media_gols_marcados", 0) + media_fora.get("media_gols_sofridos", 0)
    media_time_fora = media_fora.get("media_gols_marcados", 0) + media_casa.get("media_gols_sofridos", 0)

    # Estimativa base
    estimativa_base = (media_time_casa + media_time_fora) / 2

    # Combinar com média H2H ponderada
    estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * media_h2h.get("media_gols", 0)

    # Ajuste de tendência e confiança
    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5) * 15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5) * 20)
    else:
        tendencia = "Menos 1.5"
        confianca = min(95, 50 + (1.5 - estimativa_final) * 20)

    return round(estimativa_final, 2), round(confianca, 0), tendencia

# =============================
# Funções cálculo média H2H (ajustadas)
# =============================
def media_gols_confrontos_diretos(home_id, away_id, temporada=None, max_jogos=5):
    """
    Calcula média ponderada de gols em confrontos diretos recentes entre os times.
    """
    try:
        url = f"{BASE_URL}/fixtures/headtohead?h2h={home_id}-{away_id}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"media_gols": 0, "total_jogos": 0}

        jogos = response.json().get("response", [])
        if temporada:
            jogos = [j for j in jogos if j["league"]["season"] == temporada]

        # Ordena do mais recente para o mais antigo
        jogos = sorted(jogos, key=lambda x: x["fixture"]["date"], reverse=True)[:max_jogos]
        if not jogos:
            return {"media_gols": 0, "total_jogos": 0}

        total_pontos, total_peso = 0, 0
        for idx, j in enumerate(jogos):
            if j["fixture"]["status"]["short"] != "FT":
                continue
            home_goals = j["score"]["fulltime"]["home"]
            away_goals = j["score"]["fulltime"]["away"]
            gols = home_goals + away_goals
            peso = max_jogos - idx  # jogos mais recentes têm peso maior
            total_pontos += gols * peso
            total_peso += peso

        media_ponderada = round(total_pontos / total_peso, 2) if total_peso else 0
        return {"media_gols": media_ponderada, "total_jogos": len(jogos)}

    except Exception:
        return {"media_gols": 0, "total_jogos": 0}

# =============================
# Função cálculo médias históricas (OpenLigaDB)
# =============================
def calcular_media_gols_times(jogos_hist):
    """
    Retorna médias de gols marcados e sofridos para cada time baseado em jogos históricos.
    """
    stats = {}
    for j in jogos_hist:
        home, away = j["team1"]["teamName"], j["team2"]["teamName"]
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
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 0
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 0
        medias[time] = {"media_gols_marcados": media_marcados, "media_gols_sofridos": media_sofridos}
    return medias


# =============================
# OpenLigaDB
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
        home, away = j["team1"]["teamName"], j["team2"]["teamName"]
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
        media_marcados = sum(gols["marcados"]) / len(gols["marcados"]) if gols["marcados"] else 0
        media_sofridos = sum(gols["sofridos"]) / len(gols["sofridos"]) if gols["sofridos"] else 0
        medias[time] = {"media_gols_marcados": media_marcados, "media_gols_sofridos": media_sofridos}
    return medias

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Alertas e Jogos Históricos", layout="wide")
st.title("⚽ Sistema de Alertas de Gols + Jogos Históricos")
aba = st.tabs(["⚡ Alertas de Jogos Hoje", "📊 Jogos de Temporadas Passadas"])

# ---------- ABA 1:
# ---------- ABA 1: Alertas ----------
with aba[0]:
    st.subheader("📅 Jogos do dia e alertas de tendência")
    temporada_atual = st.selectbox("📅 Escolha a temporada:", [2022, 2023, 2024, 2025], index=1)
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

    if st.button("🔍 Buscar jogos do dia"):
        with st.spinner("Buscando jogos da API Football..."):
            url = f"{BASE_URL}/fixtures?date={hoje}"
            response = requests.get(url, headers=HEADERS)
            jogos = response.json().get("response", [])

        liga_nome = st.selectbox("🏆 Escolha a liga histórica para médias:", list(ligas_openliga.keys()))
        liga_id = ligas_openliga[liga_nome]
        temporada_hist = st.selectbox("📅 Temporada histórica:", ["2022", "2023", "2024", "2025"], index=2)
        jogos_hist = obter_jogos_liga_temporada(liga_id, temporada_hist)
        medias_historicas = calcular_media_gols_times(jogos_hist)

        melhores_15, melhores_25 = [], []

        for match in jogos:
            league_id = match.get("league", {}).get("id")
            if league_id not in ligas_principais.values():
                continue

            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            home_id = match["teams"]["home"]["id"]
            away_id = match["teams"]["away"]["id"]

            # Média H2H via API
            media_h2h = media_gols_confrontos_diretos(home_id, away_id, temporada_atual, max_jogos=5)
            media_casa = medias_historicas.get(home, {"media_gols_marcados": 1, "media_gols_sofridos": 1})
            media_fora = medias_historicas.get(away, {"media_gols_marcados": 1, "media_gols_sofridos": 1})

            estimativa, confianca, tendencia = calcular_tendencia_confianca_ajustada(
                media_h2h=media_h2h,
                media_casa=media_casa,
                media_fora=media_fora
            )

            # Formatar hora
            data_iso = match["fixture"]["date"]
            data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
            hora_formatada = data_jogo.strftime("%H:%M")
            competicao = match.get("league", {}).get("name", "Desconhecido")

            # Obter odds
            odds = obter_odds(match["fixture"]["id"])

            # Mostrar na interface
            with st.container():
                st.subheader(f"🏟️ {home} vs {away}")
                st.caption(f"Liga: {competicao} | Temporada: {temporada_atual}")
                st.write(f"📊 Estimativa de gols: **{estimativa:.2f}**")
                st.write(f"🔥 Tendência: **{tendencia}**")
                st.write(f"✅ Confiança: **{confianca:.0f}%**")
                st.write(f"💰 Odds Over 1.5: {odds['1.5']} | Over 2.5: {odds['2.5']}")

            # Enviar alerta Telegram
            verificar_enviar_alerta(match, tendencia, confianca, estimativa)

            # Adicionar aos Top 3
            if tendencia == "Mais 1.5":
                melhores_15.append({
                    "home": home, "away": away,
                    "estimativa": estimativa, "confianca": confianca,
                    "hora": hora_formatada, "competicao": competicao,
                    "odd_15": odds["1.5"]
                })
            elif tendencia == "Mais 2.5":
                melhores_25.append({
                    "home": home, "away": away,
                    "estimativa": estimativa, "confianca": confianca,
                    "hora": hora_formatada, "competicao": competicao,
                    "odd_25": odds["2.5"]
                })

        # Top 3
        melhores_15 = sorted(melhores_15, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]
        melhores_25 = sorted(melhores_25, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:3]

        if melhores_15 or melhores_25:
            msg_alt = "📢 *TOP ENTRADAS - Alertas Consolidados*\n\n"

            if melhores_15:
                odd_combinada_15 = 1
                msg_alt += "🔥 Top 3 Jogos para +1.5 Gols\n"
                for j in melhores_15:
                    odd_combinada_15 *= float(j.get("odd_15") or 1)
                    msg_alt += (
                        f"🏆 {j['competicao']}\n"
                        f"🕒 {j['hora']} BRT\n"
                        f"🏟️ {j['home']} vs {j['away']}\n"
                        f"📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n"
                        f"💰 Odd: {j.get('odd_15', 'N/A')}\n\n"
                    )
                msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_15:.2f}\n\n"

            if melhores_25:
                odd_combinada_25 = 1
                msg_alt += "⚡ Top 3 Jogos para +2.5 Gols\n"
                for j in melhores_25:
                    odd_combinada_25 *= float(j.get("odd_25") or 1)
                    msg_alt += (
                        f"🏆 {j['competicao']}\n"
                        f"🕒 {j['hora']} BRT\n"
                        f"🏟️ {j['home']} vs {j['away']}\n"
                        f"📊 Estimativa: {j['estimativa']:.2f} | ✅ Confiança: {j['confianca']:.0f}%\n"
                        f"💰 Odd: {j.get('odd_25', 'N/A')}\n\n"
                    )
                msg_alt += f"🎯 Odd combinada (3 jogos): {odd_combinada_25:.2f}\n\n"

            enviar_telegram(msg_alt, TELEGRAM_CHAT_ID_ALT2)
            st.success("🚀 Top jogos enviados para o canal alternativo 2!")
        else:
            st.info("Nenhum jogo com tendência clara de +1.5 ou +2.5 gols encontrado.")

# ---------- ABA 2: Jogos históricos ----------
with aba[1]:
    st.subheader("📊 Jogos de Temporadas Passadas (OpenLigaDB)")
    temporada_hist = st.selectbox("📅 Escolha a temporada histórica:", ["2022", "2023", "2024", "2025"], index=2, key="hist")
    liga_nome_hist = st.selectbox("🏆 Escolha a Liga:", list(ligas_openliga.keys()), key="hist_liga")
    liga_id_hist = ligas_openliga[liga_nome_hist]

    if st.button("🔍 Buscar jogos da temporada", key="btn_hist"):
        with st.spinner("Buscando jogos..."):
            jogos_hist = obter_jogos_liga_temporada(liga_id_hist, temporada_hist)
            if not jogos_hist:
                st.info("Nenhum jogo encontrado para essa temporada/liga.")
            else:
                st.success(f"{len(jogos_hist)} jogos encontrados na {liga_nome_hist} ({temporada_hist})")
                for j in jogos_hist[:50]:  # Limite de exibição inicial
                    home = j["team1"]["teamName"]
                    away = j["team2"]["teamName"]
                    placar = "-"
                    for r in j.get("matchResults", []):
                        if r.get("resultTypeID") == 2:
                            placar = f"{r.get('pointsTeam1',0)} x {r.get('pointsTeam2',0)}"
                            break
                    data = j.get("matchDateTime") or j.get("matchDateTimeUTC") or "Desconhecida"
                    st.write(f"🏟️ {home} vs {away} | 📅 {data} | ⚽ Placar: {placar}")
