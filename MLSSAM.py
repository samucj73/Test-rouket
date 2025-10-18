import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações e Segurança
# =============================
API_BASE = "https://test-rouket-nvgsix9abxckpjrnlfz79b.streamlit.app/api/mls"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1003073115320"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

CACHE_TIMEOUT = 3600  # 1 hora
ALERTAS_PATH = "alertas.json"

# =============================
# Utilitários de Cache e JSON
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
    with open(caminho, "w", encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_alertas() -> dict:
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas: dict):
    salvar_json(ALERTAS_PATH, alertas)

# =============================
# Funções de API
# =============================
def obter_json_cru(endpoint: str) -> dict | list:
    url = f"{API_BASE}?endpoint={endpoint}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erro ao obter JSON cru do endpoint '{endpoint}': {e}")
        return {}

def listar_ligas() -> dict:
    data = obter_json_cru("ligas")
    ligas_dict = {}
    for liga in data:
        nome = liga.get("name") or liga.get("league") or liga.get("nome")
        liga_id = liga.get("id") or liga.get("code") or liga.get("leagueId")
        if nome and liga_id:
            ligas_dict[nome] = liga_id
    return ligas_dict

def obter_jogos_por_liga(liga_id: str, data: str) -> list:
    endpoint = f"jogos?liga={liga_id}&data={data}"
    data_json = obter_json_cru(endpoint)
    return data_json.get("matches", []) if isinstance(data_json, dict) else data_json

# =============================
# Tendência e Alertas
# =============================
def calcular_tendencia(home: str, away: str, home_gols: float, away_gols: float) -> tuple[float, float, str]:
    estimativa = (home_gols + away_gols) / 2
    if estimativa >= 3:
        return estimativa, min(95, 70 + (estimativa-3)*10), "Mais 2.5"
    elif estimativa >= 2:
        return estimativa, min(90, 60 + (estimativa-2)*10), "Mais 1.5"
    else:
        return estimativa, min(85, 55 + (2-estimativa)*10), "Menos 2.5"

def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        response = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return response.status_code == 200
    except:
        return False

def enviar_alerta_telegram(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    home = fixture["homeTeam"]["name"]
    away = fixture["awayTeam"]["name"]
    data_jogo = datetime.fromisoformat(fixture["utcDate"].replace("Z", "+00:00")) - timedelta(hours=3)
    status = fixture.get("status", "DESCONHECIDO")
    msg = (
        f"⚽ <b>Alerta de Gols!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_jogo.strftime('%d/%m/%Y')} ⏰ {data_jogo.strftime('%H:%M')}\n"
        f"📌 Status: {status}\n"
        f"📈 Tendência: <b>{tendencia}</b>\n"
        f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
        f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
    )
    enviar_telegram(msg)

def verificar_enviar_alerta(fixture: dict, tendencia: str, estimativa: float, confianca: float):
    alertas = carregar_alertas()
    fixture_id = str(fixture.get("id"))
    if fixture_id not in alertas:
        alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca, "conferido": False}
        enviar_alerta_telegram(fixture, tendencia, estimativa, confianca)
        salvar_alertas(alertas)

# =============================
# Interface Streamlit
# =============================
def main():
    st.set_page_config(page_title="⚽ Alerta de Gols MLS API", layout="wide")
    st.title("⚽ Sistema de Alertas Automáticos - API MLS")

    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Top N Jogos", [3,5,10], index=0)
        todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
        ligas_disponiveis = listar_ligas()
        liga_selecionada = None
        if not todas_ligas and ligas_disponiveis:
            liga_selecionada = st.selectbox("📌 Liga específica", list(ligas_disponiveis.keys()))
        data_selecionada = st.date_input("📅 Data para análise:", datetime.today())

    if st.button("🔍 Buscar Jogos"):
        ligas_busca = ligas_disponiveis.values() if todas_ligas else [ligas_disponiveis[liga_selecionada]]
        top_jogos = []
        for liga_id in ligas_busca:
            jogos = obter_jogos_por_liga(liga_id, data_selecionada.strftime("%Y-%m-%d"))
            for match in jogos:
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                home_gols = match.get("homeGoals", 1) or 1
                away_gols = match.get("awayGoals", 1) or 1
                estimativa, confianca, tendencia = calcular_tendencia(home, away, home_gols, away_gols)
                verificar_enviar_alerta(match, tendencia, estimativa, confianca)
                top_jogos.append({"home": home, "away": away, "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca})
        st.success(f"✅ {len(top_jogos)} jogos processados!")
        st.table(pd.DataFrame(top_jogos))

    # Aba JSON cru
    st.header("📦 JSON cru da API")
    endpoint_debug = st.text_input("Digite o endpoint", value="ligas")
    if st.button("🔎 Obter JSON cru"):
        st.json(obter_json_cru(endpoint_debug))

if __name__ == "__main__":
    main()
