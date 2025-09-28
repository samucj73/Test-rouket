import requests
import datetime
import time
import streamlit as st

# =============================
# Configurações API
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configurações Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# =============================
# Ligas monitoradas
# =============================
LIGAS = ["PL", "PD", "BL1", "SA", "FL1", "BSA"]

# =============================
# Funções utilitárias
# =============================
def enviar_alerta(msg: str):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(BASE_URL_TG, data=payload, timeout=10)
    except Exception as e:
        st.error(f"Erro ao enviar alerta: {e}")

def carregar_estatisticas_liga(codigo_liga: str):
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/standings"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return {}
    data = resp.json()

    stats = {}
    for table in data.get("standings", []):
        for entry in table.get("table", []):
            team_id = entry["team"]["id"]
            stats[team_id] = {
                "name": entry["team"]["name"],
                "played": entry["playedGames"],
                "gf": entry["goalsFor"],
                "ga": entry["goalsAgainst"]
            }
    return stats

def calcular_gols_estimados(match, stats_liga):
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]

    home_stats = stats_liga.get(home_id, None)
    away_stats = stats_liga.get(away_id, None)

    if not home_stats or not away_stats:
        return 2.5

    def media(time):
        return (time["gf"] + time["ga"]) / time["played"] if time["played"] > 0 else 2.5

    media_home = media(home_stats)
    media_away = media(away_stats)

    return round((media_home + media_away) / 2, 2)

def buscar_jogos_dia(codigo_liga: str, data: str):
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/matches?dateFrom={data}&dateTo={data}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return []
    return resp.json().get("matches", [])

def selecionar_top3_distintos(partidas_info, max_por_faixa=3):
    usadas = set()
    top_15, top_25, top_35 = [], [], []

    partidas_info.sort(key=lambda x: x["estimativa"], reverse=True)

    for jogo in partidas_info:
        if len(top_25) < max_por_faixa and jogo["id"] not in usadas:
            top_25.append(jogo); usadas.add(jogo["id"])
    for jogo in partidas_info:
        if len(top_15) < max_por_faixa and jogo["id"] not in usadas:
            top_15.append(jogo); usadas.add(jogo["id"])
    for jogo in partidas_info:
        if len(top_35) < max_por_faixa and jogo["id"] not in usadas:
            top_35.append(jogo); usadas.add(jogo["id"])

    return top_15, top_25, top_35

def conferir_resultados(jogos_previstos):
    resultados = []
    for faixa, jogos in jogos_previstos.items():
        for jogo in jogos:
            url = f"{BASE_URL_FD}/matches/{jogo['id']}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()["match"]

            if data["status"] == "FINISHED":
                gols_home = data["score"]["fullTime"]["home"]
                gols_away = data["score"]["fullTime"]["away"]
                total = gols_home + gols_away

                if faixa == "+1.5":
                    bateu = total > 1.5
                elif faixa == "+2.5":
                    bateu = total > 2.5
                else:
                    bateu = total > 3.5

                status = "🟢 GREEN" if bateu else "🔴 RED"
                msg = f"{jogo['home']} vs {jogo['away']} | {faixa} | {total} gols → {status}"
                enviar_alerta(msg)
                resultados.append(msg)
    return resultados

# =============================
# Interface Streamlit
# =============================
st.title("⚽ Alertas Automáticos de Gols")
st.write("Baseado na API Football-Data.org")

hoje = datetime.date.today().strftime("%Y-%m-%d")

if st.button("📅 Buscar Jogos de Hoje"):
    todas_partidas = []
    stats_cache = {}

    for liga in LIGAS:
        stats_cache[liga] = carregar_estatisticas_liga(liga)
        jogos = buscar_jogos_dia(liga, hoje)
        for j in jogos:
            estimativa = calcular_gols_estimados(j, stats_cache[liga])
            todas_partidas.append({
                "id": j["id"],
                "home": j["homeTeam"]["name"],
                "away": j["awayTeam"]["name"],
                "estimativa": estimativa
            })

    top15, top25, top35 = selecionar_top3_distintos(todas_partidas)

    st.subheader("🚨 Top Jogos do Dia")
    st.write("**Top +2.5:**")
    for j in top25: st.write(f"{j['home']} vs {j['away']} → {j['estimativa']}")

    st.write("**Top +1.5:**")
    for j in top15: st.write(f"{j['home']} vs {j['away']} → {j['estimativa']}")

    st.write("**Top +3.5:**")
    for j in top35: st.write(f"{j['home']} vs {j['away']} → {j['estimativa']}")

    if st.button("🚀 Enviar Alertas no Telegram"):
        alerta = "🚨 *ALERTAS DO DIA*\n\n"
        alerta += "*Top +2.5:*\n" + "\n".join([f"{j['home']} vs {j['away']} → {j['estimativa']}" for j in top25]) + "\n\n"
        alerta += "*Top +1.5:*\n" + "\n".join([f"{j['home']} vs {j['away']} → {j['estimativa']}" for j in top15]) + "\n\n"
        alerta += "*Top +3.5:*\n" + "\n".join([f"{j['home']} vs {j['away']} → {j['estimativa']}" for j in top35])
        enviar_alerta(alerta)
        st.success("✅ Alertas enviados para o Telegram!")

    if st.button("✅ Conferir Resultados"):
        resultados = conferir_resultados({"+1.5": top15, "+2.5": top25, "+3.5": top35})
        for r in resultados:
            st.write(r)
