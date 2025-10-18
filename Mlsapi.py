import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")

# ======================================================
# CONFIGURAÇÕES
# ======================================================
API_URL = "https://www.mlssoccer.com/api/v1/schedule?season=2025&competition=mls-regular-season"
DATA_FILE = "data/mls.json"
UPDATE_INTERVAL = 15  # minutos
os.makedirs("data", exist_ok=True)


# ======================================================
# FUNÇÃO: Buscar dados da API MLS
# ======================================================
def fetch_mls_data():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()

        matches = []
        for game in data.get("matches", []):
            try:
                date_time = game.get("date", "")
                home_team = game["home"]["name"]
                away_team = game["away"]["name"]
                status = game.get("status", {}).get("display", "Agendado")

                home_score = game.get("home", {}).get("score", None)
                away_score = game.get("away", {}).get("score", None)

                score = f"{home_score} - {away_score}" if home_score is not None else "vs"

                matches.append({
                    "data": date_time[:10],
                    "hora": date_time[11:16],
                    "mandante": home_team,
                    "visitante": away_team,
                    "placar": score,
                    "status": status
                })
            except Exception:
                continue

        # Salvar localmente
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)

        return matches
    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS: {e}")
        return []


# ======================================================
# FUNÇÃO: Ler dados salvos
# ======================================================
def load_local_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ======================================================
# CONTROLE DE ATUALIZAÇÃO AUTOMÁTICA
# ======================================================
if "last_update" not in st.session_state:
    st.session_state.last_update = None

now = datetime.now()
if (
    st.session_state.last_update is None
    or (now - st.session_state.last_update) > timedelta(minutes=UPDATE_INTERVAL)
):
    matches = fetch_mls_data()
    st.session_state.last_update = now
else:
    matches = load_local_data()


# ======================================================
# INTERFACE
# ======================================================
st.title("⚽ API MLS - Elite Master")
st.caption(f"🕒 Última atualização: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')} | Atualização automática a cada {UPDATE_INTERVAL} minutos")

if not matches:
    st.warning("Nenhum dado disponível. Aguarde a atualização automática.")
else:
    for game in matches:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
        with col1:
            st.write(f"🏟️ **{game['mandante']}**")
        with col2:
            st.write(f"🆚 **{game['visitante']}**")
        with col3:
            st.write(f"⏰ {game['hora']}")
        with col4:
            st.write(f"📊 {game['placar']} | {game['status']}")

# Atualização automática no Streamlit Cloud
st_autorefresh = st.empty()
st_autorefresh.write(
    f"<script>setTimeout(function() {{ window.location.reload(); }}, {UPDATE_INTERVAL * 60000});</script>",
    unsafe_allow_html=True,
)
