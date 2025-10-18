import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os

st.set_page_config(page_title="⚽ API MLS - Elite Master", layout="wide")
st.title("⚽ API MLS - Elite Master")

DATA_FILE = "mls_cache.json"
UPDATE_INTERVAL_MINUTES = 15
DIAS_PASSADOS = 3
DIAS_FUTUROS = 2

# ===============================
# 🔗 Função para buscar dados da ESPN por data
# ===============================
def buscar_dados_por_data(data_str):
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates={data_str}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        partidas = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            status = competition.get("status", {}).get("type", {}).get("description", "")
            horario_utc = competition.get("date", "")
            horario_local = (
                datetime.fromisoformat(horario_utc.replace("Z", "+00:00"))
                - timedelta(hours=3)
            ).strftime("%d/%m/%Y %H:%M")

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
                "horário": horario_local
            })
        return partidas
    except Exception as e:
        print(f"Erro ao buscar dados da data {data_str}: {e}")
        return []

# ===============================
# 🧠 Buscar dados de várias datas
# ===============================
def buscar_todas_as_partidas():
    hoje = datetime.utcnow().date()
    datas = [
        (hoje - timedelta(days=i)).strftime("%Y%m%d") for i in range(DIAS_PASSADOS, 0, -1)
    ] + [hoje.strftime("%Y%m%d")] + [
        (hoje + timedelta(days=i)).strftime("%Y%m%d") for i in range(1, DIAS_FUTUROS + 1)
    ]

    todas = []
    for d in datas:
        todas.extend(buscar_dados_por_data(d))
    return todas

# ===============================
# 💾 Cache local
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
    dados = buscar_todas_as_partidas()
    if dados:
        salvar_cache(dados)
        st.session_state["dados"] = dados
        st.session_state["last_update"] = now
    else:
        st.warning("⚠️ Nenhum dado obtido — verifique se há partidas disponíveis.")

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

dados = pd.DataFrame(st.session_state["dados"])

if dados.empty:
    st.warning("Nenhum dado disponível no momento.")
else:
    # Colorir status
    def colorir_status(val):
        if "Final" in val:
            return "background-color: #d4edda"
        elif "Live" in val:
            return "background-color: #fff3cd"
        else:
            return ""
    st.dataframe(dados.style.applymap(colorir_status, subset=["status"]), use_container_width=True)

# ===============================
# 🔘 Atualização manual
# ===============================
if st.button("🔄 Atualizar agora"):
    dados = buscar_todas_as_partidas()
    if dados:
        salvar_cache(dados)
        st.session_state["dados"] = dados
        st.session_state["last_update"] = datetime.now()
        st.rerun()
