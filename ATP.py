import streamlit as st
import requests
import json
import os
from collections import deque
from streamlit_autorefresh import st_autorefresh

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "historico.json"
TIMESTAMP_PATH = "ultimo_timestamp.txt"
MAX_HISTORICO = 300

# === TELEGRAM ===
TELEGRAM_TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"

# === AUTOREFRESH A CADA 5 SEGUNDOS ===
st_autorefresh(interval=5000, key="atualizacao")

# === FUNÇÕES AUXILIARES ===
def obter_numero_e_timestamp():
    try:
        response = requests.get(API_URL)
        data = response.json()
        if (
            "data" in data and
            "result" in data["data"] and
            "outcome" in data["data"]["result"] and
            "number" in data["data"]["result"]["outcome"] and
            "settledAt" in data["data"]
        ):
            numero = data["data"]["result"]["outcome"]["number"]
            timestamp = data["data"]["settledAt"]
            return numero, timestamp
    except Exception as e:
        st.error(f"Erro ao acessar API: {e}")
    return None, None

def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        with open(HISTORICO_PATH, "r") as f:
            return json.load(f)
    return []

def salvar_historico(historico):
    with open(HISTORICO_PATH, "w") as f:
        json.dump(historico, f)

def carregar_timestamp():
    if os.path.exists(TIMESTAMP_PATH):
        with open(TIMESTAMP_PATH, "r") as f:
            return f.read().strip()
    return ""

def salvar_timestamp(timestamp):
    with open(TIMESTAMP_PATH, "w") as f:
        f.write(timestamp)

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensagem}
        requests.post(url, json=payload)
    except:
        st.warning("⚠️ Falha ao enviar mensagem no Telegram.")

# === EXECUÇÃO ===
numero, timestamp = obter_numero_e_timestamp()
ultimo_timestamp = carregar_timestamp()
historico = carregar_historico()

# === EXIBIÇÃO ===
st.title("🎯 Captura de Números da Roleta")
st.markdown(f"**📦 Número atual:** `{numero}`")
st.markdown(f"**⏱️ Timestamp da API:** `{timestamp}`")
st.markdown(f"**📊 Tamanho do histórico:** {len(historico)}")

# === PROCESSAMENTO ===
if numero is None or timestamp == ultimo_timestamp:
    st.warning("⏳ Aguardando novo sorteio...")
else:
    if len(historico) > 0 and historico[-1] == numero:
        st.info("🔁 Número já registrado.")
    else:
        historico.append(numero)
        if len(historico) > MAX_HISTORICO:
            historico = historico[-MAX_HISTORICO:]  # mantém os últimos 300
        salvar_historico(historico)
        salvar_timestamp(timestamp)
        msg = f"🎲 Novo número registrado: {numero}"
        st.success(msg)
        enviar_telegram(msg)

# === EXIBIÇÃO HISTÓRICO ===
st.markdown("### 📋 Últimos 10 números:")
st.write(historico[-10:])
