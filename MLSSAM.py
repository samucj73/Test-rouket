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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")

BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BASE_URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora em segundos

# =============================
# Dicionário de Ligas ESPN
# =============================
LIGA_DICT = {
    "Premier League (Inglaterra)": "eng.1",
    "Championship (Inglaterra)": "eng.2",
    "Bundesliga": "ger.1",
    "2. Bundesliga": "ger.2",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Ligue 1": "fra.1",
    "Eredivisie": "ned.1",
    "MLS": "usa.1",
    "FIFA World Cup": "fifa.world",
    "UEFA Champions League": "uefa.champions"
}

# =============================
# Utilitários de Cache
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            
            if caminho == CACHE_JOGOS:
                agora = datetime.now().timestamp()
                for key in list(dados.keys()):
                    if '_timestamp' in dados[key] and agora - dados[key]['_timestamp'] > CACHE_TIMEOUT:
                        del dados[key]
            return dados
    except (json.JSONDecodeError, IOError) as e:
        st.error(f"Erro ao carregar {caminho}: {e}")
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        if caminho == CACHE_JOGOS:
            for key in dados.keys():
                if key != "_timestamp":
                    dados[key]['_timestamp'] = datetime.now().timestamp()
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except IOError as e:
        st.error(f"Erro ao salvar {caminho}: {e}")

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Utilitários de Data e Nome
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except ValueError:
        return "Data inválida", "Hora inválida"

def abreviar_nome(nome: str, max_len: int = 15) -> str:
    if len(nome) <= max_len:
        return nome
    palavras = nome.split()
    abreviado = " ".join([p[0] + "." if len(p) > 2 else p for p in palavras])
    return abreviado[:max_len-3] + "..." if len(abreviado) > max_len else abreviado

# =============================
# Comunicação com APIs
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        response = requests.get(
            BASE_URL_TG, 
            params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return response.status_code == 200
    except requests.RequestException as e:
        st.error(f"Erro ao enviar para Telegram: {e}")
        return False

def obter_jogos_espn(liga_slug: str, data: str) -> list:
    """Obtém jogos do dia da ESPN (scoreboard)."""
    cache = carregar_cache_jogos()
    key = f"{liga_slug}_{data}"
    if key in cache:
        return cache[key]["matches"]

    url = f"{BASE_URL_ESPN}/{liga_slug}/scoreboard?dates={data.replace('-', '')}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data_json = resp.json()
        partidas = data_json.get("events", [])
        jogos = []
        for p in partidas:
            jogos.append({
                "id": p["id"],
                "homeTeam": {"name": p["competitions"][0]["competitors"][0]["team"]["displayName"]},
                "awayTeam": {"name": p["competitions"][0]["competitors"][1]["team"]["displayName"]},
                "utcDate": p["date"],
                "status": p["status"]["type"]["name"],
                "competition": {"name": p.get("league", {}).get("name", liga_slug)},
                "score": p.get("competitions")[0].get("score", {"fullTime": {"home": None, "away": None}})
            })
        cache[key] = {"matches": jogos, "_timestamp": datetime.now().timestamp()}
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Lógica de tendência e alertas (mantida)
# =============================
def calcular_tendencia(home: str, away: str, classificacao: dict = None) -> tuple[float, float, str]:
    """Calcula tendência simulada (média simples de 1.5 a 3 gols por partida)."""
    estimativa = 2.2  # valor médio base
    confianca = 70
    tendencia = "Mais 1.5"
    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = 85
    elif estimativa < 1.5:
        tendencia = "Menos 2.5"
        confianca = 65
    return estimativa, confianca, tendencia

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_formatada, hora_formatada = formatar_data_iso(fixture["utcDate"])
    competicao = fixture.get("competition", {}).get("name", "Desconhecido")
    status = fixture.get("status", "DESCONHECIDO")
    gols_home = fixture.get("score", {}).get("fullTime", {}).get("home")
    gols_away = fixture.get("score", {}).get("fullTime", {}).get("away")
    placar = f"{gols_home} x {gols_away}" if gols_home is not None and gols_away is not None else None
    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada} (BRT)\n"
        f"📌 Status: {status}\n"
    )
    if placar:
        msg += f"📊 Placar: <b>{placar}</b>\n"
    msg += (
        f"📈 Tendência: <b>{tendencia}</b>\n"
        f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
        f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
        f"🏆 Liga: {competicao}"
    )
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    alertas = carregar_alertas()
    fixture_id = str(fixture["id"])
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols ESPN", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos de Gols - ESPN")

    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Jogos no Top", [3,5,10], index=0)

    col1, col2 = st.columns([2,1])
    with col1:
        data_selecionada = st.date_input("📅 Data para análise:", value=datetime.today())
    with col2:
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
    
    liga_selecionada = None
    if not todas_ligas:
        liga_selecionada = st.selectbox("📌 Liga específica:", list(LIGA_DICT.keys()))
    
    if st.button("🔍 Buscar Partidas", type="primary"):
        processar_jogos_espn(data_selecionada, todas_ligas, liga_selecionada, top_n)

def processar_jogos_espn(data_selecionada, todas_ligas, liga_selecionada, top_n):
    hoje = data_selecionada.strftime("%Y-%m-%d")
    ligas_busca = LIGA_DICT.values() if todas_ligas else [LIGA_DICT[liga_selecionada]]

    st.write(f"⏳ Buscando jogos para {hoje}...")
    top_jogos = []

    for liga_slug in ligas_busca:
        jogos = obter_jogos_espn(liga_slug, hoje)
        for match in jogos:
            estimativa, confianca, tendencia = calcular_tendencia(
                match["homeTeam"]["name"], match["awayTeam"]["name"]
            )
            verificar_enviar_alerta(match, tendencia, estimativa, confianca)
            top_jogos.append({
                "id": match["id"],
                "home": match["homeTeam"]["name"],
                "away": match["awayTeam"]["name"],
                "tendencia": tendencia,
                "estimativa": estimativa,
                "confianca": confianca,
                "liga": match.get("competition", {}).get("name", "Desconhecido"),
                "hora": datetime.fromisoformat(match["utcDate"].replace("Z","+00:00")) - timedelta(hours=3),
                "status": match.get("status", "DESCONHECIDO")
            })
    if top_jogos:
        st.success(f"✅ {len(top_jogos)} jogos processados e alertas enviados!")
    else:
        st.warning("⚠️ Nenhum jogo encontrado.")

if __name__ == "__main__":
    main()
