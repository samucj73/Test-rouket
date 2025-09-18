import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os

# =============================
# Configurações API OpenLigaDB
# =============================
BASE_URL = "https://www.openligadb.de/api"
ALERTAS_PATH = "alertas.json"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"       # canal principal
TELEGRAM_CHAT_ID_ALT2 = "-1002932611974"  # canal alternativo
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

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
    requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg})

def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    home = fixture["MatchTeam1"]["TeamName"]
    away = fixture["MatchTeam2"]["TeamName"]

    home_goals = fixture.get("MatchResults", [{}])[0].get("PointsTeam1", 0) or 0
    away_goals = fixture.get("MatchResults", [{}])[0].get("PointsTeam2", 0) or 0
    status = fixture.get("MatchIsFinished", False)

    data_jogo = datetime.strptime(fixture["MatchDateTime"], "%Y-%m-%dT%H:%M:%S")
    data_jogo_brt = data_jogo - timedelta(hours=3)
    data_formatada = data_jogo_brt.strftime("%d/%m/%Y")
    hora_formatada = data_jogo_brt.strftime("%H:%M")

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {'Finalizado' if status else 'Ao vivo'}\n"
        f"Placar atual: {home} {home_goals} x {away_goals} {away}"
    )
    enviar_telegram(msg, TELEGRAM_CHAT_ID)

def verificar_enviar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas()
    fixture_id = str(fixture["MatchID"])

    home_goals = fixture.get("MatchResults", [{}])[0].get("PointsTeam1", 0) or 0
    away_goals = fixture.get("MatchResults", [{}])[0].get("PointsTeam2", 0) or 0

    precisa_enviar = False
    if fixture_id not in alertas:
        precisa_enviar = True
    else:
        ultimo = alertas[fixture_id]
        if (
            ultimo["home_goals"] != home_goals
            or ultimo["away_goals"] != away_goals
            or ultimo["tendencia"] != tendencia
        ):
            precisa_enviar = True

    if precisa_enviar:
        enviar_alerta_telegram(fixture, tendencia, confianca, estimativa)
        alertas[fixture_id] = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tendencia": tendencia,
        }
        salvar_alertas(alertas)

# =============================
# Estatísticas individuais dos times
# =============================
def obter_jogos_time(time_id, temporada_id):
    url = f"{BASE_URL}/getmatchdata/blid/{temporada_id}"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    jogos = response.json()
    return [j for j in jogos if j["Team1Id"] == time_id or j["Team2Id"] == time_id]

def calcular_estatisticas_time(jogos, time_id):
    stats = {
        "jogos_validos": 0,
        "gols_marc": 0,
        "gols_sof": 0,
        "media_marc": 0,
        "media_sof": 0,
        "over15_pct": 0,
        "over25_pct": 0,
        "over35_pct": 0,
        "avg_gd": 0,
    }
    if not jogos:
        return stats

    gols_total = 0
    gols_marc_total = 0
    gols_sof_total = 0
    over15 = 0
    over25 = 0
    over35 = 0

    for j in jogos:
        resultado = j.get("MatchResults", [{}])[0]
        gols_casa = resultado.get("PointsTeam1", 0) or 0
        gols_fora = resultado.get("PointsTeam2", 0) or 0
        if j["Team1Id"] == time_id:
            gols_marc_total += gols_casa
            gols_sof_total += gols_fora
            total = gols_casa + gols_fora
        else:
            gols_marc_total += gols_fora
            gols_sof_total += gols_casa
            total = gols_casa + gols_fora

        gols_total += total
        over15 += int(total > 1.5)
        over25 += int(total > 2.5)
        over35 += int(total > 3.5)

    jogos_validos = len(jogos)
    stats.update({
        "jogos_validos": jogos_validos,
        "gols_marc": gols_marc_total,
        "gols_sof": gols_sof_total,
        "media_marc": gols_marc_total / jogos_validos if jogos_validos else 0,
        "media_sof": gols_sof_total / jogos_validos if jogos_validos else 0,
        "over15_pct": over15 / jogos_validos * 100 if jogos_validos else 0,
        "over25_pct": over25 / jogos_validos * 100 if jogos_validos else 0,
        "over35_pct": over35 / jogos_validos * 100 if jogos_validos else 0,
        "avg_gd": (gols_marc_total - gols_sof_total) / jogos_validos if jogos_validos else 0
    })
    return stats

# =============================
# H2H média gols
# =============================
def media_gols_h2h(home_id, away_id, temporada_id, max_jogos=5):
    url = f"{BASE_URL}/getmatchdata/blid/{temporada_id}"
    response = requests.get(url)
    if response.status_code != 200:
        return 0, 0
    jogos = response.json()
    confrontos = [j for j in jogos if (j["Team1Id"]==home_id and j["Team2Id"]==away_id) or (j["Team1Id"]==away_id and j["Team2Id"]==home_id)]
    confrontos = sorted(confrontos, key=lambda x: x["MatchDateTime"], reverse=True)[:max_jogos]

    if not confrontos:
        return 0, 0
    total_gols = 0
    for j in confrontos:
        r = j.get("MatchResults", [{}])[0]
        total_gols += (r.get("PointsTeam1",0) + r.get("PointsTeam2",0))
    return round(total_gols / len(confrontos),2), len(confrontos)

# =============================
# Tendência Over/Under
# =============================
def calcular_tendencia(home_stats, away_stats, h2h_media, peso_h2h=0.3):
    media_time_casa = home_stats["media_marc"] + away_stats["media_sof"]
    media_time_fora = away_stats["media_marc"] + home_stats["media_sof"]
    estimativa_base = (media_time_casa + media_time_fora)/2
    estimativa_final = (1 - peso_h2h)*estimativa_base + peso_h2h*h2h_media

    if estimativa_final >= 2.5:
        tendencia = "Mais 2.5"
        confianca = min(95, 60 + (estimativa_final - 2.5)*15)
    elif estimativa_final >= 1.5:
        tendencia = "Mais 1.5"
        confianca = min(95, 55 + (estimativa_final - 1.5)*20)
    else:
       # tendencia = "Menos 1.5
        tendencia = "Menos 1.5"
        confianca = min(95, 55 + (1.5 - estimativa_final)*20)

    return estimativa_final, confianca, tendencia

# =============================
# Interface Streamlit
# =============================
st.set_page_config(page_title="⚽ Sistema Over/Under", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos Over/Under")
st.markdown("Monitora jogos históricos e atuais, calculando tendência de gols e enviando top 3 para o Telegram.")

temporadas = [2020, 2021, 2022, 2023, 2024, 2025]
temporada = st.selectbox("📅 Escolha a temporada:", temporadas, index=len(temporadas)-2)
data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
hoje = data_selecionada.strftime("%Y-%m-%d")

if st.button("🔍 Buscar jogos do dia"):
    url = f"{BASE_URL}/getmatchdata/bydate/{hoje}"
    response = requests.get(url)
    jogos = response.json() if response.status_code == 200 else []

    st.subheader("📝 Jogos encontrados")
    st.write(f"{len(jogos)} jogos encontrados para {hoje}")

    top_jogos = []

    for j in jogos:
        home_id = j["Team1Id"]
        away_id = j["Team2Id"]
        home_name = j["MatchTeam1"]["TeamName"]
        away_name = j["MatchTeam2"]["TeamName"]

        # Estatísticas individuais
        jogos_home = obter_jogos_time(home_id, temporada)
        jogos_away = obter_jogos_time(away_id, temporada)
        home_stats = calcular_estatisticas_time(jogos_home, home_id)
        away_stats = calcular_estatisticas_time(jogos_away, away_id)

        # H2H
        h2h_media, h2h_count = media_gols_h2h(home_id, away_id, temporada)

        # Tendência
        estimativa, confianca, tendencia = calcular_tendencia(home_stats, away_stats, h2h_media)

        # Exibição limpa
        st.markdown(f"### 🏟️ {home_name} vs {away_name}")
        st.write(f"📊 Estimativa total (gols): **{estimativa:.2f}**")
        st.write(f"🔥 Tendência linha: **{tendencia}** | Confiança: **{confianca:.0f}%**")
        st.write(f"📈 Detalhes:")
        st.write(f"• Média H2H: {h2h_media} (últimos {h2h_count})")
        st.write(f"• Home stats: Jogos={home_stats['jogos_validos']}, Gols Marc={home_stats['gols_marc']}, Gols Sofr={home_stats['gols_sof']}, Média Marc={home_stats['media_marc']:.2f}, Média Sofr={home_stats['media_sof']:.2f}")
        st.write(f"• Away stats: Jogos={away_stats['jogos_validos']}, Gols Marc={away_stats['gols_marc']}, Gols Sofr={away_stats['gols_sof']}, Média Marc={away_stats['media_marc']:.2f}, Média Sofr={away_stats['media_sof']:.2f}")

        verificar_enviar_alerta(j, tendencia, confianca, estimativa)

        # Adiciona ao top
        top_jogos.append({
            "home": home_name,
            "away": away_name,
            "estimativa": estimativa,
            "confianca": confianca,
            "tendencia": tendencia,
            "jogo": j
        })

    # Top 3 jogos mais confiáveis
    top_jogos_sorted = sorted(top_jogos, key=lambda x: x["confianca"], reverse=True)[:3]
    if top_jogos_sorted:
        msg_top3 = "📢 TOP 3 Jogos Recomendados\n\n"
        for tj in top_jogos_sorted:
            msg_top3 += (
                f"🏟️ {tj['home']} vs {tj['away']}\n"
                f"📊 Estimativa: {tj['estimativa']:.2f} gols | 🔥 Tendência: {tj['tendencia']} | ✅ Confiança: {tj['confianca']:.0f}%\n\n"
            )
        enviar_telegram(msg_top3, TELEGRAM_CHAT_ID_ALT2)
        st.success("🚀 Top 3 jogos enviados para o canal alternativo!")
