import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import json
import os

# ===============================
# ⚙️ Configurações gerais
# ===============================
st.set_page_config(page_title="⚽ API MLS - Elite", layout="wide")
st.title("⚽ API MLS - Elite Master")

DATA_FILE = "mls_cache.json"
UPDATE_INTERVAL_MINUTES = 15

# ===============================
# 🧩 Função: ESPN API oculta
# ===============================
def buscar_dados_api():
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        partidas = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            status = competition.get("status", {}).get("type", {}).get("description", "")
            horario = competition.get("date", "")[:19].replace("T", " ")

            teams = competition.get("competitors", [])
            mandante = visitante = placar_m = placar_v = ""

            for team in teams:
                if team.get("homeAway") == "home":
                    mandante = team.get("team", {}).get("shortDisplayName", "")
                    placar_m = team.get("score", "-")
                else:
                    visitante = team.get("team", {}).get("shortDisplayName", "")
                    placar_v = team.get("score", "-")

            partidas.append({
                "mandante": mandante,
                "visitante": visitante,
                "placar_m": placar_m,
                "placar_v": placar_v,
                "status": status,
                "horário": horario
            })
        return partidas
    except Exception as e:
        print("Erro API ESPN:", e)
        return None

# ===============================
# 🧩 Função: Fallback via Scraping
# ===============================
def buscar_dados_scraping():
    try:
        url = "https://www.espn.com/soccer/scoreboard/_/league/usa.1"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        partidas = []
        blocos = soup.select("section.Scoreboard")

        for bloco in blocos:
            equipes = bloco.select("span.sb-team-short")
            if len(equipes) < 2:
                continue

            mandante = equipes[0].text.strip()
            visitante = equipes[1].text.strip()

            placares = bloco.select("span.sb-team-score")
            placar_m = placares[0].text.strip() if len(placares) >= 1 else "-"
            placar_v = placares[1].text.strip() if len(placares) >= 2 else "-"

            status_elem = bloco.select_one("span.sb-status-text")
            status = status_elem.text.strip() if status_elem else "Agendado"

            hora_elem = bloco.select_one("span.sb-date-time")
            horario = hora_elem.text.strip() if hora_elem else "-"

            partidas.append({
                "mandante": mandante,
                "visitante": visitante,
                "placar_m": placar_m,
                "placar_v": placar_v,
                "status": status,
                "horário": horario
            })

        return partidas if partidas else None
    except Exception as e:
        print("Erro scraping ESPN:", e)
        return None

# ===============================
# 💾 Funções auxiliares
# ===============================
def salvar_cache(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_cache():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ===============================
# 🔁 Atualização automática
# ===============================
if "last_update" not in st.session_state:
    st.session_state["last_update"] = None
if "dados" not in st.session_state:
    st.session_state["dados"] = carregar_cache()

now = datetime.now()
if (
    st.session_state["last_update"] is None
    or (now - st.session_state["last_update"]) > timedelta(minutes=UPDATE_INTERVAL_MINUTES)
):
    dados = buscar_dados_api()
    if not dados:
        dados = buscar_dados_scraping()
    if dados:
        salvar_cache(dados)
        st.session_state["dados"] = dados
        st.session_state["last_update"] = now
    else:
        st.warning("⚠️ Nenhum dado obtido — verifique se há partidas hoje.")

# ===============================
# 🌐 Endpoint JSON (/api/mls)
# ===============================
params = st.query_params
if "endpoint" in params and params["endpoint"][0].lower() == "mls":
    st.json(st.session_state["dados"])
    st.stop()

# ===============================
# 📊 Interface visual
# ===============================
ultima = (
    st.session_state["last_update"].strftime("%d/%m/%Y %H:%M:%S")
    if st.session_state["last_update"]
    else "Nunca"
)
st.markdown(f"🕒 **Última atualização:** {ultima} | Atualização automática a cada {UPDATE_INTERVAL_MINUTES} minutos.")

dados = st.session_state["dados"]

if not dados:
    st.warning("Nenhum dado disponível no momento.")
else:
    df = pd.DataFrame(dados)
    st.dataframe(df, use_container_width=True)

# ===============================
# 🔘 Botão de atualização manual
# ===============================
if st.button("🔄 Atualizar agora"):
    dados = buscar_dados_api() or buscar_dados_scraping()
    if dados:
        salvar_cache(dados)
        st.session_state["dados"] = dados
        st.session_state["last_update"] = datetime.now()
        st.rerun()
