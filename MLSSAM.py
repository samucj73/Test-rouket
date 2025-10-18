import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import os
import json

# =============================
# ⚙️ Configurações
# =============================
API_BASE = "https://test-rouket-nvgsix9abxckpjrnlfz79b.streamlit.app"
ALERTAS_PATH = "alertas.json"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# =============================
# 🌐 Comunicação API
# =============================
def obter_dados(endpoint, params={}):
    try:
        url = f"{API_BASE}/?endpoint={endpoint}"
        for k, v in params.items():
            url += f"&{k}={v}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception as e:
        st.error(f"Erro ao buscar {endpoint}: {e}")
        return []

def enviar_telegram(msg: str, chat_id=TELEGRAM_CHAT_ID):
    try:
        r = requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200
    except:
        return False

# =============================
# ⚠️ Alertas Telegram
# =============================
def carregar_alertas():
    if os.path.exists(ALERTAS_PATH):
        with open(ALERTAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_alertas(alertas):
    with open(ALERTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

def calcular_tendencia(home, away, partidas_historicas):
    home_matches = [m for m in partidas_historicas if m["mandante"] == home or m["visitante"] == home]
    away_matches = [m for m in partidas_historicas if m["mandante"] == away or m["visitante"] == away]

    gols_home = sum([int(m["placar_m"]) if m["mandante"] == home else int(m["placar_v"]) 
                     for m in home_matches if m["placar_m"].isdigit() and m["placar_v"].isdigit()])
    gols_home_sofridos = sum([int(m["placar_v"]) if m["mandante"] == home else int(m["placar_m"]) 
                              for m in home_matches if m["placar_m"].isdigit() and m["placar_v"].isdigit()])
    jogos_home = max(len(home_matches),1)

    gols_away = sum([int(m["placar_m"]) if m["mandante"] == away else int(m["placar_v"]) 
                     for m in away_matches if m["placar_m"].isdigit() and m["placar_v"].isdigit()])
    gols_away_sofridos = sum([int(m["placar_v"]) if m["mandante"] == away else int(m["placar_m"]) 
                              for m in away_matches if m["placar_m"].isdigit() and m["placar_v"].isdigit()])
    jogos_away = max(len(away_matches),1)

    media_home = gols_home / jogos_home
    media_away_sofridos = gols_away_sofridos / jogos_away
    media_away = gols_away / jogos_away
    media_home_sofridos = gols_home_sofridos / jogos_home

    estimativa = (media_home + media_away_sofridos + media_away + media_home_sofridos)/2

    if estimativa >= 3:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa-3)*10)
    elif estimativa >= 2:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa-2)*10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2-estimativa)*10)
    return estimativa, confianca, tendencia

def verificar_enviar_alerta(match, partidas_historicas):
    alertas = carregar_alertas()
    fixture_id = f"{match['liga']}_{match['mandante']}_{match['visitante']}_{match['horario']}"
    if fixture_id not in alertas:
        estimativa, confianca, tendencia = calcular_tendencia(match["mandante"], match["visitante"], partidas_historicas)
        msg = (
            f"⚽ <b>Alerta!</b>\n"
            f"🏟️ {match['mandante']} vs {match['visitante']}\n"
            f"🕒 {match['horario']}\n"
            f"📈 Tendência: <b>{tendencia}</b>\n"
            f"🎯 Estimativa: <b>{estimativa:.2f} gols</b>\n"
            f"💯 Confiança: <b>{confianca:.0f}%</b>\n"
            f"🏆 Liga: {match['liga']}"
        )
        enviar_telegram(msg)
        alertas[fixture_id] = {"tendencia": tendencia, "conferido": False}
        salvar_alertas(alertas)

# =============================
# 🖥️ Streamlit Interface
# =============================
st.set_page_config(page_title="⚽ Alertas Nova API", layout="wide")
st.title("⚽ Sistema de Alertas Automáticos (API Online)")

# Sidebar
ligas_disponiveis = obter_dados("leagues")
selected_ligas = st.sidebar.multiselect("Selecione Ligas:", options=ligas_disponiveis, default=ligas_disponiveis)
data_selecionada = st.sidebar.date_input("Filtrar por data:", value=datetime.utcnow().date())

# Carregar partidas diretamente da API
partidas = []
for liga in selected_ligas:
    partidas_liga = obter_dados("matches", {"liga": liga, "data": data_selecionada.strftime("%Y-%m-%d")})
    partidas.extend(partidas_liga)

partidas_df = pd.DataFrame(partidas)

if not partidas_df.empty:
    for idx, row in partidas_df.iterrows():
        st.markdown(f"### {row['mandante']} vs {row['visitante']}")
        logos = [row.get('mandante_logo'), row.get('visitante_logo')]
        captions = [row.get('mandante'), row.get('visitante')]
        st.image([l for l in logos if l], width=80, caption=captions[:len([l for l in logos if l])])
        st.markdown(f"**Placar:** {row.get('placar_m','-')} x {row.get('placar_v','-')} | **Status:** {row.get('status','')}")
        verificar_enviar_alerta(row, partidas)
        st.markdown("---")
else:
    st.warning("Nenhuma partida disponível para os filtros selecionados.")
