import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta

# Configurações iniciais
st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")
st.title("⚽ API MLS - Elite Master")

DATA_FILE = "mls.json"
UPDATE_INTERVAL_MINUTES = 15
os.makedirs(".", exist_ok=True)

# Função para raspar a página da ESPN MLS
def fetch_espn_mls():
    url = "https://www.espn.com/soccer/scoreboard/_/league/usa.1"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    matches = []

    # Cada bloco de partida está dentro de <section class="Scoreboard"> — verificar estrutura real
    for bloco in soup.select("section.Scoreboard"):
        try:
            equipes = bloco.select("span.sb-team-short")
            if len(equipes) < 2:
                continue
            mandante = equipes[0].text.strip()
            visitante = equipes[1].text.strip()

            placares = bloco.select("span.sb-team-score")
            if len(placares) >= 2:
                placar_m = placares[0].text.strip()
                placar_v = placares[1].text.strip()
                placar = f"{placar_m} - {placar_v}"
            else:
                placar = "vs"

            status_elem = bloco.select_one("span.sb-status-text")
            status = status_elem.text.strip() if status_elem else "Agendado"

            hora_elem = bloco.select_one("span.sb-date-time")
            horario = hora_elem.text.strip() if hora_elem else ""

            matches.append({
                "mandante": mandante,
                "visitante": visitante,
                "horario": horario,
                "placar": placar,
                "status": status
            })
        except Exception as e:
            # Em caso de falha num bloco, ignorar e continuar
            print("Erro num bloco:", e)
            continue

    # Salvar local para reutilização
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    return matches

# Função para carregar dados salvos
def load_local():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Controle de atualização automática
if "last_update" not in st.session_state:
    st.session_state["last_update"] = None
if "matches" not in st.session_state:
    st.session_state["matches"] = []

now = datetime.now()
if (
    st.session_state["last_update"] is None
    or (now - st.session_state["last_update"]) > timedelta(minutes=UPDATE_INTERVAL_MINUTES)
):
    try:
        st.session_state["matches"] = fetch_espn_mls()
        st.session_state["last_update"] = now
    except Exception as e:
        st.error(f"Erro ao buscar dados da MLS (ESPN): {e}")
        # fallback para dados locais
        st.session_state["matches"] = load_local()
else:
    # usar dados locais
    st.session_state["matches"] = load_local()

# Modo API JSON via query param
params = st.query_params
if "endpoint" in params and params["endpoint"][0].lower() == "mls":
    st.json(st.session_state["matches"])
    st.stop()

# Interface visual
st.caption(f"🕒 Última atualização: {st.session_state['last_update'].strftime('%d/%m/%Y %H:%M:%S')} | Atualização a cada {UPDATE_INTERVAL_MINUTES} min")

if not st.session_state["matches"]:
    st.warning("Nenhum dado disponível. Aguarde a próxima atualização.")
else:
    for m in st.session_state["matches"]:
        st.markdown(f"**{m['mandante']}** vs **{m['visitante']}** — {m['horario']} | {m['placar']} | {m['status']}")

# Botão opcional de atualização manual
if st.button("🔄 Atualizar agora"):
    try:
        st.session_state["matches"] = fetch_espn_mls()
        st.session_state["last_update"] = datetime.now()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
