import streamlit as st
import requests
import os
import joblib
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pandas as pd

# === CONFIGURAÇÕES ===
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HISTORICO_PATH = "/mnt/data/historico_gnt.joblib"
INTERVALO_PREVISAO = 6  # Gera previsão a cada 6 sorteios
NUM_PREVISOES = 5       # Quantos números prever
MAX_HISTORICO = 300     # Limite do histórico mantido em memória

# === TELEGRAM CONFIG ===
TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002796136111"

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar Telegram: {e}")

# === FUNÇÕES AUXILIARES ===
def carregar_historico():
    if os.path.exists(HISTORICO_PATH):
        return joblib.load(HISTORICO_PATH)
    return deque(maxlen=MAX_HISTORICO)

def salvar_historico(historico):
    os.makedirs(os.path.dirname(HISTORICO_PATH), exist_ok=True)
    joblib.dump(historico, HISTORICO_PATH)

def capturar_numero_atual():
    try:
        resposta = requests.get(API_URL)
        dados = resposta.json()
        numero = dados['data']['result']['outcome']['number']
        timestamp = dados['data']['settledAt']
        return int(numero), timestamp
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return None, None

def teoria_dos_grandes_numeros(historico):
    if not historico:
        return []

    contagem = Counter(historico)
    total = len(historico)
    frequencias = {n: contagem.get(n, 0) / total for n in range(37)}
    diferencas = {n: abs(frequencias[n] - (1/37)) for n in range(37)}

    # Ordena por maior diferença para baixo (menos saíram do que o esperado)
    tendencia = sorted(diferencas.items(), key=lambda x: x[1], reverse=True)
    candidatos = [n for n, _ in tendencia if frequencias[n] < (1/37)]
    return candidatos[:NUM_PREVISOES]

# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="IA - Teoria dos Grandes Números", layout="centered")
st.title("🎯 Previsão com Teoria dos Grandes Números")
st_autorefresh(interval=5_000, key="auto")

# === EXECUÇÃO PRINCIPAL ===
historico = carregar_historico()
numero_atual, timestamp = capturar_numero_atual()

if "ultimo_timestamp" not in st.session_state:
    st.session_state.ultimo_timestamp = ""

if numero_atual is not None and timestamp != st.session_state.ultimo_timestamp:
    st.session_state.ultimo_timestamp = timestamp
    historico.append(numero_atual)
    salvar_historico(historico)

# Exibe histórico
st.subheader("📋 Histórico recente:")
st.write(list(historico)[-20:][::-1])  # últimos 20

# Lógica de previsão
if len(historico) >= 20 and len(historico) % INTERVALO_PREVISAO == 0:
    previsao = teoria_dos_grandes_numeros(historico)
    st.subheader("🔮 Previsão de Números:")
    st.success(f"Números sugeridos: {sorted(previsao)}")

    # Enviar para Telegram
    mensagem = "🎯 *Nova Previsão - IA Teoria dos Grandes Números*\n\n"
    mensagem += "\n".join([f"➡️ Número `{n}`" for n in sorted(previsao)])
    enviar_telegram(mensagem)

    if "ult_previsao" not in st.session_state:
        st.session_state.ult_previsao = []
        st.session_state.resultados = []

    if st.session_state.ult_previsao:
        ultimo_num = historico[-1]
        if ultimo_num in st.session_state.ult_previsao:
            st.success(f"✅ GREEN! {ultimo_num} estava na previsão anterior.")
            st.session_state.resultados.append("🟢")
        else:
            st.error(f"❌ RED! {ultimo_num} não estava na previsão anterior.")
            st.session_state.resultados.append("🔴")

    st.session_state.ult_previsao = previsao

# Dashboard de acertos
st.subheader("📊 Resultados recentes:")
st.write("".join(st.session_state.get("resultados", [])))
