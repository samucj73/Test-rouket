import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações e Segurança
# =============================
API_KEY = os.getenv("FOOTBALL_API_KEY", "9058de85e3324bdb969adc005b5d918a")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

HEADERS = {"X-Auth-Token": API_KEY}
BASE_URL_FD = "https://api.football-data.org/v4"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Constantes
ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"
CACHE_TIMEOUT = 3600  # 1 hora
DIAS_PASSADOS = 3
DIAS_FUTUROS = 2

# =============================
# Ligas disponíveis
# =============================
LIGA_DICT = {
    "FIFA World Cup": "WC",
    "UEFA Champions League": "CL", 
    "Bundesliga": "BL1",
    "Eredivisie": "DED",
    "Campeonato Brasileiro Série A": "BSA",
    "Primera Division": "PD",
    "Ligue 1": "FL1",
    "Championship (Inglaterra)": "ELC",
    "Primeira Liga (Portugal)": "PPL",
    "European Championship": "EC",
    "Serie A (Itália)": "SA",
    "Premier League (Inglaterra)": "PL"
}

# =============================
# Cache e JSON
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            return dados
    except:
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except:
        pass

def carregar_cache_jogos(): return carregar_json(CACHE_JOGOS)
def salvar_cache_jogos(dados): salvar_json(CACHE_JOGOS, dados)
def carregar_cache_classificacao(): return carregar_json(CACHE_CLASSIFICACAO)
def salvar_cache_classificacao(dados): salvar_json(CACHE_CLASSIFICACAO, dados)
def carregar_alertas(): return carregar_json(ALERTAS_PATH)
def salvar_alertas(alertas): salvar_json(ALERTAS_PATH, alertas)

# =============================
# Comunicação API
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        response = requests.get(
            BASE_URL_TG, 
            params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

def obter_dados_api(url: str) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except:
        return None

def obter_classificacao(liga_id: str) -> dict:
    cache = carregar_cache_classificacao()
    if liga_id in cache:
        return cache[liga_id]

    url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
    data = obter_dados_api(url)
    if not data: return {}

    standings = {}
    for s in data.get("standings", []):
        if s["type"] != "TOTAL": continue
        for t in s["table"]:
            standings[t["team"]["name"]] = {
                "scored": t.get("goalsFor", 0),
                "against": t.get("goalsAgainst", 0),
                "played": t.get("playedGames", 1)
            }
    cache[liga_id] = standings
    salvar_cache_classificacao(cache)
    return standings

def obter_jogos(liga_id: str, data_selecionada: datetime) -> list:
    """Busca jogos passados/futuros da liga."""
    cache = carregar_cache_jogos()
    jogos_totais = []

    datas = [
        (data_selecionada - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DIAS_PASSADOS, 0, -1)
    ] + [data_selecionada.strftime("%Y-%m-%d")] + [
        (data_selecionada + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, DIAS_FUTUROS + 1)
    ]

    for data in datas:
        key = f"{liga_id}_{data}"
        if key in cache:
            jogos = cache[key]
        else:
            url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
            data_api = obter_dados_api(url)
            jogos = data_api.get("matches", []) if data_api else []
            cache[key] = jogos

        jogos_totais.extend(jogos)

    salvar_cache_jogos(cache)
    return jogos_totais

# =============================
# Tendência de gols
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict):
    dados_home = classificacao.get(home, {"scored":0,"against":0,"played":1})
    dados_away = classificacao.get(away, {"scored":0,"against":0,"played":1})
    played_home = max(dados_home["played"],1)
    played_away = max(dados_away["played"],1)
    media_home_feitos = dados_home["scored"]/played_home
    media_home_sofridos = dados_home["against"]/played_home
    media_away_feitos = dados_away["scored"]/played_away
    media_away_sofridos = dados_away["against"]/played_away
    estimativa = ((media_home_feitos+media_away_sofridos)/2 + (media_away_feitos+media_home_sofridos)/2)
    if estimativa>=3.0:
        tendencia="Mais 2.5"; confianca=min(95,70+(estimativa-3.0)*10)
    elif estimativa>=2.0:
        tendencia="Mais 1.5"; confianca=min(90,60+(estimativa-2.0)*10)
    else:
        tendencia="Menos 2.5"; confianca=min(85,55+(2.0-estimativa)*10)
    return estimativa,confianca,tendencia

# =============================
# Alertas
# =============================
def verificar_enviar_alerta(fixture, tendencia, estimativa, confianca):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia":tendencia,"estimativa":estimativa,"confianca":confianca,"conferido":False}
        enviar_alerta_telegram(fixture,tendencia,estimativa,confianca)
        salvar_alertas(alertas)

def enviar_alerta_telegram(fixture, tendencia, estimativa, confianca):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_format = datetime.fromisoformat(fixture["utcDate"].replace("Z","+00:00")) - timedelta(hours=3)
    competicao = fixture.get("competition",{}).get("name","Desconhecido")
    msg = f"⚽ <b>Alerta de Gols!</b>\n🏟️ {home} vs {away}\n📅 {data_format.strftime('%d/%m/%Y')} ⏰ {data_format.strftime('%H:%M')} BRT\n📈 Tendência: <b>{tendencia}</b>\n🎯 Estimativa: <b>{estimativa:.2f}</b>\n💯 Confiança: <b>{confianca:.0f}%</b>\n🏆 Liga: {competicao}"
    enviar_telegram(msg)

# =============================
# Processamento e Streamlit
# =============================
def processar_jogos_streamlit(data_selecionada, todas_ligas, liga_selecionada, top_n):
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]
    st.write(f"⏳ Buscando jogos para {data_selecionada.strftime('%d/%m/%Y')}...")

    top_jogos = []
    progress_bar = st.progress(0)
    total_ligas = len(ligas_busca)

    for i, liga_id in enumerate(ligas_busca):
        classificacao = obter_classificacao(liga_id)
        jogos = obter_jogos(liga_id, data_selecionada)

        for match in jogos:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            estimativa, confianca, tendencia = calcular_tendencia(home, away, classificacao)

            verificar_enviar_alerta(match, tendencia, estimativa, confianca)

            top_jogos.append({
                "id": match["id"],
                "home": home,
                "away": away,
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3),
                "status": match.get("status", "DESCONHECIDO"),
            })

        progress_bar.progress((i + 1) / total_ligas)

    if top_jogos:
        enviar_top_jogos(top_jogos, top_n)
        st.success(f"✅ Análise concluída! {len(top_jogos)} jogos processados.")
    else:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")

def enviar_top_jogos(jogos: list, top_n: int):
    jogos_filtrados = [j for j in jogos if j["status"] not in ["FINISHED","IN_PLAY","POSTPONED","SUSPENDED"]]
    if not jogos_filtrados:
        st.warning("⚠️ Nenhum jogo elegível para o Top Jogos (todos já iniciados ou finalizados).")
        return

    top_jogos_sorted = sorted(jogos_filtrados, key=lambda x: x["confianca"], reverse=True)[:top_n]

    msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
    for j in top_jogos_sorted:
        hora_format = j["hora"].strftime("%H:%M")
        msg += (
            f"🏟️ {j['home']} vs {j['away']}\n"
            f"🕒 {hora_format} BRT | Liga: {j['liga']} | Status: {j['status']}\n"
            f"📈 Tendência: {j['tendencia']} | Estimativa: {j['estimativa']:.2f} | "
            f"💯 Confiança: {j['confianca']:.0f}%\n\n"
        )
    enviar_telegram(msg, TELEGRAM_CHAT_ID_ALT2)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Jogos no Top", [3,5,10], index=0)
        st.info("Configure as opções de análise")

    col1,col2 = st.columns([2,1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)

    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))

    if st.button("🔍 Buscar Partidas"):
        processar_jogos_streamlit(data_selecionada, todas_ligas, liga_selecionada, top_n)

if __name__ == "__main__":
    main()
