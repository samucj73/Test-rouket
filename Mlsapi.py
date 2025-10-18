# mls_app_streamlit.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import time

# =============================
# Configuração inicial
# =============================
st.set_page_config(page_title="API MLS - Elite Master", layout="wide")
DATA_FILE = "mls.json"
UPDATE_INTERVAL_MINUTES = 15  # Atualização automática

# =============================
# Função de raspagem do site oficial da MLS
# =============================
def get_mls_matches():
    url = "https://www.mlssoccer.com/competitions/mls-regular-season/2025/schedule/week-with-matches"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    matches = []
    for game in soup.select("div.match-list__match"):
        try:
            date = game.select_one("span.match-list__date").text.strip() if game.select_one("span.match-list__date") else ""
            home = game.select_one("div.match-list__team--home").text.strip() if game.select_one("div.match-list__team--home") else ""
            away = game.select_one("div.match-list__team--away").text.strip() if game.select_one("div.match-list__team--away") else ""
            score_elem = game.select_one("span.match-list__score")
            score = score_elem.text.strip() if score_elem else "vs"
            status_elem = game.select_one("span.match-list__status")
            status = status_elem.text.strip() if status_elem else "Agendado"

            matches.append({
                "data": date,
                "mandante": home,
                "visitante": away,
                "placar": score,
                "status": status
            })
        except Exception as e:
            print("Erro ao ler jogo:", e)

    return matches

# =============================
# Funções auxiliares
# =============================
def save_matches(matches):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

def load_matches():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def update_data():
    st.toast("Atualizando dados da MLS...", icon="⏳")
    matches = get_mls_matches()
    save_matches(matches)
    st.toast(f"{len(matches)} partidas atualizadas com sucesso!", icon="✅")
    st.session_state["last_update"] = datetime.now()
    return matches

# =============================
# Controle automático de atualização
# =============================
if "last_update" not in st.session_state:
    st.session_state["last_update"] = datetime.min

elapsed = datetime.now() - st.session_state["last_update"]
if elapsed > timedelta(minutes=UPDATE_INTERVAL_MINUTES):
    update_data()

# =============================
# Endpoint da API JSON via URL
# =============================
params = st.experimental_get_query_params()
if "endpoint" in params and params["endpoint"][0].lower() == "mls":
    matches = load_matches()
    st.json(matches)
    st.stop()

# =============================
# Interface visual (painel)
# =============================
st.title("⚽ API MLS - Elite Master")
st.markdown("Sistema de coleta automática dos dados oficiais da MLS direto da nuvem 🌎")

last_update = st.session_state["last_update"].strftime("%d/%m/%Y %H:%M:%S")
st.info(f"🕒 Última atualização: {last_update} | Atualiza automaticamente a cada 15 minutos")

# Botão manual opcional
if st.button("🔄 Atualizar agora"):
    update_data()

# Exibe partidas salvas
matches = load_matches()
if matches:
    st.subheader("📅 Partidas MLS - Semana Atual")
    for match in matches:
        st.markdown(f"""
        🏟️ **{match['mandante']}** vs **{match['visitante']}**  
        📅 {match['data']} | ⚽ {match['placar']} | 📊 Status: {match['status']}
        ---
        """)
else:
    st.warning("Nenhum dado disponível. Aguarde a atualização automática.")

st.markdown("---")
st.caption("Desenvolvido por Elite Master ⚙️ | Dados oficiais da MLS (mlssoccer.com)")
