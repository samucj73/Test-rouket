import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json
import os

# ==========================
# Configurações da API e Telegram
# ==========================
API_KEY = "f07fc89fcff4416db7f079fda478dd61"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "5121457416"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas_em_andamento.json"

st.set_page_config(page_title="Jogos e Tendência de Gols", layout="wide")
st.title("⚽ Jogos e Tendência de Gols - API Football")

# ==========================
# ==========================
# Função para enviar alerta no Telegram
# ==========================
def enviar_alerta_telegram(fixture, tendencia, confianca, estimativa):
    teams = fixture.get("teams", {})
    home_team = teams.get("home", {}).get("name", "Time da Casa")
    away_team = teams.get("away", {}).get("name", "Time de Fora")
    status = fixture.get("status", {}).get("long", "Desconhecido")
    goals = fixture.get("goals", {})
    home_goals = goals.get("home", 0)
    away_goals = goals.get("away", 0)

    msg = (
        f"⚽ Alerta de Gols!\n"
        f"🏟️ {home_team} vs {away_team}\n"
        f"Tendência: {tendencia}\n"
        f"Estimativa: {estimativa:.2f} gols\n"
        f"Confiança: {confianca:.0f}%\n"
        f"Status: {status}\n"
        f"Placar atual: {home_team} {home_goals} x {away_goals} {away_team}"
    )
    try:
        requests.get(BASE_URL_TG, params={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        st.error(f"Erro ao enviar alerta Telegram: {e}")


# ==========================
# Controle de alertas (para evitar repetição desnecessária)
# ==========================
def carregar_alertas_andamento():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas_andamento(alertas):
    with open(ALERTAS_PATH, "w") as f:
        json.dump(alertas, f)

def verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa):
    alertas = carregar_alertas_andamento()
    fixture_id = str(fixture["id"])

    goals = fixture.get("goals", {})
    home_goals = goals.get("home", 0)
    away_goals = goals.get("away", 0)

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
            "tendencia": tendencia
        }
        salvar_alertas_andamento(alertas)

# ==========================
# Função para buscar ligas
# ==========================
@st.cache_data
def get_ligas():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()["response"]
        ligas = [
            {"id": l["league"]["id"], "nome": l["league"]["name"], "pais": l["country"]["name"]}
            for l in data
        ]
        return ligas
    else:
        st.error(f"Erro {response.status_code}: {response.text}")
        return []

# ==========================
# Buscar jogos finalizados da liga e calcular estatísticas
# ==========================
@st.cache_data
def buscar_estatisticas_liga(liga_id, temporada=None):
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code} ao buscar temporadas: {response.text}")
        return {}

    ligas_data = response.json()["response"]
    temporada_liga = temporada
    if not temporada_liga:
        for l in ligas_data:
            if l["league"]["id"] == liga_id:
                temporadas = l["seasons"]
                temporadas.sort(key=lambda x: x["year"], reverse=True)
                temporada_liga = temporadas[0]["year"]
                break
    if not temporada_liga:
        st.error("Não foi possível determinar a temporada.")
        return {}

    url_fixtures = f"{BASE_URL}/fixtures?league={liga_id}&season={temporada_liga}"
    response = requests.get(url_fixtures, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Erro {response.status_code} ao buscar jogos: {response.text}")
        return {}

    jogos = response.json()["response"]
    if not jogos:
        st.warning(f"🔎 API retornou 0 jogos da liga {liga_id} na temporada {temporada_liga}")
        return {}

    times_stats = {}
    for j in jogos:
        fixture = j["fixture"]
        status = fixture["status"]["short"]
        if status != "FT":
            continue  # Apenas finalizados

        home = j["teams"]["home"]
        away = j["teams"]["away"]
        home_goals = j["score"]["fulltime"]["home"]
        away_goals = j["score"]["fulltime"]["away"]

        for t in [home, away]:
            if t["id"] not in times_stats:
                times_stats[t["id"]] = {
                    "nome": t["name"],
                    "logo": t["logo"],
                    "jogos_disputados": 0,
                    "vitorias": 0,
                    "empates": 0,
                    "derrotas": 0,
                    "gols_marcados": 0,
                    "gols_sofridos": 0
                }

        times_stats[home["id"]]["jogos_disputados"] += 1
        times_stats[away["id"]]["jogos_disputados"] += 1
        times_stats[home["id"]]["gols_marcados"] += home_goals
        times_stats[home["id"]]["gols_sofridos"] += away_goals
        times_stats[away["id"]]["gols_marcados"] += away_goals
        times_stats[away["id"]]["gols_sofridos"] += home_goals

        if home_goals > away_goals:
            times_stats[home["id"]]["vitorias"] += 1
            times_stats[away["id"]]["derrotas"] += 1
        elif home_goals < away_goals:
            times_stats[away["id"]]["vitorias"] += 1
            times_stats[home["id"]]["derrotas"] += 1
        else:
            times_stats[home["id"]]["empates"] += 1
            times_stats[away["id"]]["empates"] += 1

    for t_id, t_stats in times_stats.items():
        jogos = t_stats["jogos_disputados"]
        t_stats["media_gols_marcados"] = round(t_stats["gols_marcados"] / jogos, 2) if jogos else 0
        t_stats["media_gols_sofridos"] = round(t_stats["gols_sofridos"] / jogos, 2) if jogos else 0

    return times_stats

# ==========================
# Função visual
# ==========================
def exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca):
    # Definir cores e ícones conforme a tendência
    if "Mais 2.5" in tendencia:
        cor = "red"
        icone = "🔥"
    elif "Menos 1.5" in tendencia:
        cor = "blue"
        icone = "❄️"
    else:
        cor = "orange"
        icone = "⚖️"

    # Obter gols com segurança
    goals = fixture.get("goals", {})
    home_goals = goals.get("home", 0)
    away_goals = goals.get("away", 0)

    col1, col2, col3 = st.columns([3,1,3])
    with col1:
        st.image(teams["home"].get("logo",""), width=50)
        st.markdown(f"### {teams['home'].get('name','Casa')}")
        st.caption(f"⚽ Média: {media_casa.get('media_gols_marcados',0):.2f} | 🛡️ Sofridos: {media_casa.get('media_gols_sofridos',0):.2f}")

    with col2:
        st.markdown(
            f"<div style='text-align:center; color:{cor}; font-size:18px;'>"
            f"<b>{icone} {tendencia}</b><br>Estimativa: {estimativa:.2f}<br>Confiança: {confianca:.0f}%</div>",
            unsafe_allow_html=True
        )
        st.caption(f"⚽ Placar Atual: {home_goals} x {away_goals}")
        st.caption(f"📍 {fixture.get('venue', {}).get('name','Desconhecido')}\n{fixture.get('date','')[:16].replace('T',' ')}")
        st.caption(f"🏟️ Liga: {league.get('name','Desconhecida')}\nStatus: {fixture.get('status',{}).get('long','Desconhecido')}")

    with col3:
        st.image(teams["away"].get("logo",""), width=50)
        st.markdown(f"### {teams['away'].get('name','Fora')}")
        st.caption(f"⚽ Média: {media_fora.get('media_gols_marcados',0):.2f} | 🛡️ Sofridos: {media_fora.get('media_gols_sofridos',0):.2f}")

    st.divider()


# ==========================
# Interface principal
# ==========================
ligas = get_ligas()
if ligas:
    df_ligas = pd.DataFrame(ligas)
    liga_escolhida = st.selectbox(
        "Escolha uma liga:",
        options=df_ligas["nome"].unique()
    )
    liga_id = df_ligas[df_ligas["nome"] == liga_escolhida]["id"].values[0]
    temporada_escolhida = st.number_input("Escolha a temporada da liga:", min_value=2000, max_value=datetime.today().year, value=datetime.today().year, step=1)
    data_selecionada = st.date_input("Escolha a data:", value=datetime.today())
    data_formatada = data_selecionada.strftime("%Y-%m-%d")

    if st.button("Buscar Jogos"):
        st.info("⏳ Buscando jogos finalizados da liga e calculando estatísticas...")
        times_stats = buscar_estatisticas_liga(liga_id, temporada_escolhida)

        url = f"{BASE_URL}/fixtures?date={data_formatada}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()["response"]
            if data:
                data_filtrada = [j for j in data if j["league"]["id"] == int(liga_id)]
                if data_filtrada:
                    for j in data_filtrada:
                        fixture = j["fixture"]
                        league = j["league"]
                        teams = j["teams"]

                        media_casa = times_stats.get(teams["home"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})
                        media_fora = times_stats.get(teams["away"]["id"], {"media_gols_marcados":0,"media_gols_sofridos":0})

                        estimativa = media_casa["media_gols_marcados"] + media_fora["media_gols_marcados"]
                        confianca = 50 + abs(estimativa - 2) * 20  # Simples para exemplo
                        if estimativa >= 2.5:
                            tendencia = "Mais 2.5"
                        elif estimativa <= 1.5:
                            tendencia = "Menos 1.5"
                        else:
                            tendencia = "Equilibrado"

                        exibir_jogo_card(fixture, league, teams, media_casa, media_fora, estimativa, tendencia, confianca)

                        # Envio de alerta Telegram
                        if confianca >= 60 and tendencia in ["Mais 2.5", "Menos 1.5"]:
                            verificar_e_atualizar_alerta(fixture, tendencia, confianca, estimativa)
                else:
                    st.warning("⚠️ Não há jogos dessa liga na data selecionada.")
            else:
                st.info("ℹ️ Nenhum jogo encontrado para essa data.")
        else:
            st.error(f"Erro {response.status_code}: {response.text}")
