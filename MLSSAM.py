# ================================================
# ⚽ ESPN Soccer - Elite Master
# ================================================
import streamlit as st
import requests
import json
import os
import io
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações e Constantes
# =============================
st.set_page_config(page_title="⚽ ESPN Soccer - Elite", layout="wide")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003073115320")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1002754276285")
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Principais ligas (ESPN + MLS)
# =============================
LIGAS_ESPN = {
    "Brasileirão Série A": "br.1",
    "Brasileirão Série B": "br.2",
    "Premier League (Inglaterra)": "eng.1",
    "La Liga (Espanha)": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Liga MX (México)": "mex.1",
    "Saudi Pro League (Arábia)": "sau.1",
    "Copa Libertadores": "sud.1",
    "MLS (Estados Unidos)": "usa.1"
}

# =============================
# Funções utilitárias
# =============================
def carregar_json(caminho: str) -> dict:
    try:
        if os.path.exists(caminho):
            with open(caminho, "r", encoding='utf-8') as f:
                dados = json.load(f)
            # Checar timeout
            if caminho == CACHE_JOGOS:
                if "_timestamp" in dados:
                    if datetime.now().timestamp() - dados["_timestamp"] > CACHE_TIMEOUT:
                        return {}
            return dados
    except Exception:
        return {}
    return {}

def salvar_json(caminho: str, dados: dict):
    try:
        if caminho == CACHE_JOGOS:
            dados["_timestamp"] = datetime.now().timestamp()
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID):
    try:
        requests.get(BASE_URL_TG, params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

# =============================
# Função para buscar jogos ESPN
# =============================
def buscar_jogos_espn(liga_slug: str, data: str) -> list:
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_slug}/scoreboard"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dados = response.json()
        partidas = []

        for evento in dados.get("events", []):
            hora = evento.get("date", "")
            hora_dt = datetime.fromisoformat(hora.replace("Z", "+00:00")) - timedelta(hours=3) if hora else None
            hora_format = hora_dt.strftime("%d/%m %H:%M") if hora_dt else "-"
            competicao = evento.get("competitions", [])[0]
            times = competicao.get("competitors", [])
            if len(times) == 2:
                home = times[0]["team"]["displayName"]
                away = times[1]["team"]["displayName"]
                placar_home = times[0].get("score", "-")
                placar_away = times[1].get("score", "-")
            else:
                home = away = placar_home = placar_away = "-"
            partidas.append({
                "home": home,
                "away": away,
                "placar": f"{placar_home} - {placar_away}",
                "status": evento.get("status", {}).get("type", {}).get("description", "-"),
                "hora": hora_dt,
                "liga": competicao.get("league", {}).get("name", liga_slug)
            })
        return partidas
    except Exception as e:
        st.error(f"Erro ao buscar jogos da ESPN: {e}")
        return []

# =============================
# Funções de cache
# =============================
def carregar_cache_jogos() -> dict:
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados: dict):
    salvar_json(CACHE_JOGOS, dados)

# =============================
# Função para processar jogos
# =============================
def processar_jogos(data_str, ligas_busca, top_n, linhas_exibir):
    st.info(f"⏳ Buscando jogos para {data_str}...")
    cache = carregar_cache_jogos()
    todas_partidas = []

    for liga in ligas_busca:
        partidas = buscar_jogos_espn(liga, data_str)
        todas_partidas.extend(partidas)
    
    if not todas_partidas:
        st.warning("⚠️ Nenhum jogo encontrado para a data selecionada.")
        return

    # Salvar cache
    cache[data_str] = todas_partidas
    salvar_cache_jogos(cache)

    # Exibir tabela
    df = pd.DataFrame(todas_partidas)
    if linhas_exibir < len(df):
        df = df.head(linhas_exibir)
    st.dataframe(df, use_container_width=True)

    # Top N jogos (pode ser por horário ou critério que desejar)
    top_msg = f"📢 TOP {top_n} Jogos do Dia\n\n"
    for p in todas_partidas[:top_n]:
        top_msg += f"🏟️ {p['home']} vs {p['away']} | {p['placar']} | {p['status']} | {p['hora'].strftime('%H:%M') if p['hora'] else '-'}\n"
    enviar_telegram(top_msg, TELEGRAM_CHAT_ID_ALT2)
    st.success(f"✅ Top {top_n} jogos enviados para o Telegram!")

# =============================
# Interface Streamlit
# =============================
def main():
    st.title("⚽ ESPN Soccer - Elite Master")
    
    # Sidebar
    with st.sidebar:
        st.header("Configurações")
        top_n = st.selectbox("📊 Top N Jogos", [3,5,10], index=0)
        linhas_exibir = st.number_input("📄 Linhas a exibir na tabela", min_value=1, max_value=50, value=10, step=1)
    
    data_selecionada = st.date_input("📅 Data dos Jogos", value=datetime.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Botões
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 Buscar Jogos"):
            processar_jogos(data_str, LIGAS_ESPN.values(), top_n, linhas_exibir)
    with col2:
        if st.button("🔄 Atualizar Status"):
            st.success("✅ Status atualizado (simulação)")
    with col3:
        if st.button("🧹 Limpar Cache"):
            for f in [CACHE_JOGOS, ALERTAS_PATH]:
                if os.path.exists(f):
                    os.remove(f)
            st.success("✅ Cache limpo!")

if __name__ == "__main__":
    main()
