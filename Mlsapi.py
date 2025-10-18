import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")

DATA_FILE = "data/mls.json"
UPDATE_INTERVAL = 15  # minutos
os.makedirs("data", exist_ok=True)

# ==========================================
# Função para buscar dados via sportapi.mlssoccer.com
# ==========================================
def fetch_mls_data():
    url = "https://sportapi.mlssoccer.com/api/matches"
    params = {
        "culture": "en-us",
        "competition": "98",          # código da competição MLS (regular)
        "matchType": "Regular",       # tipo de jogo regular
        # você pode definir um range de datas, por exemplo:
        # "dateFrom": "2025-10-01",
        # "dateTo": "2025-12-31"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        matches = []
        for m in data.get("matches", []):
            home = m.get("home", {}).get("fullName")
            away = m.get("away", {}).get("fullName")
            date = m.get("date")  # por exemplo, "2025-10-18T21:00:00Z"
            status = m.get("status", {}).get("name") if m.get("status") else None

            hs = m.get("home", {}).get("score")
            as_ = m.get("away", {}).get("score")

            score = f"{hs} - {as_}" if hs is not None and as_ is not None else "vs"

            matches.append({
                "datetime": date,
                "mandante": home,
                "visitante": away,
                "placar": score,
                "status": status
            })

        # salvar localmente
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)

        return matches
    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS (sportapi): {e}")
        return []

def load_local_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Controle de atualização
if "last_update" not in st.session_state:
    st.session_state.last_update = None

now = datetime.now()
if st.session_state.last_update is None or (now - st.session_state.last_update) > timedelta(minutes=UPDATE_INTERVAL):
    matches = fetch_mls_data()
    st.session_state.last_update = now
else:
    matches = load_local_data()

# Verifica se o modo API JSON foi solicitado
params = st.query_params
if "endpoint" in params and params["endpoint"].lower() == "mls":
    st.json(matches)
    st.stop()

# Interface visual
st.title("⚽ API MLS - Elite Master")
if st.session_state.last_update:
    st.caption(f"🕒 Última atualização: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')} | atualização automática a cada {UPDATE_INTERVAL} minutos")
else:
    st.caption("🕒 Ainda não atualizado")

if not matches:
    st.warning("Nenhum dado disponível. Tentando buscar via API interna...")
else:
    for g in matches:
        dt = g.get("datetime", "")
        # opcional: separar data e hora
        st.markdown(f"**{g['mandante']}** vs **{g['visitante']}** — {dt} | {g['placar']} | {g['status']}")

# botao manual
if st.button("🔄 Atualizar agora"):
    _ = fetch_mls_data()
