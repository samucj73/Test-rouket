import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# ===============================
# ⚙️ Configurações gerais
# ===============================
st.set_page_config(page_title="⚽ Soccer API - Elite Master", layout="wide")
st.title("⚽ Soccer API - Elite Master")

CACHE_DIR = "cache"
DIAS_FUTUROS = 2
DIAS_PASSADOS = 7
ANOS_HISTORICOS = range(2005, datetime.utcnow().year + 1)

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# ===============================
# 🔗 Principais ligas
# ===============================
LIGAS = {
    "MLS (EUA)": "usa.1",
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Primeira Liga (Portugal)": "por.1",
    "Brasileirão Série A": "bra.1",
    "Argentinian Primera División": "arg.1",
    "Campeonato Chileno": "chi.1",
    "Campeonato Colombiano": "col.1",
}

# ===============================
# 💾 Funções de cache
# ===============================
def cache_file(liga_code, ano):
    return os.path.join(CACHE_DIR, f"{liga_code}_{ano}.json")

def salvar_cache(liga_code, ano, dados):
    with open(cache_file(liga_code, ano), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_cache(liga_code, ano):
    if os.path.exists(cache_file(liga_code, ano)):
        with open(cache_file(liga_code, ano), "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ===============================
# 🧠 Buscar dados da ESPN com escudos
# ===============================
def buscar_dados(liga_code, data_str):
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_code}/scoreboard?dates={data_str}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        partidas = []

        for event in data.get("events", []):
            comp = event.get("competitions", [{}])[0]
            status = comp.get("status", {}).get("type", {}).get("description", "")
            horario_utc = comp.get("date", "")
            horario_local = (
                datetime.fromisoformat(horario_utc.replace("Z", "+00:00")) - timedelta(hours=3)
            ).strftime("%Y-%m-%d %H:%M")

            teams = comp.get("competitors", [])
            mandante = visitante = placar_m = placar_v = ""
            mandante_logo = visitante_logo = ""

            for team in teams:
                logo = team.get("team", {}).get("logos", [{}])
                logo_url = logo[0].get("href", "") if logo else ""
                if team.get("homeAway") == "home":
                    mandante = team.get("team", {}).get("shortDisplayName", "")
                    placar_m = team.get("score", "-")
                    mandante_logo = logo_url
                else:
                    visitante = team.get("team", {}).get("shortDisplayName", "")
                    placar_v = team.get("score", "-")
                    visitante_logo = logo_url

            partidas.append({
                "liga": liga_code,
                "mandante": mandante,
                "visitante": visitante,
                "placar_m": placar_m,
                "placar_v": placar_v,
                "mandante_logo": mandante_logo,
                "visitante_logo": visitante_logo,
                "status": status,
                "horario": horario_local
            })
        return partidas
    except Exception as e:
        print(f"Erro {liga_code} {data_str}: {e}")
        return []

# ===============================
# 🔁 Atualização inteligente
# ===============================
def atualizar_cache_rapida():
    hoje = datetime.utcnow().date()
    datas = [(hoje - timedelta(days=i)).strftime("%Y%m%d") for i in range(DIAS_PASSADOS,0,-1)] + \
            [hoje.strftime("%Y%m%d")] + \
            [(hoje + timedelta(days=i)).strftime("%Y%m%d") for i in range(1, DIAS_FUTUROS+1)]
    total_partidas = 0
    for liga_name, liga_code in LIGAS.items():
        ano = hoje.year
        novas = []
        for d in datas:
            partidas = buscar_dados(liga_code, d)
            if partidas:
                novas.extend(partidas)
        if novas:
            salvar_cache(liga_code, ano, novas)
            total_partidas += len(novas)
    return total_partidas

# ===============================
# 🔁 Carregar todas partidas
# ===============================
def carregar_todas_partidas():
    todas = []
    for liga_name, liga_code in LIGAS.items():
        for ano in ANOS_HISTORICOS:
            dados = carregar_cache(liga_code, ano)
            if dados:
                todas.extend(dados)
    return todas

# ===============================
# 🔘 Inicialização
# ===============================
if "dados" not in st.session_state:
    st.session_state["dados"] = carregar_todas_partidas()
if "last_update" not in st.session_state:
    st.session_state["last_update"] = None

# Atualização automática
now = datetime.now()
if st.session_state["last_update"] is None or (now - st.session_state["last_update"]) > timedelta(minutes=15):
    st.info("🔄 Atualizando partidas recentes...")
    total = atualizar_cache_rapida()
    st.session_state["dados"] = carregar_todas_partidas()
    st.session_state["last_update"] = now
    st.success(f"✅ Cache atualizado: {total} partidas")

# ===============================
# 🌐 API via query params
# ===============================
params = st.experimental_get_query_params()
if "endpoint" in params:
    endpoint = params["endpoint"][0].lower()
    dados = st.session_state["dados"]

    if endpoint == "matches":
        liga = params.get("liga", [None])[0]
        data = params.get("data", [None])[0]
        time = params.get("time", [None])[0]
        if liga:
            liga_code = LIGAS.get(liga)
            if liga_code:
                dados = [d for d in dados if d["liga"] == liga_code]
        if data:
            dados = [d for d in dados if d["horario"].startswith(data)]
        if time:
            dados = [d for d in dados if time.lower() in d["mandante"].lower() or time.lower() in d["visitante"].lower()]
        st.json({"count": len(dados), "matches": dados})
        st.stop()

    if endpoint == "leagues":
        st.json({"count": len(LIGAS), "leagues": list(LIGAS.keys())})
        st.stop()

    if endpoint == "upcoming":
        agora = datetime.utcnow()
        dados = [d for d in dados if datetime.strptime(d["horario"], "%Y-%m-%d %H:%M") >= agora]
        st.json({"count": len(dados), "matches": dados})
        st.stop()

    if endpoint == "results":
        agora = datetime.utcnow()
        dados = [d for d in dados if datetime.strptime(d["horario"], "%Y-%m-%d %H:%M") < agora]
        st.json({"count": len(dados), "matches": dados})
        st.stop()

    if endpoint == "update":
        total = atualizar_cache_rapida()
        st.session_state["dados"] = carregar_todas_partidas()
        st.session_state["last_update"] = datetime.now()
        st.json({"message": f"Cache atualizado com {total} partidas"})
        st.stop()

# ===============================
# 📊 Dashboard visual
# ===============================
ultima = st.session_state["last_update"].strftime("%d/%m/%Y %H:%M:%S") if st.session_state["last_update"] else "Nunca"
st.markdown(f"🕒 **Última atualização:** {ultima}")

dados_df = pd.DataFrame(st.session_state["dados"])

if not dados_df.empty:
    liga_selecionada = st.multiselect("Selecione ligas:", options=list(LIGAS.keys()), default=list(LIGAS.keys()))
    data_selecionada = st.date_input("Filtrar por data:", value=datetime.utcnow().date())
    dados_filtrados = dados_df[
        (dados_df["liga"].isin([LIGAS[l] for l in liga_selecionada])) &
        (pd.to_datetime(dados_df["horario"]).dt.date == data_selecionada)
    ]

    for idx, row in dados_filtrados.iterrows():
        st.markdown(f"### {row['mandante']} vs {row['visitante']}")
        st.image([row['mandante_logo'], row['visitante_logo']], width=80, caption=[row['mandante'], row['visitante']])
        st.markdown(f"**Placar:** {row['placar_m']} x {row['placar_v']} | **Status:** {row['status']}")
        st.markdown("---")
else:
    st.warning("Nenhum dado disponível no momento.")
