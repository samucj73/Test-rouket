import requests
import streamlit as st
import datetime
import pytz

# =============================
# Configurações API Football-Data.org
# =============================
API_KEY = "9058de85e3324bdb969adc005b5d918a"
HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"

# =============================
# Configuração Telegram
# =============================
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# =============================
# Campeonatos disponíveis
# =============================
COMPETICOES_PADRAO = {
    "PL": "Premier League (Inglaterra)",
    "PD": "La Liga (Espanha)",
    "SA": "Serie A (Itália)",
    "BL1": "Bundesliga (Alemanha)",
    "FL1": "Ligue 1 (França)",
    "BSA": "Brasileirão Série A (Brasil)",
    "PPL": "Primeira Liga (Portugal)"
}

# =============================
# Funções auxiliares
# =============================

def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def buscar_jogos_fd(codigo_liga: str, data: str):
    """Busca partidas de uma liga em uma data."""
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/matches?dateFrom={data}&dateTo={data}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro buscar jogos:", resp.status_code, resp.text)
        return []
    return resp.json().get("matches", [])

def conferir_jogo_fd(match_id: int):
    """Consulta o status e placar final de um jogo."""
    url = f"{BASE_URL_FD}/matches/{match_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro conferir jogo:", resp.status_code, resp.text)
        return None
    return resp.json().get("match", {})

def carregar_estatisticas_liga(codigo_liga: str):
    """Carrega estatísticas dos times de uma liga (gols feitos/sofridos)."""
    url = f"{BASE_URL_FD}/competitions/{codigo_liga}/standings"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print("Erro ao buscar estatísticas:", resp.status_code, resp.text)
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
    """Calcula a estimativa de gols de um jogo usando as médias reais da temporada."""
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]

    home_stats = stats_liga.get(home_id, None)
    away_stats = stats_liga.get(away_id, None)

    if not home_stats or not away_stats:
        return 2.5  # fallback

    def media(time):
        if time["played"] > 0:
            return (time["gf"] + time["ga"]) / time["played"]
        return 2.5

    media_home = media(home_stats)
    media_away = media(away_stats)

    return round((media_home + media_away) / 2, 2)

def selecionar_top3_distintos(partidas, stats_liga, max_por_faixa=3):
    """Seleciona até 3 partidas distintas para cada faixa de gols."""
    top_15, top_25, top_35 = [], [], []

    for match in partidas:
        estimativa = calcular_gols_estimados(match, stats_liga)
        partida_info = {
            "id": match["id"],
            "home": match["homeTeam"]["name"],
            "away": match["awayTeam"]["name"],
            "estimativa": estimativa
        }

        if estimativa >= 1.5 and len(top_15) < max_por_faixa:
            top_15.append(partida_info)
        if estimativa >= 2.5 and len(top_25) < max_por_faixa:
            top_25.append(partida_info)
        if estimativa >= 3.5 and len(top_35) < max_por_faixa:
            top_35.append(partida_info)

    return top_15, top_25, top_35

# =============================
# Streamlit App
# =============================
st.set_page_config(page_title="Futebol Alertas Top3", layout="wide")
st.title("⚽ Futebol Alertas Top3 — Football-Data.org")

aba = st.tabs(["📊 Seleção & Envio", "✅ Conferência Resultados"])

# -----------------------------
# Aba 1 - Seleção & Envio
# -----------------------------
with aba[0]:
    st.subheader("📅 Selecionar Campeonatos")
    ligas_escolhidas = st.multiselect("Escolha os campeonatos:",
                                      options=list(COMPETICOES_PADRAO.keys()),
                                      format_func=lambda x: COMPETICOES_PADRAO[x])

    hoje = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%Y-%m-%d")

    if st.button("🔎 Buscar Jogos & Enviar Alertas"):
        todas_partidas = []
        mensagens = []
        for liga in ligas_escolhidas:
            jogos = buscar_jogos_fd(liga, hoje)
            stats = carregar_estatisticas_liga(liga)
            if jogos:
                top15, top25, top35 = selecionar_top3_distintos(jogos, stats)
                mensagens.append(f"🏆 {COMPETICOES_PADRAO[liga]}")
                for titulo, lista in [("+1.5 Gols", top15), ("+2.5 Gols", top25), ("+3.5 Gols", top35)]:
                    mensagens.append(f"\n🎯 *{titulo}*")
                    for p in lista:
                        mensagens.append(f"🏟️ {p['home']} vs {p['away']} | Estim.: {p['estimativa']}")

        if mensagens:
            mensagem_final = "📢 *Top3 Alertas do Dia*\n" + "\n".join(mensagens)
            st.code(mensagem_final)
            enviar_telegram(mensagem_final)
        else:
            st.warning("Nenhum jogo encontrado.")

# -----------------------------
# Aba 2 - Conferência
# -----------------------------
with aba[1]:
    st.subheader("📊 Conferência dos Jogos")

    match_id = st.text_input("Digite o ID do jogo para conferir:")
    if st.button("Conferir Jogo"):
        info = conferir_jogo_fd(match_id)
        if not info:
            st.error("Não foi possível buscar o jogo.")
        else:
            home = info["homeTeam"]["name"]
            away = info["awayTeam"]["name"]
            status = info["status"]
            gols_home = info["score"]["fullTime"]["home"]
            gols_away = info["score"]["fullTime"]["away"]
            total = (gols_home or 0) + (gols_away or 0)

            st.write(f"🏟️ {home} vs {away}")
            st.write(f"📌 Status: {status}")
            st.write(f"⚽ Placar final: {gols_home} x {gols_away}")

            for faixa in [1.5, 2.5, 3.5]:
                resultado = "🟢 GREEN" if total > faixa else "🔴 RED"
                st.write(f"{resultado} para +{faixa} gols")
