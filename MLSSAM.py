import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# =============================
# Configurações e segurança
# =============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1000000000000")
TELEGRAM_CHAT_ID_ALT2 = os.getenv("TELEGRAM_CHAT_ID_ALT2", "-1000000000001")

API_BASE = "https://test-rouket-nvgsix9abxckpjrnlfz79b.streamlit.app/api/mls"
CACHE_LIGAS = "cache_ligas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_ALERTAS = "cache_alertas.json"
CACHE_TIMEOUT = 3600  # 1 hora

# =============================
# Funções de cache
# =============================
def carregar_cache(caminho: str):
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if "_timestamp" in dados:
            if datetime.now().timestamp() - dados["_timestamp"] > CACHE_TIMEOUT:
                return {}
        return dados
    return {}

def salvar_cache(caminho: str, dados: dict):
    dados['_timestamp'] = datetime.now().timestamp()
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# =============================
# API Nova
# =============================
def obter_ligas():
    cache = carregar_cache(CACHE_LIGAS)
    if cache:
        return cache
    try:
        response = requests.get(f"{API_BASE}?endpoint=ligas", timeout=10)
        response.raise_for_status()
        ligas = response.json()
        salvar_cache(CACHE_LIGAS, ligas)
        return ligas
    except Exception as e:
        st.error(f"Erro ao buscar ligas: {e}")
        return {}

def obter_jogos(liga_id: str, data: str):
    cache = carregar_cache(CACHE_JOGOS)
    key = f"{liga_id}_{data}"
    if key in cache:
        return cache[key]
    try:
        response = requests.get(f"{API_BASE}?endpoint=jogos&liga={liga_id}&data={data}", timeout=10)
        response.raise_for_status()
        jogos = response.json()
        cache[key] = jogos
        salvar_cache(CACHE_JOGOS, cache)
        return jogos
    except Exception as e:
        st.error(f"Erro ao buscar jogos da liga {liga_id}: {e}")
        return []

# =============================
# Telegram
# =============================
def enviar_telegram(msg: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except:
        return False

# =============================
# Utilitários
# =============================
def formatar_data_iso(data_iso: str) -> tuple[str, str]:
    try:
        data_jogo = datetime.fromisoformat(data_iso.replace("Z", "+00:00")) - timedelta(hours=3)
        return data_jogo.strftime("%d/%m/%Y"), data_jogo.strftime("%H:%M")
    except:
        return "Data inválida", "Hora inválida"

def calcular_tendencia(home: str, away: str) -> tuple[float, float, str]:
    """Simples: tendência fictícia baseada em nomes (exemplo)."""
    import random
    estimativa = random.uniform(1.0, 4.0)
    if estimativa >= 3.0:
        return estimativa, 80, "Mais 2.5"
    elif estimativa >= 2.0:
        return estimativa, 70, "Mais 1.5"
    else:
        return estimativa, 60, "Menos 2.5"

# =============================
# Alertas
# =============================
def verificar_enviar_alerta(jogo):
    alertas = carregar_cache(CACHE_ALERTAS)
    fixture_id = str(jogo["id"])
    if fixture_id in alertas:
        return

    home = jogo["homeTeam"]["name"]
    away = jogo["awayTeam"]["name"]
    estimativa, confianca, tendencia = calcular_tendencia(home, away)

    data_formatada, hora_formatada = formatar_data_iso(jogo["utcDate"])
    liga = jogo.get("competition", {}).get("name", "Desconhecido")
    status = jogo.get("status", "DESCONHECIDO")
    msg = (
        f"⚽ <b>Alerta!</b>\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_formatada} ⏰ {hora_formatada}\n"
        f"📈 Tendência: {tendencia} | Estimativa: {estimativa:.2f} | Conf.: {confianca}%\n"
        f"🏆 Liga: {liga} | Status: {status}"
    )
    enviar_telegram(msg)
    alertas[fixture_id] = {"tendencia": tendencia, "estimativa": estimativa, "confianca": confianca}
    salvar_cache(CACHE_ALERTAS, alertas)

# =============================
# Streamlit App
# =============================
st.title("⚽ Nova API MLS - Elite Master")

# Ligas
ligas = obter_ligas()
if not ligas:
    st.warning("Nenhuma liga disponível")
    st.stop()

todas_ligas = st.checkbox("🌍 Todas as ligas", value=True)
liga_selecionada = None
if not todas_ligas:
    liga_selecionada = st.selectbox("Selecione Liga", list(ligas.keys()))

# Data
data_selecionada = st.date_input("📅 Data para análise:", datetime.today())
data_str = data_selecionada.strftime("%Y-%m-%d")

if st.button("🔍 Buscar Jogos"):
    st.info(f"Buscando jogos para {data_str}...")
    ligas_busca = ligas.values() if todas_ligas else [ligas[liga_selecionada]]
    todos_jogos = []

    for liga_id in ligas_busca:
        jogos = obter_jogos(liga_id, data_str)
        if jogos:
            for j in jogos:
                verificar_enviar_alerta(j)
            todos_jogos.extend(jogos)

    if todos_jogos:
        st.success(f"{len(todos_jogos)} jogos processados!")
        df = pd.DataFrame([
            {
                "Home": j["homeTeam"]["name"],
                "Away": j["awayTeam"]["name"],
                "Data": formatar_data_iso(j["utcDate"])[0],
                "Hora": formatar_data_iso(j["utcDate"])[1],
                "Status": j.get("status", "DESCONHECIDO"),
                "Liga": j.get("competition", {}).get("name", "Desconhecido")
            }
            for j in todos_jogos
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Nenhum jogo encontrado.")
